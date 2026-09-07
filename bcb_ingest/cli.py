"""Interface de linha de comando do bcb_ingest."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

import structlog

from bcb_ingest.client import ClienteBCB, ConfiguracaoCliente, ErroClienteBcb
from bcb_ingest.logging_config import configurar_logging
from bcb_ingest.sgs import BASE_URL, ErroSgs, buscar_ultimos

logger = structlog.get_logger(__name__)


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


def main(argv: Sequence[str] | None = None) -> int:
    configurar_logging()
    parser = construir_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
