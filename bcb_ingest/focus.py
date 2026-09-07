"""Extração do Focus/Olinda."""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb
import structlog
from pydantic import ValidationError

from bcb_ingest.armazenamento import gravar_landing_focus, upsert_expectativas
from bcb_ingest.client import ClienteBCB, ErroRequisicaoInvalida
from bcb_ingest.contratos import FocusExpectativaAnual
from bcb_ingest.estado import WatermarkFocus, atualizar_watermark_focus, obter_watermark_focus

logger = structlog.get_logger(__name__)

BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata"
RECURSO_ANUAL = "ExpectativasMercadoAnuais"
TAMANHO_PAGINA_PADRAO = 1000
MAX_PAGINAS_PADRAO = 200
ORDERBY_ANUAL = "Data asc,DataReferencia asc,baseCalculo asc"

_PADRAO_ENVELOPE = re.compile(r"^\s*/\*(?P<corpo>.*)\*/\s*$", re.DOTALL)


class ErroFocus(Exception):
    """Erro de domínio do Focus."""


@dataclass(frozen=True)
class ResultadoCargaFocus:
    indicador: str
    linhas_carregadas: int
    paginas: int
    duracao_segundos: float
    data_coleta_maxima: date | None


@dataclass(frozen=True)
class ConfiguracaoCargaFocus:
    tamanho_pagina: int = TAMANHO_PAGINA_PADRAO
    max_paginas: int = MAX_PAGINAS_PADRAO
    execucao_id: str | None = None


def decodificar_erro_olinda(corpo_bruto: str) -> str:
    casamento = _PADRAO_ENVELOPE.match(corpo_bruto)
    texto_json = casamento.group("corpo") if casamento else corpo_bruto
    try:
        dados = json.loads(texto_json)
        codigo = dados["codigo"]
        mensagem = dados["mensagem"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return f"Olinda respondeu com corpo não reconhecido: {corpo_bruto[:300]}"
    return f"Olinda respondeu {codigo}: {mensagem}"


def carregar_historico_indicador(
    cliente: ClienteBCB,
    con: duckdb.DuckDBPyConnection,
    indicador: str,
    landing_dir: Path,
    config: ConfiguracaoCargaFocus | None = None,
) -> ResultadoCargaFocus:
    config = config or ConfiguracaoCargaFocus()
    execucao_id = config.execucao_id or str(uuid.uuid4())
    watermark = obter_watermark_focus(con, indicador)
    data_coleta_minima = watermark.data_coleta_maxima if watermark else None

    filtro = f"Indicador eq '{indicador}'"
    if data_coleta_minima is not None:
        filtro += f" and Data gt '{data_coleta_minima.isoformat()}'"

    def buscar_pagina(skip: int) -> list[dict[str, Any]]:
        params = {
            "$format": "json",
            "$filter": filtro,
            "$orderby": ORDERBY_ANUAL,
            "$top": str(config.tamanho_pagina),
            "$skip": str(skip),
        }
        try:
            resposta = cliente.requisitar("GET", f"/{RECURSO_ANUAL}", params=params)
        except ErroRequisicaoInvalida as erro:
            raise ErroFocus(decodificar_erro_olinda(erro.corpo_bruto)) from erro
        envelope: dict[str, Any] = resposta.json()
        return envelope["value"]  # type: ignore[no-any-return]

    def processar_pagina(payload_bruto: list[dict[str, Any]]) -> tuple[int, date | None]:
        try:
            itens = [FocusExpectativaAnual.model_validate(item) for item in payload_bruto]
        except ValidationError as erro:
            raise ErroFocus(f"resposta do Focus não bate com o contrato esperado: {erro}") from erro
        upsert_expectativas(con, itens=itens, payload_bruto=payload_bruto, execucao_id=execucao_id)
        maior_data = max((item.Data for item in itens), default=None)
        return len(itens), maior_data

    total_linhas = 0
    paginas_processadas = 0
    data_maxima = data_coleta_minima
    pagina_anterior: str | None = None
    skip = 0
    inicio_execucao = time.monotonic()

    structlog.contextvars.bind_contextvars(indicador=indicador, operacao="carregar_historico_focus")
    try:
        for _ in range(config.max_paginas + 1):
            payload_bruto = buscar_pagina(skip)
            gravar_landing_focus(landing_dir, indicador, skip, config.tamanho_pagina, payload_bruto)

            if not payload_bruto:
                break

            hash_pagina = _hash_pagina(payload_bruto)
            if hash_pagina == pagina_anterior:
                raise ErroFocus(f"página repetida para indicador {indicador!r} em skip={skip}")
            pagina_anterior = hash_pagina

            linhas, maior_data = processar_pagina(payload_bruto)
            total_linhas += linhas
            paginas_processadas += 1
            if maior_data is not None:
                data_maxima = maior_data if data_maxima is None else max(data_maxima, maior_data)

            skip += config.tamanho_pagina
        else:
            raise ErroFocus(
                f"limite de {config.max_paginas} páginas atingido para indicador {indicador!r}"
            )
    finally:
        structlog.contextvars.unbind_contextvars("indicador", "operacao")

    duracao = time.monotonic() - inicio_execucao
    atualizar_watermark_focus(
        con,
        WatermarkFocus(
            indicador=indicador,
            data_coleta_maxima=data_maxima,
            contagem_linhas=total_linhas,
            executado_em=datetime.now(),
            execucao_id=execucao_id,
        ),
    )

    return ResultadoCargaFocus(
        indicador=indicador,
        linhas_carregadas=total_linhas,
        paginas=paginas_processadas,
        duracao_segundos=duracao,
        data_coleta_maxima=data_maxima,
    )


def _hash_pagina(payload_bruto: list[dict[str, Any]]) -> str:
    canonico = json.dumps(payload_bruto, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()
