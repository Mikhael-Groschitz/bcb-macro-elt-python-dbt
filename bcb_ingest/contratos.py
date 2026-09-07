"""Modelos Pydantic dos formatos de resposta do SGS e do Focus."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SgsObservacao(BaseModel):
    """Observação da série temporal do SGS."""

    model_config = ConfigDict(extra="forbid")

    data: date
    valor: Decimal

    @field_validator("data", mode="before")
    @classmethod
    def _parse_data_brasileira(cls, valor: object) -> object:
        if isinstance(valor, str):
            try:
                return datetime.strptime(valor, "%d/%m/%Y").date()
            except ValueError as erro:
                raise ValueError(f"data do SGS fora do formato dd/MM/aaaa: {valor!r}") from erro
        return valor

    @field_validator("valor", mode="before")
    @classmethod
    def _parse_valor_decimal(cls, valor: object) -> object:
        if isinstance(valor, str):
            try:
                return Decimal(valor)
            except InvalidOperation as erro:
                raise ValueError(f"valor do SGS não é decimal válido: {valor!r}") from erro
        return valor


class SgsErro(BaseModel):
    """Corpo de erro do SGS."""

    model_config = ConfigDict(extra="forbid")

    error: str
    message: str
    syntax: str


class RespostaOlinda[T: BaseModel](BaseModel):
    """Envelope OData comum aos recursos do Focus."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    odata_context: str = Field(alias="@odata.context")
    value: list[T]


class FocusExpectativaAnual(BaseModel):
    """Item de ExpectativasMercadoAnuais."""

    model_config = ConfigDict(extra="forbid")

    Indicador: str
    IndicadorDetalhe: str | None
    Data: date
    DataReferencia: str
    Media: float
    Mediana: float
    DesvioPadrao: float
    Minimo: float
    Maximo: float
    numeroRespondentes: int
    baseCalculo: int


class FocusExpectativaSelic(BaseModel):
    """Item de ExpectativasMercadoSelic."""

    model_config = ConfigDict(extra="forbid")

    Indicador: str
    Data: date
    Reuniao: str
    Media: float
    Mediana: float
    DesvioPadrao: float
    Minimo: float
    Maximo: float
    numeroRespondentes: int
    baseCalculo: int


class FocusExpectativaMensal(BaseModel):
    """Item de ExpectativaMercadoMensais."""

    model_config = ConfigDict(extra="forbid")

    Indicador: str
    Data: date
    DataReferencia: str
    Media: float
    Mediana: float
    DesvioPadrao: float
    Minimo: float
    Maximo: float
    numeroRespondentes: int
    baseCalculo: int
