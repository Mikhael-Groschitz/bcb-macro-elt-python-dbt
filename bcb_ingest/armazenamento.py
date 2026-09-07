"""Persistência da carga do SGS e do Focus: landing (JSON) e raw (DuckDB)."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa

from bcb_ingest.contratos import FocusExpectativaAnual, SgsObservacao


def gravar_landing(
    diretorio: Path,
    codigo_serie: int,
    inicio: date,
    fim: date,
    payload_bruto: list[dict[str, Any]],
) -> Path:
    destino = (
        diretorio
        / "sgs"
        / f"serie={codigo_serie}"
        / f"janela={inicio.isoformat()}_{fim.isoformat()}.json"
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(payload_bruto, ensure_ascii=False), encoding="utf-8")
    return destino


def hash_payload(item_bruto: dict[str, Any]) -> str:
    canonico = json.dumps(item_bruto, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def upsert_observacoes(
    con: duckdb.DuckDBPyConnection,
    *,
    codigo_serie: int,
    observacoes: list[SgsObservacao],
    payload_bruto: list[dict[str, Any]],
    execucao_id: str,
) -> int:
    if not observacoes:
        return 0
    agora = datetime.now()
    tabela = pa.table(
        {
            "codigo_serie": pa.array([codigo_serie] * len(observacoes), type=pa.int32()),
            "data_referencia": [obs.data for obs in observacoes],
            "valor": pa.array([obs.valor for obs in observacoes], type=pa.decimal128(18, 6)),
            "_carregado_em": [agora] * len(observacoes),
            "_execucao_id": [execucao_id] * len(observacoes),
            "_hash_payload": [hash_payload(bruto) for bruto in payload_bruto],
        }
    )
    con.register("_staging_sgs_observacao", tabela)
    try:
        con.execute(
            """
            INSERT INTO raw.sgs_observacao
            SELECT * FROM _staging_sgs_observacao
            ON CONFLICT (codigo_serie, data_referencia) DO UPDATE SET
                valor = excluded.valor,
                _carregado_em = excluded._carregado_em,
                _execucao_id = excluded._execucao_id,
                _hash_payload = excluded._hash_payload
            """
        )
    finally:
        con.unregister("_staging_sgs_observacao")
    return len(observacoes)


def gravar_landing_focus(
    diretorio: Path, indicador: str, skip: int, top: int, payload_bruto: list[dict[str, Any]]
) -> Path:
    destino = diretorio / "focus" / f"indicador={indicador}" / f"pagina={skip}_{top}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(payload_bruto, ensure_ascii=False), encoding="utf-8")
    return destino


def upsert_expectativas(
    con: duckdb.DuckDBPyConnection,
    *,
    itens: list[FocusExpectativaAnual],
    payload_bruto: list[dict[str, Any]],
    execucao_id: str,
) -> int:
    if not itens:
        return 0
    agora = datetime.now()
    tabela = pa.table(
        {
            "indicador": [item.Indicador for item in itens],
            "indicador_detalhe": [item.IndicadorDetalhe or "" for item in itens],
            "data_referencia": [item.DataReferencia for item in itens],
            "data_coleta": [item.Data for item in itens],
            "base_calculo": pa.array([item.baseCalculo for item in itens], type=pa.int32()),
            "media": pa.array([item.Media for item in itens], type=pa.float64()),
            "mediana": pa.array([item.Mediana for item in itens], type=pa.float64()),
            "desvio_padrao": pa.array([item.DesvioPadrao for item in itens], type=pa.float64()),
            "minimo": pa.array([item.Minimo for item in itens], type=pa.float64()),
            "maximo": pa.array([item.Maximo for item in itens], type=pa.float64()),
            "numero_respondentes": pa.array(
                [item.numeroRespondentes for item in itens], type=pa.int32()
            ),
            "_carregado_em": [agora] * len(itens),
            "_execucao_id": [execucao_id] * len(itens),
            "_hash_payload": [hash_payload(bruto) for bruto in payload_bruto],
        }
    )
    con.register("_staging_focus_expectativa", tabela)
    try:
        con.execute(
            """
            INSERT INTO raw.focus_expectativa
            SELECT * FROM _staging_focus_expectativa
            ON CONFLICT (indicador, indicador_detalhe, data_referencia, data_coleta, base_calculo)
            DO UPDATE SET
                media = excluded.media,
                mediana = excluded.mediana,
                desvio_padrao = excluded.desvio_padrao,
                minimo = excluded.minimo,
                maximo = excluded.maximo,
                numero_respondentes = excluded.numero_respondentes,
                _carregado_em = excluded._carregado_em,
                _execucao_id = excluded._execucao_id,
                _hash_payload = excluded._hash_payload
            """
        )
    finally:
        con.unregister("_staging_focus_expectativa")
    return len(itens)
