"""Watermark e controle de carga."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import duckdb


@dataclass(frozen=True)
class Watermark:
    codigo_serie: int
    data_ultima_observacao: date | None
    horizonte_inicio: date
    horizonte_fim: date
    contagem_linhas: int
    executado_em: datetime
    execucao_id: str


def obter_watermark(con: duckdb.DuckDBPyConnection, codigo_serie: int) -> Watermark | None:
    linha = con.execute(
        """
        SELECT codigo_serie, data_ultima_observacao, horizonte_inicio, horizonte_fim,
               contagem_linhas, executado_em, execucao_id
        FROM _controle.ingestao
        WHERE codigo_serie = ?
        """,
        [codigo_serie],
    ).fetchone()
    if linha is None:
        return None
    return Watermark(*linha)


@dataclass(frozen=True)
class WatermarkFocus:
    indicador: str
    data_coleta_maxima: date | None
    contagem_linhas: int
    executado_em: datetime
    execucao_id: str


def obter_watermark_focus(con: duckdb.DuckDBPyConnection, indicador: str) -> WatermarkFocus | None:
    linha = con.execute(
        """
        SELECT indicador, data_coleta_maxima, contagem_linhas, executado_em, execucao_id
        FROM _controle.ingestao_focus
        WHERE indicador = ?
        """,
        [indicador],
    ).fetchone()
    if linha is None:
        return None
    return WatermarkFocus(*linha)


def atualizar_watermark_focus(con: duckdb.DuckDBPyConnection, watermark: WatermarkFocus) -> None:
    con.execute(
        """
        INSERT INTO _controle.ingestao_focus
            (indicador, data_coleta_maxima, contagem_linhas, executado_em, execucao_id)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (indicador) DO UPDATE SET
            data_coleta_maxima = excluded.data_coleta_maxima,
            contagem_linhas = excluded.contagem_linhas,
            executado_em = excluded.executado_em,
            execucao_id = excluded.execucao_id
        """,
        [
            watermark.indicador,
            watermark.data_coleta_maxima,
            watermark.contagem_linhas,
            watermark.executado_em,
            watermark.execucao_id,
        ],
    )


def atualizar_watermark(con: duckdb.DuckDBPyConnection, watermark: Watermark) -> None:
    con.execute(
        """
        INSERT INTO _controle.ingestao
            (codigo_serie, data_ultima_observacao, horizonte_inicio, horizonte_fim,
             contagem_linhas, executado_em, execucao_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (codigo_serie) DO UPDATE SET
            data_ultima_observacao = excluded.data_ultima_observacao,
            horizonte_inicio = excluded.horizonte_inicio,
            horizonte_fim = excluded.horizonte_fim,
            contagem_linhas = excluded.contagem_linhas,
            executado_em = excluded.executado_em,
            execucao_id = excluded.execucao_id
        """,
        [
            watermark.codigo_serie,
            watermark.data_ultima_observacao,
            watermark.horizonte_inicio,
            watermark.horizonte_fim,
            watermark.contagem_linhas,
            watermark.executado_em,
            watermark.execucao_id,
        ],
    )
