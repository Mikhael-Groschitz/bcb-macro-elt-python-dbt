"""Testes dos contratos Pydantic."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from bcb_ingest.contratos import (
    FocusExpectativaAnual,
    FocusExpectativaMensal,
    FocusExpectativaSelic,
    RespostaOlinda,
    SgsErro,
    SgsObservacao,
)

DIR_FIXTURES = Path(__file__).parent / "fixtures"


def _carregar(nome: str) -> Any:
    return json.loads((DIR_FIXTURES / nome).read_text(encoding="utf-8"))


def test_sgs_observacao_parseia_data_e_valor_decimal() -> None:
    dados = _carregar("sgs_sucesso.json")

    observacoes = [SgsObservacao.model_validate(item) for item in dados]

    assert observacoes[0].data.isoformat() == "2026-08-31"
    assert observacoes[0].valor == Decimal("5.1816")
    assert isinstance(observacoes[0].valor, Decimal)


def test_sgs_observacao_rejeita_campo_extra() -> None:
    with pytest.raises(ValidationError) as excinfo:
        SgsObservacao.model_validate({"data": "31/08/2026", "valor": "5.18", "campo_novo": "x"})

    assert "campo_novo" in str(excinfo.value)


def test_sgs_observacao_rejeita_valor_nao_decimal() -> None:
    with pytest.raises(ValidationError) as excinfo:
        SgsObservacao.model_validate({"data": "31/08/2026", "valor": "não-é-número"})

    erros = excinfo.value.errors()
    assert any(erro["loc"] == ("valor",) for erro in erros)


def test_sgs_observacao_rejeita_data_fora_do_formato() -> None:
    with pytest.raises(ValidationError) as excinfo:
        SgsObservacao.model_validate({"data": "2026-08-31", "valor": "5.18"})

    erros = excinfo.value.errors()
    assert any(erro["loc"] == ("data",) for erro in erros)


def test_sgs_erro_parseia_corpo_de_erro_real() -> None:
    dados = _carregar("sgs_erro_janela.json")

    erro = SgsErro.model_validate(dados)

    assert "10 anos" in erro.error


def test_focus_anual_parseia_envelope_real() -> None:
    dados = _carregar("focus_anual_envelope.json")

    resposta = RespostaOlinda[FocusExpectativaAnual].model_validate(dados)

    assert len(resposta.value) == 2
    assert resposta.value[0].Indicador == "IPCA"
    assert resposta.value[0].DataReferencia == "2026"
    assert resposta.value[0].IndicadorDetalhe is None


def test_focus_selic_usa_reuniao_em_vez_de_data_referencia() -> None:
    dados = _carregar("focus_selic_item.json")

    resposta = RespostaOlinda[FocusExpectativaSelic].model_validate(dados)

    assert resposta.value[0].Reuniao == "R5/2028"


def test_focus_mensal_data_referencia_no_formato_mes_ano() -> None:
    dados = _carregar("focus_mensal_item.json")

    resposta = RespostaOlinda[FocusExpectativaMensal].model_validate(dados)

    assert resposta.value[0].DataReferencia == "08/2028"


def test_focus_anual_rejeita_campo_inesperado() -> None:
    dados = _carregar("focus_anual_envelope.json")
    dados["value"][0]["CampoNovoNaoMapeado"] = "x"

    with pytest.raises(ValidationError) as excinfo:
        RespostaOlinda[FocusExpectativaAnual].model_validate(dados)

    assert "CampoNovoNaoMapeado" in str(excinfo.value)


def test_focus_selic_rejeita_data_referencia_no_lugar_de_reuniao() -> None:
    item_selic_com_campo_de_anual = {
        "Indicador": "Selic",
        "Data": "2026-08-28",
        "DataReferencia": "2026",
        "Media": 10.0,
        "Mediana": 10.0,
        "DesvioPadrao": 0.5,
        "Minimo": 9.0,
        "Maximo": 11.0,
        "numeroRespondentes": 10,
        "baseCalculo": 0,
    }

    with pytest.raises(ValidationError):
        FocusExpectativaSelic.model_validate(item_selic_com_campo_de_anual)
