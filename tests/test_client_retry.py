"""Testes de retry do ClienteBCB."""

from __future__ import annotations

import httpx
import pytest
import respx

from bcb_ingest.client import ClienteBCB, ErroRequisicaoInvalida, ErroServidorIndisponivel

CAMINHO = "/dados/teste"


@respx.mock
def test_retry_em_429_ate_sucesso(
    cliente_teste: ClienteBCB, espiao_dormir, base_url_teste: str
) -> None:
    rota = respx.get(f"{base_url_teste}{CAMINHO}").mock(
        side_effect=[httpx.Response(429), httpx.Response(429), httpx.Response(200, json=[])]
    )

    resposta = cliente_teste.requisitar("GET", CAMINHO)

    assert resposta.status_code == 200
    assert rota.call_count == 3
    assert len(espiao_dormir.chamadas) == 2


@respx.mock
def test_retry_em_5xx_ate_sucesso(
    cliente_teste: ClienteBCB, espiao_dormir, base_url_teste: str
) -> None:
    rota = respx.get(f"{base_url_teste}{CAMINHO}").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=[])]
    )

    resposta = cliente_teste.requisitar("GET", CAMINHO)

    assert resposta.status_code == 200
    assert rota.call_count == 2
    assert len(espiao_dormir.chamadas) == 1


@respx.mock
def test_retry_em_timeout_ate_sucesso(
    cliente_teste: ClienteBCB, espiao_dormir, base_url_teste: str
) -> None:
    rota = respx.get(f"{base_url_teste}{CAMINHO}").mock(
        side_effect=[httpx.ReadTimeout("tempo esgotado"), httpx.Response(200, json=[])]
    )

    resposta = cliente_teste.requisitar("GET", CAMINHO)

    assert resposta.status_code == 200
    assert rota.call_count == 2
    assert len(espiao_dormir.chamadas) == 1


@respx.mock
def test_erro_4xx_nao_gera_retry(
    cliente_teste: ClienteBCB, espiao_dormir, base_url_teste: str
) -> None:
    rota = respx.get(f"{base_url_teste}{CAMINHO}").mock(
        return_value=httpx.Response(406, text="corpo do erro")
    )

    with pytest.raises(ErroRequisicaoInvalida) as excinfo:
        cliente_teste.requisitar("GET", CAMINHO)

    assert excinfo.value.status_code == 406
    assert excinfo.value.corpo_bruto == "corpo do erro"
    assert rota.call_count == 1
    assert espiao_dormir.chamadas == []


@respx.mock
def test_tentativas_esgotadas_levanta_erro_servidor(
    cliente_teste: ClienteBCB, espiao_dormir, base_url_teste: str
) -> None:
    rota = respx.get(f"{base_url_teste}{CAMINHO}").mock(return_value=httpx.Response(429))

    with pytest.raises(ErroServidorIndisponivel) as excinfo:
        cliente_teste.requisitar("GET", CAMINHO)

    assert excinfo.value.tentativas == 3
    assert rota.call_count == 3
    assert len(espiao_dormir.chamadas) == 2


@respx.mock
def test_304_por_etag_nao_gera_erro_nem_retry(
    cliente_teste: ClienteBCB, espiao_dormir, base_url_teste: str
) -> None:
    rota = respx.get(f"{base_url_teste}{CAMINHO}").mock(return_value=httpx.Response(304))

    resposta = cliente_teste.requisitar("GET", CAMINHO, etag_anterior='W/"abc"')

    assert resposta.status_code == 304
    assert rota.call_count == 1
    assert espiao_dormir.chamadas == []
    assert rota.calls.last.request.headers["If-None-Match"] == 'W/"abc"'
