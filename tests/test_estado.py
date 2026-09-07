"""Testes de bcb_ingest.estado (watermark)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime

import duckdb
import pytest

from bcb_ingest.db import conectar
from bcb_ingest.estado import Watermark, atualizar_watermark, obter_watermark


@pytest.fixture
def con() -> Iterator[duckdb.DuckDBPyConnection]:
    conexao = conectar(":memory:")
    yield conexao
    conexao.close()


def test_obter_watermark_inexistente_retorna_none(con: duckdb.DuckDBPyConnection) -> None:
    assert obter_watermark(con, codigo_serie=1) is None


def test_atualizar_e_obter_watermark(con: duckdb.DuckDBPyConnection) -> None:
    atualizar_watermark(
        con,
        Watermark(
            codigo_serie=1,
            data_ultima_observacao=date(2024, 6, 1),
            horizonte_inicio=date(2020, 1, 1),
            horizonte_fim=date(2024, 6, 1),
            contagem_linhas=1200,
            executado_em=datetime(2024, 6, 1, 10, 0, 0),
            execucao_id="exec-1",
        ),
    )

    watermark = obter_watermark(con, codigo_serie=1)

    assert watermark is not None
    assert watermark.data_ultima_observacao == date(2024, 6, 1)
    assert watermark.contagem_linhas == 1200
    assert watermark.execucao_id == "exec-1"


def test_atualizar_watermark_da_mesma_serie_sobrescreve_sem_duplicar(
    con: duckdb.DuckDBPyConnection,
) -> None:
    for dia, execucao in ((1, "exec-1"), (2, "exec-2")):
        atualizar_watermark(
            con,
            Watermark(
                codigo_serie=1,
                data_ultima_observacao=date(2024, 6, dia),
                horizonte_inicio=date(2020, 1, 1),
                horizonte_fim=date(2024, 6, dia),
                contagem_linhas=100 * dia,
                executado_em=datetime(2024, 6, dia, 10, 0, 0),
                execucao_id=execucao,
            ),
        )

    total = con.execute("SELECT COUNT(*) FROM _controle.ingestao").fetchone()
    watermark = obter_watermark(con, codigo_serie=1)

    assert total is not None
    assert total[0] == 1
    assert watermark is not None
    assert watermark.execucao_id == "exec-2"
    assert watermark.data_ultima_observacao == date(2024, 6, 2)


def test_watermarks_de_series_diferentes_nao_se_afetam(
    con: duckdb.DuckDBPyConnection,
) -> None:
    for codigo_serie in (1, 11):
        atualizar_watermark(
            con,
            Watermark(
                codigo_serie=codigo_serie,
                data_ultima_observacao=date(2024, 6, 1),
                horizonte_inicio=date(2020, 1, 1),
                horizonte_fim=date(2024, 6, 1),
                contagem_linhas=10,
                executado_em=datetime(2024, 6, 1, 10, 0, 0),
                execucao_id="exec-1",
            ),
        )

    assert obter_watermark(con, codigo_serie=1) is not None
    assert obter_watermark(con, codigo_serie=11) is not None
    assert obter_watermark(con, codigo_serie=99) is None
