"""Catálogo de séries SGS e indicadores Focus cobertos pela carga completa."""

from __future__ import annotations

from datetime import date

DATA_INICIO_PADRAO = date(1995, 1, 1)

SERIES_SGS: tuple[int, ...] = (1, 11, 12, 432, 433, 7326)
INDICADORES_FOCUS: tuple[str, ...] = ("IPCA", "Selic", "Câmbio", "PIB Total")
