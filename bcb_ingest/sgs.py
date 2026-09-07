"""Extração do SGS."""

from __future__ import annotations

import structlog
from pydantic import ValidationError

from bcb_ingest.client import ClienteBCB, ErroRequisicaoInvalida
from bcb_ingest.contratos import SgsErro, SgsObservacao

logger = structlog.get_logger(__name__)

BASE_URL = "https://api.bcb.gov.br"


class ErroSgs(Exception):
    """Erro de domínio do SGS."""


def buscar_ultimos(cliente: ClienteBCB, codigo_serie: int, n: int) -> list[SgsObservacao]:
    structlog.contextvars.bind_contextvars(codigo_serie=codigo_serie, operacao="ultimos", n=n)
    try:
        caminho = f"/dados/serie/bcdata.sgs.{codigo_serie}/dados/ultimos/{n}"
        try:
            resposta = cliente.requisitar("GET", caminho, params={"formato": "json"})
        except ErroRequisicaoInvalida as erro:
            raise ErroSgs(_decodificar_erro(erro)) from erro

        dados_brutos = resposta.json()
        try:
            return [SgsObservacao.model_validate(item) for item in dados_brutos]
        except ValidationError as erro:
            raise ErroSgs(f"resposta do SGS não bate com o contrato esperado: {erro}") from erro
    finally:
        structlog.contextvars.unbind_contextvars("codigo_serie", "operacao", "n")


def _decodificar_erro(erro: ErroRequisicaoInvalida) -> str:
    try:
        sgs_erro = SgsErro.model_validate_json(erro.corpo_bruto)
    except ValidationError:
        return f"SGS respondeu {erro.status_code}: {erro.corpo_bruto[:300]}"
    return f"SGS respondeu {erro.status_code}: {sgs_erro.error} - {sgs_erro.message}"
