"""Testes de bcb_ingest.armazenamento."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from bcb_ingest.armazenamento import (
    gravar_landing,
    gravar_landing_focus,
    hash_payload,
    upsert_expectativas,
    upsert_observacoes,
)
from bcb_ingest.contratos import FocusExpectativaAnual, SgsObservacao
from bcb_ingest.db import conectar


@pytest.fixture
def con() -> Iterator[duckdb.DuckDBPyConnection]:
    conexao = conectar(":memory:")
    yield conexao
    conexao.close()


def test_gravar_landing_cria_arquivo_no_caminho_esperado(tmp_path: Path) -> None:
    payload = [{"data": "01/01/2024", "valor": "5.00"}]

    destino = gravar_landing(tmp_path, 1, date(2024, 1, 1), date(2024, 1, 31), payload)

    assert destino == tmp_path / "sgs" / "serie=1" / "janela=2024-01-01_2024-01-31.json"
    assert json.loads(destino.read_text(encoding="utf-8")) == payload


def test_hash_payload_e_deterministico_e_muda_com_o_valor() -> None:
    item = {"data": "01/01/2024", "valor": "5.00"}

    assert hash_payload(item) == hash_payload({"data": "01/01/2024", "valor": "5.00"})
    assert hash_payload(item) != hash_payload({"data": "01/01/2024", "valor": "5.01"})


def test_upsert_observacoes_insere_linhas(con: duckdb.DuckDBPyConnection) -> None:
    payload = [{"data": "01/01/2024", "valor": "5.00"}, {"data": "02/01/2024", "valor": "5.05"}]
    observacoes = [SgsObservacao.model_validate(item) for item in payload]

    linhas = upsert_observacoes(
        con, codigo_serie=1, observacoes=observacoes, payload_bruto=payload, execucao_id="exec-1"
    )

    total = con.execute("SELECT COUNT(*) FROM raw.sgs_observacao").fetchone()
    assert linhas == 2
    assert total is not None
    assert total[0] == 2


def test_upsert_observacoes_repetido_nao_duplica(con: duckdb.DuckDBPyConnection) -> None:
    payload = [{"data": "01/01/2024", "valor": "5.00"}]
    observacoes = [SgsObservacao.model_validate(item) for item in payload]

    for execucao in ("exec-1", "exec-2"):
        upsert_observacoes(
            con,
            codigo_serie=1,
            observacoes=observacoes,
            payload_bruto=payload,
            execucao_id=execucao,
        )

    total = con.execute("SELECT COUNT(*) FROM raw.sgs_observacao").fetchone()
    assert total is not None
    assert total[0] == 1


def test_upsert_observacoes_com_valor_revisado_atualiza_em_vez_de_duplicar(
    con: duckdb.DuckDBPyConnection,
) -> None:
    original = [{"data": "01/01/2024", "valor": "5.00"}]
    revisado = [{"data": "01/01/2024", "valor": "5.10"}]

    upsert_observacoes(
        con,
        codigo_serie=1,
        observacoes=[SgsObservacao.model_validate(item) for item in original],
        payload_bruto=original,
        execucao_id="exec-1",
    )
    upsert_observacoes(
        con,
        codigo_serie=1,
        observacoes=[SgsObservacao.model_validate(item) for item in revisado],
        payload_bruto=revisado,
        execucao_id="exec-2",
    )

    linha = con.execute(
        "SELECT valor, _execucao_id FROM raw.sgs_observacao WHERE codigo_serie = 1"
    ).fetchall()

    assert len(linha) == 1
    assert linha[0][0] == Decimal("5.100000")
    assert linha[0][1] == "exec-2"


def _item_focus(**overrides: object) -> dict[str, object]:
    base = {
        "Indicador": "IPCA",
        "IndicadorDetalhe": None,
        "Data": "2026-08-21",
        "DataReferencia": "2026",
        "Media": 5.0122,
        "Mediana": 5.0164,
        "DesvioPadrao": 0.2139,
        "Minimo": 4.3,
        "Maximo": 5.8146,
        "numeroRespondentes": 148,
        "baseCalculo": 0,
    }
    base.update(overrides)
    return base


def test_gravar_landing_focus_cria_arquivo_no_caminho_esperado(tmp_path: Path) -> None:
    payload = [_item_focus()]

    destino = gravar_landing_focus(tmp_path, "IPCA", 0, 1000, payload)

    assert destino == tmp_path / "focus" / "indicador=IPCA" / "pagina=0_1000.json"
    assert json.loads(destino.read_text(encoding="utf-8")) == payload


def test_upsert_expectativas_insere_linhas(con: duckdb.DuckDBPyConnection) -> None:
    payload = [_item_focus(), _item_focus(DataReferencia="2027")]
    itens = [FocusExpectativaAnual.model_validate(item) for item in payload]

    linhas = upsert_expectativas(con, itens=itens, payload_bruto=payload, execucao_id="exec-1")

    total = con.execute("SELECT COUNT(*) FROM raw.focus_expectativa").fetchone()
    assert linhas == 2
    assert total is not None
    assert total[0] == 2


def test_upsert_expectativas_repetido_nao_duplica(con: duckdb.DuckDBPyConnection) -> None:
    payload = [_item_focus()]
    itens = [FocusExpectativaAnual.model_validate(item) for item in payload]

    for execucao in ("exec-1", "exec-2"):
        upsert_expectativas(con, itens=itens, payload_bruto=payload, execucao_id=execucao)

    total = con.execute("SELECT COUNT(*) FROM raw.focus_expectativa").fetchone()
    assert total is not None
    assert total[0] == 1


def test_upsert_expectativas_com_media_revisada_atualiza_em_vez_de_duplicar(
    con: duckdb.DuckDBPyConnection,
) -> None:
    original = [_item_focus(Media=5.0122)]
    revisado = [_item_focus(Media=5.05)]

    upsert_expectativas(
        con,
        itens=[FocusExpectativaAnual.model_validate(item) for item in original],
        payload_bruto=original,
        execucao_id="exec-1",
    )
    upsert_expectativas(
        con,
        itens=[FocusExpectativaAnual.model_validate(item) for item in revisado],
        payload_bruto=revisado,
        execucao_id="exec-2",
    )

    linha = con.execute(
        "SELECT media, _execucao_id FROM raw.focus_expectativa WHERE indicador = 'IPCA'"
    ).fetchall()

    assert len(linha) == 1
    assert linha[0][0] == pytest.approx(5.05)
    assert linha[0][1] == "exec-2"


def test_upsert_expectativas_base_calculo_diferente_nao_colide(
    con: duckdb.DuckDBPyConnection,
) -> None:
    payload = [_item_focus(baseCalculo=0), _item_focus(baseCalculo=1)]
    itens = [FocusExpectativaAnual.model_validate(item) for item in payload]

    upsert_expectativas(con, itens=itens, payload_bruto=payload, execucao_id="exec-1")

    total = con.execute("SELECT COUNT(*) FROM raw.focus_expectativa").fetchone()
    assert total is not None
    assert total[0] == 2
