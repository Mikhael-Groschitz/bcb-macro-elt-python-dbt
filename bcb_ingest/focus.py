"""Extração do Focus/Olinda."""

from __future__ import annotations

import json
import re

BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata"

_PADRAO_ENVELOPE = re.compile(r"^\s*/\*(?P<corpo>.*)\*/\s*$", re.DOTALL)


class ErroFocus(Exception):
    """Erro de domínio do Focus."""


def decodificar_erro_olinda(corpo_bruto: str) -> str:
    casamento = _PADRAO_ENVELOPE.match(corpo_bruto)
    texto_json = casamento.group("corpo") if casamento else corpo_bruto
    try:
        dados = json.loads(texto_json)
        codigo = dados["codigo"]
        mensagem = dados["mensagem"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return f"Olinda respondeu com corpo não reconhecido: {corpo_bruto[:300]}"
    return f"Olinda respondeu {codigo}: {mensagem}"
