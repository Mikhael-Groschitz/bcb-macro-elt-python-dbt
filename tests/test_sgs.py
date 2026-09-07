"""Testes de bcb_ingest.sgs.buscar_ultimos."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from bcb_ingest.client import ClienteBCB
from bcb_ingest.sgs import ErroSgs, buscar_ultimos

DIR_FIXTURES = Path(__file__).parent / "fixtures"
CAMINHO_ULTIMOS_5 = "/dados/serie/bcdata.sgs.1/dados/ultimos/5"


@respx.mock
def test_buscar_ultimos_retorna_observacoes_tipadas(
    cliente_teste: ClienteBCB, base_url_teste: str
) -> None:
    payload = json.loads((DIR_FIXTURES / "sgs_sucesso.json").read_text(encoding="utf-8"))
    respx.get(f"{base_url_teste}{CAMINHO_ULTIMOS_5}").mock(
        return_value=httpx.Response(200, json=payload)
    )

    observacoes = buscar_ultimos(cliente_teste, codigo_serie=1, n=5)

    assert len(observacoes) == 5
    assert observacoes[0].valor == Decimal("5.1816")


@respx.mock
def test_buscar_ultimos_decodifica_erro_de_janela_real(
    cliente_teste: ClienteBCB, base_url_teste: str
) -> None:
    corpo = (DIR_FIXTURES / "sgs_erro_janela.json").read_text(encoding="utf-8")
    respx.get(f"{base_url_teste}{CAMINHO_ULTIMOS_5}").mock(
        return_value=httpx.Response(406, text=corpo)
    )

    with pytest.raises(ErroSgs) as excinfo:
        buscar_ultimos(cliente_teste, codigo_serie=1, n=5)

    assert "10 anos" in str(excinfo.value)
