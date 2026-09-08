"""Testes de bcb_ingest.orquestracao."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import duckdb
import httpx
import pytest
import respx

from bcb_ingest.catalogo import INDICADORES_FOCUS, SERIES_SGS
from bcb_ingest.client import ClienteBCB, ConfiguracaoCliente
from bcb_ingest.db import conectar
from bcb_ingest.orquestracao import ingerir_tudo, obter_status_geral

HOST_SGS = "https://sgs.teste.bcb.gov.br"
HOST_FOCUS = "https://olinda.teste.bcb.gov.br"


@pytest.fixture
def con() -> Iterator[duckdb.DuckDBPyConnection]:
    conexao = conectar(":memory:")
    yield conexao
    conexao.close()


@pytest.fixture
def cliente_sgs() -> Iterator[ClienteBCB]:
    config = ConfiguracaoCliente(base_url=HOST_SGS, max_tentativas=1)
    with ClienteBCB(config) as c:
        yield c


@pytest.fixture
def cliente_focus() -> Iterator[ClienteBCB]:
    config = ConfiguracaoCliente(base_url=HOST_FOCUS, max_tentativas=1)
    with ClienteBCB(config) as c:
        yield c


def _mockar_catalogo_inteiro_vazio() -> None:
    respx.route(host="sgs.teste.bcb.gov.br").mock(return_value=httpx.Response(200, json=[]))
    respx.route(host="olinda.teste.bcb.gov.br").mock(
        return_value=httpx.Response(200, json={"@odata.context": "x", "value": []})
    )


@respx.mock
def test_ingerir_tudo_sucesso_cobre_catalogo_inteiro(
    con: duckdb.DuckDBPyConnection,
    cliente_sgs: ClienteBCB,
    cliente_focus: ClienteBCB,
    tmp_path: Path,
) -> None:
    _mockar_catalogo_inteiro_vazio()

    resultado = ingerir_tudo(cliente_sgs, cliente_focus, con, tmp_path)

    assert len(resultado.itens) == len(SERIES_SGS) + len(INDICADORES_FOCUS)
    assert all(item.sucesso for item in resultado.itens)
    identificadores_sgs = {item.identificador for item in resultado.itens if item.tipo == "sgs"}
    assert identificadores_sgs == {str(codigo) for codigo in SERIES_SGS}
    identificadores_focus = {item.identificador for item in resultado.itens if item.tipo == "focus"}
    assert identificadores_focus == set(INDICADORES_FOCUS)


@respx.mock
def test_ingerir_tudo_falha_isolada_nao_interrompe_as_demais(
    con: duckdb.DuckDBPyConnection,
    cliente_sgs: ClienteBCB,
    cliente_focus: ClienteBCB,
    tmp_path: Path,
) -> None:
    respx.get(url__regex=r".*bcdata\.sgs\.432/dados.*").mock(return_value=httpx.Response(500))
    _mockar_catalogo_inteiro_vazio()

    resultado = ingerir_tudo(cliente_sgs, cliente_focus, con, tmp_path)

    por_identificador = {item.identificador: item for item in resultado.itens}
    assert por_identificador["432"].sucesso is False
    assert por_identificador["432"].erro is not None
    outros = [item for item in resultado.itens if item.identificador != "432"]
    assert all(item.sucesso for item in outros)


def test_obter_status_geral_sem_carga_marca_tudo_como_nao_carregado(
    con: duckdb.DuckDBPyConnection,
) -> None:
    itens = obter_status_geral(con)

    assert len(itens) == len(SERIES_SGS) + len(INDICADORES_FOCUS)
    assert all(not item.carregado for item in itens)
    assert all(item.data_referencia is None for item in itens)
