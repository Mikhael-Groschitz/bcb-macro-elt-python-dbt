"""Testes de bcb_ingest.db.resetar_ingestao."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime

import duckdb
import pytest

from bcb_ingest.db import conectar, resetar_ingestao
from bcb_ingest.estado import Watermark, atualizar_watermark, obter_watermark


@pytest.fixture
def con() -> Iterator[duckdb.DuckDBPyConnection]:
    conexao = conectar(":memory:")
    yield conexao
    conexao.close()


def test_resetar_ingestao_limpa_raw_e_controle_mas_mantem_schema(
    con: duckdb.DuckDBPyConnection,
) -> None:
    con.execute(
        """
        INSERT INTO raw.sgs_observacao VALUES
            (1, '2024-01-01', 5.0, now(), 'exec-1', 'hash-1')
        """
    )
    atualizar_watermark(
        con,
        Watermark(
            codigo_serie=1,
            data_ultima_observacao=date(2024, 1, 1),
            horizonte_inicio=date(2020, 1, 1),
            horizonte_fim=date(2024, 1, 1),
            contagem_linhas=1,
            executado_em=datetime(2024, 1, 1, 10, 0, 0),
            execucao_id="exec-1",
        ),
    )

    resetar_ingestao(con)

    assert obter_watermark(con, codigo_serie=1) is None
    assert con.execute("SELECT count(*) FROM raw.sgs_observacao").fetchone() == (0,)
