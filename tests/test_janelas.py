"""Testes de bcb_ingest.janelas.particionar_janelas."""

from __future__ import annotations

from datetime import date

import pytest

from bcb_ingest.janelas import particionar_janelas


def test_intervalo_menor_que_dez_anos_produz_uma_janela() -> None:
    janelas = particionar_janelas(date(2023, 1, 1), date(2023, 12, 31))

    assert janelas == [(date(2023, 1, 1), date(2023, 12, 31))]


def test_dez_anos_exatos_produz_uma_janela() -> None:
    janelas = particionar_janelas(date(2015, 1, 1), date(2025, 1, 1))

    assert janelas == [(date(2015, 1, 1), date(2025, 1, 1))]


def test_dez_anos_e_um_dia_produz_duas_janelas() -> None:
    janelas = particionar_janelas(date(2015, 1, 1), date(2025, 1, 2))

    assert janelas == [
        (date(2015, 1, 1), date(2025, 1, 1)),
        (date(2025, 1, 2), date(2025, 1, 2)),
    ]


def test_dia_unico_produz_uma_janela_de_um_dia() -> None:
    janelas = particionar_janelas(date(2024, 6, 15), date(2024, 6, 15))

    assert janelas == [(date(2024, 6, 15), date(2024, 6, 15))]


def test_intervalo_longo_nao_alinhado_nao_tem_lacuna_nem_sobreposicao() -> None:
    inicio, fim = date(2010, 6, 15), date(2023, 3, 1)

    janelas = particionar_janelas(inicio, fim)

    assert janelas[0][0] == inicio
    assert janelas[-1][1] == fim
    for (_, fim_atual), (inicio_seguinte, _) in zip(janelas, janelas[1:], strict=False):
        assert (inicio_seguinte - fim_atual).days == 1


def test_ano_bissexto_29_fevereiro_cai_para_28_no_destino_nao_bissexto() -> None:
    janelas = particionar_janelas(date(2016, 2, 29), date(2026, 2, 28))

    assert janelas == [(date(2016, 2, 29), date(2026, 2, 28))]


def test_inicio_posterior_a_fim_levanta_erro() -> None:
    with pytest.raises(ValueError, match="posterior"):
        particionar_janelas(date(2024, 1, 1), date(2023, 1, 1))
