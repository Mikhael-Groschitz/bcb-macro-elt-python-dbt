"""Particionamento de intervalos de data em janelas de no máximo 10 anos."""

from __future__ import annotations

from datetime import date, timedelta

MAX_ANOS_JANELA = 10


def particionar_janelas(
    inicio: date, fim: date, max_anos: int = MAX_ANOS_JANELA
) -> list[tuple[date, date]]:
    if inicio > fim:
        raise ValueError(f"data inicial ({inicio}) posterior à data final ({fim})")

    janelas: list[tuple[date, date]] = []
    inicio_janela = inicio
    while inicio_janela <= fim:
        fim_janela = min(fim, _adicionar_anos(inicio_janela, max_anos))
        janelas.append((inicio_janela, fim_janela))
        inicio_janela = fim_janela + timedelta(days=1)
    return janelas


def _adicionar_anos(data: date, anos: int) -> date:
    try:
        return data.replace(year=data.year + anos)
    except ValueError:
        return data.replace(month=2, day=28, year=data.year + anos)
