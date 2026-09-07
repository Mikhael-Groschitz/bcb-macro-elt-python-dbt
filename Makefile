.PHONY: setup test lint typecheck validar ingest dbt

setup:
	python3 -m pip show uv > /dev/null 2>&1 || python3 -m pip install uv
	python3 -m uv sync --extra dev

test:
	python3 -m uv run pytest

lint:
	python3 -m uv run ruff check .
	python3 -m uv run ruff format --check .

typecheck:
	python3 -m uv run mypy bcb_ingest

validar: lint typecheck test
	python3 -m uv run python -m bcb_ingest.cli ultimos --serie 1 --n 5

ingest:
	@echo "Fase 2 ainda não implementada: extração completa do SGS com janelamento e watermark."

dbt:
	@echo "Fase 4 ainda não implementada: projeto dbt."
