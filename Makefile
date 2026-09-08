.PHONY: setup test lint typecheck validar carregar carregar-focus ingest status reset \
	bootstrap-db dbt dbt-docs ci

setup:
	python3 -m pip show uv > /dev/null 2>&1 || python3 -m pip install uv
	python3 -m uv sync --extra dev --extra dbt

test:
	python3 -m uv run pytest

lint:
	python3 -m uv run ruff check .
	python3 -m uv run ruff format --check .

typecheck:
	python3 -m uv run mypy bcb_ingest

validar: lint typecheck test
	python3 -m uv run python -m bcb_ingest.cli ultimos --serie 1 --n 5

carregar:
	@test -n "$(SERIE)" || (echo "uso: make carregar SERIE=<codigo> [DESDE=aaaa-mm-dd]" && exit 1)
	python3 -m uv run python -m bcb_ingest.cli carregar --serie $(SERIE) $(if $(DESDE),--desde $(DESDE),)

carregar-focus:
	@test -n "$(INDICADOR)" || (echo "uso: make carregar-focus INDICADOR=<nome>" && exit 1)
	python3 -m uv run python -m bcb_ingest.cli carregar-focus --indicador "$(INDICADOR)"

ingest:
	python3 -m uv run python -m bcb_ingest.cli ingest

status:
	python3 -m uv run python -m bcb_ingest.cli status

reset:
	@test "$(CONFIRMAR)" = "1" || (echo "uso: make reset CONFIRMAR=1" && exit 1)
	python3 -m uv run python -m bcb_ingest.cli reset --confirmar

bootstrap-db:
	python3 -m uv run python -c "import os; from bcb_ingest.db import conectar; conectar(os.environ.get('BCB_DUCKDB_PATH', 'bcb.duckdb')).close()"

dbt:
	python3 -m uv run dbt build --project-dir dbt --profiles-dir dbt

dbt-docs:
	python3 -m uv run dbt docs generate --project-dir dbt --profiles-dir dbt
	python3 -m uv run dbt docs serve --project-dir dbt --profiles-dir dbt

ci: lint typecheck test bootstrap-db dbt
