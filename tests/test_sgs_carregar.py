"""Testes de bcb_ingest.sgs.carregar_historico."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import duckdb
import httpx
import pytest
import respx

from bcb_ingest.client import ClienteBCB, ConfiguracaoCliente
from bcb_ingest.db import conectar
from bcb_ingest.estado import obter_watermark
from bcb_ingest.sgs import ConfiguracaoCarga, ErroSgs, carregar_historico

CODIGO_SERIE = 1


@pytest.fixture
def con() -> Iterator[duckdb.DuckDBPyConnection]:
    conexao = conectar(":memory:")
    yield conexao
    conexao.close()


@pytest.fixture
def cliente() -> Iterator[ClienteBCB]:
    config = ConfiguracaoCliente(base_url="https://api.teste.bcb.gov.br", max_tentativas=1)
    with ClienteBCB(config) as c:
        yield c


def _payload(*pares: tuple[str, str]) -> list[dict[str, str]]:
    return [{"data": data, "valor": valor} for data, valor in pares]


@respx.mock
def test_primeira_carga_sem_watermark_usa_desde(
    con: duckdb.DuckDBPyConnection, cliente: ClienteBCB, tmp_path: Path
) -> None:
    respx.get(
        "https://api.teste.bcb.gov.br/dados/serie/bcdata.sgs.1/dados",
        params={"formato": "json", "dataInicial": "01/01/2024", "dataFinal": "10/01/2024"},
    ).mock(return_value=httpx.Response(200, json=_payload(("02/01/2024", "5.00"))))

    resultado = carregar_historico(
        cliente,
        con,
        CODIGO_SERIE,
        tmp_path,
        ConfiguracaoCarga(desde=date(2024, 1, 1), ate=date(2024, 1, 10)),
    )

    assert resultado.linhas_carregadas == 1
    assert resultado.data_ultima_observacao == date(2024, 1, 2)
    assert (tmp_path / "sgs" / "serie=1" / "janela=2024-01-01_2024-01-10.json").exists()

    watermark = obter_watermark(con, CODIGO_SERIE)
    assert watermark is not None
    assert watermark.data_ultima_observacao == date(2024, 1, 2)
    assert watermark.contagem_linhas == 1


def test_sem_watermark_e_sem_desde_levanta_erro(
    con: duckdb.DuckDBPyConnection, cliente: ClienteBCB, tmp_path: Path
) -> None:
    with pytest.raises(ErroSgs, match="watermark"):
        carregar_historico(cliente, con, CODIGO_SERIE, tmp_path, ConfiguracaoCarga())


@respx.mock
def test_janela_maior_que_dez_anos_dispara_duas_requisicoes(
    con: duckdb.DuckDBPyConnection, cliente: ClienteBCB, tmp_path: Path
) -> None:
    rota = respx.get("https://api.teste.bcb.gov.br/dados/serie/bcdata.sgs.1/dados").mock(
        side_effect=[
            httpx.Response(200, json=_payload(("10/06/2010", "3.00"))),
            httpx.Response(200, json=_payload(("01/03/2023", "5.00"))),
        ]
    )

    resultado = carregar_historico(
        cliente,
        con,
        CODIGO_SERIE,
        tmp_path,
        ConfiguracaoCarga(desde=date(2010, 6, 10), ate=date(2023, 3, 1)),
    )

    assert rota.call_count == 2
    assert len(resultado.janelas) == 2
    assert resultado.linhas_carregadas == 2


@respx.mock
def test_segunda_execucao_imediata_nao_duplica_linha(
    con: duckdb.DuckDBPyConnection, cliente: ClienteBCB, tmp_path: Path
) -> None:
    payload = _payload(("08/01/2024", "5.00"), ("09/01/2024", "5.01"), ("10/01/2024", "5.02"))
    respx.get("https://api.teste.bcb.gov.br/dados/serie/bcdata.sgs.1/dados").mock(
        return_value=httpx.Response(200, json=payload)
    )

    carregar_historico(
        cliente,
        con,
        CODIGO_SERIE,
        tmp_path,
        ConfiguracaoCarga(desde=date(2024, 1, 1), ate=date(2024, 1, 10)),
    )
    total_apos_primeira = con.execute(
        "SELECT COUNT(*) FROM raw.sgs_observacao WHERE codigo_serie = ?", [CODIGO_SERIE]
    ).fetchone()

    resultado_segunda = carregar_historico(
        cliente,
        con,
        CODIGO_SERIE,
        tmp_path,
        ConfiguracaoCarga(ate=date(2024, 1, 10), lookback_dias=90),
    )
    total_apos_segunda = con.execute(
        "SELECT COUNT(*) FROM raw.sgs_observacao WHERE codigo_serie = ?", [CODIGO_SERIE]
    ).fetchone()

    assert total_apos_primeira is not None
    assert total_apos_segunda is not None
    assert total_apos_primeira[0] == total_apos_segunda[0] == 3
    assert resultado_segunda.linhas_carregadas == 3


@respx.mock
def test_revisao_de_valor_atualiza_sem_duplicar(
    con: duckdb.DuckDBPyConnection, cliente: ClienteBCB, tmp_path: Path
) -> None:
    rota = respx.get("https://api.teste.bcb.gov.br/dados/serie/bcdata.sgs.1/dados").mock(
        side_effect=[
            httpx.Response(200, json=_payload(("08/01/2024", "5.00"))),
            httpx.Response(200, json=_payload(("08/01/2024", "5.10"))),
        ]
    )

    carregar_historico(
        cliente,
        con,
        CODIGO_SERIE,
        tmp_path,
        ConfiguracaoCarga(desde=date(2024, 1, 8), ate=date(2024, 1, 8)),
    )
    carregar_historico(
        cliente,
        con,
        CODIGO_SERIE,
        tmp_path,
        ConfiguracaoCarga(ate=date(2024, 1, 8), lookback_dias=10),
    )

    linhas = con.execute(
        "SELECT valor FROM raw.sgs_observacao WHERE codigo_serie = ?", [CODIGO_SERIE]
    ).fetchall()

    assert rota.call_count == 2
    assert len(linhas) == 1
    assert str(linhas[0][0]) == "5.100000"
