"""Orquestração da carga completa do catálogo e leitura de status agregado."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import duckdb
import structlog

from bcb_ingest.catalogo import DATA_INICIO_PADRAO, INDICADORES_FOCUS, SERIES_SGS
from bcb_ingest.client import ClienteBCB, ErroClienteBcb
from bcb_ingest.estado import obter_watermark, obter_watermark_focus
from bcb_ingest.focus import ConfiguracaoCargaFocus, ErroFocus, carregar_historico_indicador
from bcb_ingest.sgs import ConfiguracaoCarga, ErroSgs, carregar_historico

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ResultadoItemIngestao:
    tipo: str
    identificador: str
    sucesso: bool
    linhas_carregadas: int | None
    erro: str | None


@dataclass(frozen=True)
class ResultadoIngestaoTudo:
    itens: list[ResultadoItemIngestao]
    duracao_segundos: float


def ingerir_tudo(
    cliente_sgs: ClienteBCB,
    cliente_focus: ClienteBCB,
    con: duckdb.DuckDBPyConnection,
    landing_dir: Path,
) -> ResultadoIngestaoTudo:
    inicio_execucao = time.monotonic()
    itens: list[ResultadoItemIngestao] = []

    for codigo_serie in SERIES_SGS:
        try:
            resultado = carregar_historico(
                cliente_sgs,
                con,
                codigo_serie,
                landing_dir,
                ConfiguracaoCarga(desde=DATA_INICIO_PADRAO),
            )
        except (ErroClienteBcb, ErroSgs) as erro:
            logger.error("falha_ingest_sgs", codigo_serie=codigo_serie, erro=str(erro))
            itens.append(ResultadoItemIngestao("sgs", str(codigo_serie), False, None, str(erro)))
        else:
            itens.append(
                ResultadoItemIngestao(
                    "sgs", str(codigo_serie), True, resultado.linhas_carregadas, None
                )
            )

    for indicador in INDICADORES_FOCUS:
        try:
            resultado_focus = carregar_historico_indicador(
                cliente_focus, con, indicador, landing_dir, ConfiguracaoCargaFocus()
            )
        except (ErroClienteBcb, ErroFocus) as erro:
            logger.error("falha_ingest_focus", indicador=indicador, erro=str(erro))
            itens.append(ResultadoItemIngestao("focus", indicador, False, None, str(erro)))
        else:
            itens.append(
                ResultadoItemIngestao(
                    "focus", indicador, True, resultado_focus.linhas_carregadas, None
                )
            )

    return ResultadoIngestaoTudo(itens=itens, duracao_segundos=time.monotonic() - inicio_execucao)


@dataclass(frozen=True)
class ItemStatus:
    tipo: str
    identificador: str
    carregado: bool
    data_referencia: date | None
    contagem_linhas: int | None
    executado_em: datetime | None


def obter_status_geral(con: duckdb.DuckDBPyConnection) -> list[ItemStatus]:
    itens: list[ItemStatus] = []

    for codigo_serie in SERIES_SGS:
        watermark = obter_watermark(con, codigo_serie)
        itens.append(
            ItemStatus(
                tipo="sgs",
                identificador=str(codigo_serie),
                carregado=watermark is not None,
                data_referencia=watermark.data_ultima_observacao if watermark else None,
                contagem_linhas=watermark.contagem_linhas if watermark else None,
                executado_em=watermark.executado_em if watermark else None,
            )
        )

    for indicador in INDICADORES_FOCUS:
        watermark_focus = obter_watermark_focus(con, indicador)
        itens.append(
            ItemStatus(
                tipo="focus",
                identificador=indicador,
                carregado=watermark_focus is not None,
                data_referencia=watermark_focus.data_coleta_maxima if watermark_focus else None,
                contagem_linhas=watermark_focus.contagem_linhas if watermark_focus else None,
                executado_em=watermark_focus.executado_em if watermark_focus else None,
            )
        )

    return itens
