"""Configuração de logging estruturado em JSON."""

from __future__ import annotations

import logging
import sys

import structlog


def configurar_logging(nivel: int = logging.INFO) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=nivel)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(nivel),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
