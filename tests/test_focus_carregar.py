"""Testes de bcb_ingest.focus.carregar_historico_indicador."""

from __future__ import annotations

from collections.abc import Iterator

import duckdb
import httpx
import pytest
import respx

from bcb_ingest.client import ClienteBCB, ConfiguracaoCliente
from bcb_ingest.db import conectar
from bcb_ingest.estado import obter_watermark_focus
from bcb_ingest.focus import ConfiguracaoCargaFocus, ErroFocus, carregar_historico_indicador

INDICADOR = "IPCA"
URL_RECURSO = "https://olinda.teste.bcb.gov.br/ExpectativasMercadoAnuais"


@pytest.fixture
def con() -> Iterator[duckdb.DuckDBPyConnection]:
    conexao = conectar(":memory:")
    yield conexao
    conexao.close()


@pytest.fixture
def cliente() -> Iterator[ClienteBCB]:
    config = ConfiguracaoCliente(base_url="https://olinda.teste.bcb.gov.br", max_tentativas=1)
    with ClienteBCB(config) as c:
        yield c


def _item(**overrides: object) -> dict[str, object]:
    base = {
        "Indicador": INDICADOR,
        "IndicadorDetalhe": None,
        "Data": "2026-08-21",
        "DataReferencia": "2026",
        "Media": 5.0122,
        "Mediana": 5.0164,
        "DesvioPadrao": 0.2139,
        "Minimo": 4.3,
        "Maximo": 5.8146,
        "numeroRespondentes": 148,
        "baseCalculo": 0,
    }
    base.update(overrides)
    return base


def _envelope(itens: list[dict[str, object]]) -> dict[str, object]:
    return {"@odata.context": "https://exemplo/$metadata#ExpectativasMercadoAnuais", "value": itens}


@respx.mock
def test_carga_com_duas_paginas_ate_pagina_vazia(
    con: duckdb.DuckDBPyConnection, cliente: ClienteBCB, tmp_path
) -> None:
    respx.get(URL_RECURSO).mock(
        side_effect=[
            httpx.Response(200, json=_envelope([_item(DataReferencia="2026")])),
            httpx.Response(200, json=_envelope([_item(DataReferencia="2027")])),
            httpx.Response(200, json=_envelope([])),
        ]
    )

    resultado = carregar_historico_indicador(
        cliente, con, INDICADOR, tmp_path, ConfiguracaoCargaFocus(tamanho_pagina=1)
    )

    assert resultado.linhas_carregadas == 2
    assert resultado.paginas == 2
    assert (tmp_path / "focus" / "indicador=IPCA" / "pagina=0_1.json").exists()
    assert (tmp_path / "focus" / "indicador=IPCA" / "pagina=2_1.json").exists()

    watermark = obter_watermark_focus(con, INDICADOR)
    assert watermark is not None
    assert watermark.contagem_linhas == 2


@respx.mock
def test_pagina_parcial_nao_encerra_sozinha(
    con: duckdb.DuckDBPyConnection, cliente: ClienteBCB, tmp_path
) -> None:
    respx.get(URL_RECURSO).mock(
        side_effect=[
            httpx.Response(
                200, json=_envelope([_item(DataReferencia="2026"), _item(DataReferencia="2027")])
            ),
            httpx.Response(200, json=_envelope([])),
        ]
    )

    resultado = carregar_historico_indicador(
        cliente, con, INDICADOR, tmp_path, ConfiguracaoCargaFocus(tamanho_pagina=5)
    )

    assert resultado.linhas_carregadas == 2
    assert resultado.paginas == 1


@respx.mock
def test_pagina_repetida_levanta_erro(
    con: duckdb.DuckDBPyConnection, cliente: ClienteBCB, tmp_path
) -> None:
    pagina_repetida = _envelope([_item(DataReferencia="2026")])
    respx.get(URL_RECURSO).mock(
        side_effect=[
            httpx.Response(200, json=pagina_repetida),
            httpx.Response(200, json=pagina_repetida),
        ]
    )

    with pytest.raises(ErroFocus, match="repetida"):
        carregar_historico_indicador(
            cliente, con, INDICADOR, tmp_path, ConfiguracaoCargaFocus(tamanho_pagina=1)
        )


@respx.mock
def test_teto_de_paginas_levanta_erro(
    con: duckdb.DuckDBPyConnection, cliente: ClienteBCB, tmp_path
) -> None:
    respx.get(URL_RECURSO).mock(
        side_effect=[
            httpx.Response(200, json=_envelope([_item(DataReferencia=str(ano))]))
            for ano in range(2000, 2010)
        ]
    )

    with pytest.raises(ErroFocus, match="limite de 3 páginas"):
        carregar_historico_indicador(
            cliente,
            con,
            INDICADOR,
            tmp_path,
            ConfiguracaoCargaFocus(tamanho_pagina=1, max_paginas=3),
        )


@respx.mock
def test_segunda_execucao_usa_filtro_incremental_e_nao_duplica(
    con: duckdb.DuckDBPyConnection, cliente: ClienteBCB, tmp_path
) -> None:
    filtros_recebidos: list[str] = []

    def responder(request: httpx.Request) -> httpx.Response:
        filtros_recebidos.append(request.url.params["$filter"])
        if request.url.params["$skip"] == "0":
            return httpx.Response(200, json=_envelope([_item(Data="2026-08-21")]))
        return httpx.Response(200, json=_envelope([]))

    respx.get(URL_RECURSO).mock(side_effect=responder)

    carregar_historico_indicador(
        cliente, con, INDICADOR, tmp_path, ConfiguracaoCargaFocus(tamanho_pagina=10)
    )
    carregar_historico_indicador(
        cliente, con, INDICADOR, tmp_path, ConfiguracaoCargaFocus(tamanho_pagina=10)
    )

    total = con.execute("SELECT COUNT(*) FROM raw.focus_expectativa").fetchone()

    assert "Data gt" not in filtros_recebidos[0]
    assert "Data gt '2026-08-21'" in filtros_recebidos[2]
    assert total is not None
    assert total[0] == 1
