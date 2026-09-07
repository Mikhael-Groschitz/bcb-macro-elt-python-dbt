"""Conexão DuckDB e bootstrap do schema."""

from __future__ import annotations

import duckdb


def conectar(caminho: str) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(caminho)
    _bootstrap(con)
    return con


def _bootstrap(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("CREATE SCHEMA IF NOT EXISTS _controle")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS raw.sgs_observacao (
            codigo_serie INTEGER NOT NULL,
            data_referencia DATE NOT NULL,
            valor DECIMAL(18,6) NOT NULL,
            _carregado_em TIMESTAMP NOT NULL,
            _execucao_id VARCHAR NOT NULL,
            _hash_payload VARCHAR NOT NULL,
            PRIMARY KEY (codigo_serie, data_referencia)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS _controle.ingestao (
            codigo_serie INTEGER PRIMARY KEY,
            data_ultima_observacao DATE,
            horizonte_inicio DATE NOT NULL,
            horizonte_fim DATE NOT NULL,
            contagem_linhas BIGINT NOT NULL,
            executado_em TIMESTAMP NOT NULL,
            execucao_id VARCHAR NOT NULL
        )
        """
    )
