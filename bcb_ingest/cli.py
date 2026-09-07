"""Interface de linha de comando do bcb_ingest."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

import structlog

from bcb_ingest.client import ClienteBCB, ConfiguracaoCliente, ErroClienteBcb
from bcb_ingest.db import conectar
from bcb_ingest.logging_config import configurar_logging
from bcb_ingest.sgs import (
    BASE_URL,
    LOOKBACK_PADRAO_DIAS,
    ConfiguracaoCarga,
    ErroSgs,
    buscar_ultimos,
    carregar_historico,
)

logger = structlog.get_logger(__name__)


def _parse_data(valor: str) -> date:
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError as erro:
        raise argparse.ArgumentTypeError(f"data fora do formato aaaa-mm-dd: {valor!r}") from erro


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bcb_ingest", description=__doc__)
    subparsers = parser.add_subparsers(dest="comando", required=True)

    ultimos = subparsers.add_parser(
        "ultimos", help="busca os últimos N valores de uma série SGS (smoke test)"
    )
    ultimos.add_argument("--serie", type=int, required=True, help="código da série SGS")
    ultimos.add_argument(
        "--n", type=int, default=5, help="quantidade de valores (máx. 20, limite da API)"
    )
    ultimos.set_defaults(func=comando_ultimos)

    carregar = subparsers.add_parser(
        "carregar", help="carrega o histórico de uma série SGS em raw.sgs_observacao"
    )
    carregar.add_argument("--serie", type=int, required=True, help="código da série SGS")
    carregar.add_argument(
        "--desde",
        type=_parse_data,
        default=None,
        help="data inicial (aaaa-mm-dd), obrigatória só na primeira carga da série",
    )
    carregar.add_argument(
        "--lookback-dias",
        type=int,
        default=LOOKBACK_PADRAO_DIAS,
        help=f"dias reprocessados antes da última observação (padrão {LOOKBACK_PADRAO_DIAS})",
    )
    carregar.add_argument(
        "--db",
        default=os.environ.get("BCB_DUCKDB_PATH", "bcb.duckdb"),
        help="caminho do arquivo DuckDB (padrão: variável BCB_DUCKDB_PATH ou bcb.duckdb)",
    )
    carregar.add_argument(
        "--landing-dir",
        default=os.environ.get("BCB_LANDING_DIR", "landing"),
        help="diretório de landing (padrão: variável BCB_LANDING_DIR ou landing)",
    )
    carregar.set_defaults(func=comando_carregar)

    return parser


def comando_ultimos(args: argparse.Namespace) -> int:
    config = ConfiguracaoCliente(base_url=BASE_URL)
    try:
        with ClienteBCB(config) as cliente:
            observacoes = buscar_ultimos(cliente, codigo_serie=args.serie, n=args.n)
    except (ErroClienteBcb, ErroSgs) as erro:
        logger.error("falha_smoke_test", erro=str(erro))
        return 1

    for observacao in observacoes:
        print(observacao.model_dump_json())
    return 0


def comando_carregar(args: argparse.Namespace) -> int:
    config = ConfiguracaoCliente(base_url=BASE_URL)
    config_carga = ConfiguracaoCarga(desde=args.desde, lookback_dias=args.lookback_dias)
    con = conectar(args.db)
    try:
        with ClienteBCB(config) as cliente:
            resultado = carregar_historico(
                cliente,
                con,
                args.serie,
                Path(args.landing_dir),
                config_carga,
            )
    except (ErroClienteBcb, ErroSgs) as erro:
        logger.error("falha_carga_sgs", erro=str(erro))
        return 1
    finally:
        con.close()

    print(
        json.dumps(
            {
                "codigo_serie": resultado.codigo_serie,
                "linhas_carregadas": resultado.linhas_carregadas,
                "janelas": len(resultado.janelas),
                "duracao_segundos": round(resultado.duracao_segundos, 3),
                "data_ultima_observacao": (
                    resultado.data_ultima_observacao.isoformat()
                    if resultado.data_ultima_observacao
                    else None
                ),
            }
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    configurar_logging()
    parser = construir_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
