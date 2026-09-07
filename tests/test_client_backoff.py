"""Testes do cálculo de backoff isolado do transporte HTTP."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from bcb_ingest.client import ClienteBCB, ConfiguracaoCliente


@pytest.fixture
def cliente_calculo() -> Iterator[ClienteBCB]:
    config = ConfiguracaoCliente(
        base_url="https://api.teste.bcb.gov.br",
        backoff_base_segundos=1.0,
        backoff_teto_segundos=4.0,
    )
    cliente = ClienteBCB(config, dormir=lambda _: None)
    yield cliente
    cliente.fechar()


def test_espera_cresce_exponencialmente(cliente_calculo: ClienteBCB, monkeypatch) -> None:
    monkeypatch.setattr("bcb_ingest.client.random.uniform", lambda a, b: 0.0)

    esperas = [cliente_calculo._calcular_espera(tentativa, None) for tentativa in (1, 2, 3)]

    assert esperas == [1.0, 2.0, 4.0]  # 1*2^0, 1*2^1, min(teto=4, 1*2^2)


def test_espera_respeita_teto(cliente_calculo: ClienteBCB, monkeypatch) -> None:
    monkeypatch.setattr("bcb_ingest.client.random.uniform", lambda a, b: 0.0)

    espera = cliente_calculo._calcular_espera(tentativa=10, retry_after=None)

    assert espera == 4.0


def test_espera_inclui_jitter(cliente_calculo: ClienteBCB, monkeypatch) -> None:
    monkeypatch.setattr("bcb_ingest.client.random.uniform", lambda a, b: 0.3)

    espera = cliente_calculo._calcular_espera(tentativa=1, retry_after=None)

    assert espera == pytest.approx(1.3)


def test_retry_after_numerico_sobrepoe_calculo(cliente_calculo: ClienteBCB, monkeypatch) -> None:
    def _uniform_nao_deveria_ser_chamado(a: float, b: float) -> float:
        raise AssertionError("não deveria calcular jitter quando Retry-After é numérico")

    monkeypatch.setattr("bcb_ingest.client.random.uniform", _uniform_nao_deveria_ser_chamado)

    espera = cliente_calculo._calcular_espera(tentativa=1, retry_after="7")

    assert espera == 7.0


def test_retry_after_invalido_cai_para_calculo_padrao(
    cliente_calculo: ClienteBCB, monkeypatch
) -> None:
    monkeypatch.setattr("bcb_ingest.client.random.uniform", lambda a, b: 0.0)

    espera = cliente_calculo._calcular_espera(tentativa=1, retry_after="quinta-feira")

    assert espera == 1.0
