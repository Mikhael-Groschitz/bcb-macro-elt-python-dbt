"""Fixtures compartilhadas."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from bcb_ingest.client import ClienteBCB, ConfiguracaoCliente

BASE_URL_TESTE = "https://api.teste.bcb.gov.br"


class EspiaoDormir:
    def __init__(self) -> None:
        self.chamadas: list[float] = []

    def __call__(self, segundos: float) -> None:
        self.chamadas.append(segundos)


@pytest.fixture
def base_url_teste() -> str:
    return BASE_URL_TESTE


@pytest.fixture
def espiao_dormir() -> EspiaoDormir:
    return EspiaoDormir()


@pytest.fixture
def config_teste(base_url_teste: str) -> ConfiguracaoCliente:
    return ConfiguracaoCliente(
        base_url=base_url_teste,
        max_tentativas=3,
        backoff_base_segundos=0.01,
        backoff_teto_segundos=0.05,
    )


@pytest.fixture
def cliente_teste(
    config_teste: ConfiguracaoCliente, espiao_dormir: EspiaoDormir
) -> Iterator[ClienteBCB]:
    cliente = ClienteBCB(config_teste, dormir=espiao_dormir)
    yield cliente
    cliente.fechar()
