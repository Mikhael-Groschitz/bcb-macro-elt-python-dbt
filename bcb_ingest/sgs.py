"""Extração do SGS."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import structlog
from pydantic import ValidationError

from bcb_ingest.armazenamento import gravar_landing, upsert_observacoes
from bcb_ingest.client import ClienteBCB, ErroRequisicaoInvalida
from bcb_ingest.contratos import SgsErro, SgsObservacao
from bcb_ingest.estado import Watermark, atualizar_watermark, obter_watermark
from bcb_ingest.janelas import particionar_janelas

logger = structlog.get_logger(__name__)

BASE_URL = "https://api.bcb.gov.br"
LOOKBACK_PADRAO_DIAS = 90


class ErroSgs(Exception):
    """Erro de domínio do SGS."""


@dataclass(frozen=True)
class ResultadoCarga:
    codigo_serie: int
    linhas_carregadas: int
    janelas: list[tuple[date, date]]
    duracao_segundos: float
    data_ultima_observacao: date | None


@dataclass(frozen=True)
class ConfiguracaoCarga:
    desde: date | None = None
    ate: date | None = None
    lookback_dias: int = LOOKBACK_PADRAO_DIAS
    execucao_id: str | None = None


def buscar_ultimos(cliente: ClienteBCB, codigo_serie: int, n: int) -> list[SgsObservacao]:
    structlog.contextvars.bind_contextvars(codigo_serie=codigo_serie, operacao="ultimos", n=n)
    try:
        caminho = f"/dados/serie/bcdata.sgs.{codigo_serie}/dados/ultimos/{n}"
        try:
            resposta = cliente.requisitar("GET", caminho, params={"formato": "json"})
        except ErroRequisicaoInvalida as erro:
            raise ErroSgs(_decodificar_erro(erro)) from erro

        dados_brutos = resposta.json()
        try:
            return [SgsObservacao.model_validate(item) for item in dados_brutos]
        except ValidationError as erro:
            raise ErroSgs(f"resposta do SGS não bate com o contrato esperado: {erro}") from erro
    finally:
        structlog.contextvars.unbind_contextvars("codigo_serie", "operacao", "n")


def carregar_historico(
    cliente: ClienteBCB,
    con: duckdb.DuckDBPyConnection,
    codigo_serie: int,
    landing_dir: Path,
    config: ConfiguracaoCarga | None = None,
) -> ResultadoCarga:
    config = config or ConfiguracaoCarga()
    execucao_id = config.execucao_id or str(uuid.uuid4())
    ate = config.ate or date.today()
    watermark = obter_watermark(con, codigo_serie)
    inicio = _resolver_inicio(watermark, config.desde, config.lookback_dias, codigo_serie)

    def processar_janela(janela_inicio: date, janela_fim: date) -> tuple[int, date | None]:
        caminho = f"/dados/serie/bcdata.sgs.{codigo_serie}/dados"
        params = {
            "formato": "json",
            "dataInicial": janela_inicio.strftime("%d/%m/%Y"),
            "dataFinal": janela_fim.strftime("%d/%m/%Y"),
        }
        try:
            resposta = cliente.requisitar("GET", caminho, params=params)
        except ErroRequisicaoInvalida as erro:
            raise ErroSgs(_decodificar_erro(erro)) from erro

        payload_bruto = resposta.json()
        gravar_landing(landing_dir, codigo_serie, janela_inicio, janela_fim, payload_bruto)

        try:
            observacoes = [SgsObservacao.model_validate(item) for item in payload_bruto]
        except ValidationError as erro:
            raise ErroSgs(f"resposta do SGS não bate com o contrato esperado: {erro}") from erro

        upsert_observacoes(
            con,
            codigo_serie=codigo_serie,
            observacoes=observacoes,
            payload_bruto=payload_bruto,
            execucao_id=execucao_id,
        )
        maior_data = max((obs.data for obs in observacoes), default=None)
        return len(observacoes), maior_data

    janelas = particionar_janelas(inicio, ate)
    total_linhas = 0
    data_maxima = watermark.data_ultima_observacao if watermark else None
    inicio_execucao = time.monotonic()

    structlog.contextvars.bind_contextvars(codigo_serie=codigo_serie, operacao="carregar_historico")
    try:
        for janela_inicio, janela_fim in janelas:
            linhas, maior_data = processar_janela(janela_inicio, janela_fim)
            total_linhas += linhas
            if maior_data is not None:
                data_maxima = maior_data if data_maxima is None else max(data_maxima, maior_data)
    finally:
        structlog.contextvars.unbind_contextvars("codigo_serie", "operacao")

    duracao = time.monotonic() - inicio_execucao
    atualizar_watermark(
        con,
        Watermark(
            codigo_serie=codigo_serie,
            data_ultima_observacao=data_maxima,
            horizonte_inicio=inicio,
            horizonte_fim=ate,
            contagem_linhas=total_linhas,
            executado_em=datetime.now(),
            execucao_id=execucao_id,
        ),
    )

    return ResultadoCarga(
        codigo_serie=codigo_serie,
        linhas_carregadas=total_linhas,
        janelas=janelas,
        duracao_segundos=duracao,
        data_ultima_observacao=data_maxima,
    )


def _resolver_inicio(
    watermark: Watermark | None, desde: date | None, lookback_dias: int, codigo_serie: int
) -> date:
    if watermark is not None and watermark.data_ultima_observacao is not None:
        return watermark.data_ultima_observacao - timedelta(days=lookback_dias)
    if desde is not None:
        return desde
    raise ErroSgs(f"série {codigo_serie} sem watermark: informe `desde` para a primeira carga")


def _decodificar_erro(erro: ErroRequisicaoInvalida) -> str:
    try:
        sgs_erro = SgsErro.model_validate_json(erro.corpo_bruto)
    except ValidationError:
        return f"SGS respondeu {erro.status_code}: {erro.corpo_bruto[:300]}"
    return f"SGS respondeu {erro.status_code}: {sgs_erro.error} - {sgs_erro.message}"
