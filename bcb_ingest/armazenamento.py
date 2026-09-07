"""Persistência da carga do SGS: landing (JSON) e raw (DuckDB)."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb

from bcb_ingest.contratos import SgsObservacao


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
    agora = datetime.now()
    linhas = [
        (codigo_serie, obs.data, obs.valor, agora, execucao_id, hash_payload(bruto))
        for obs, bruto in zip(observacoes, payload_bruto, strict=True)
    ]
    con.executemany(
        """
        INSERT INTO raw.sgs_observacao
            (codigo_serie, data_referencia, valor, _carregado_em, _execucao_id, _hash_payload)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (codigo_serie, data_referencia) DO UPDATE SET
            valor = excluded.valor,
            _carregado_em = excluded._carregado_em,
            _execucao_id = excluded._execucao_id,
            _hash_payload = excluded._hash_payload
        """,
        linhas,
    )
    return len(linhas)
