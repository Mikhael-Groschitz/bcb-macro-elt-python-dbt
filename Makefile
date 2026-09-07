.PHONY: setup test lint typecheck validar ingest ingest-focus dbt dbt-docs

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

ingest:
	@test -n "$(SERIE)" || (echo "uso: make ingest SERIE=<codigo> [DESDE=aaaa-mm-dd]" && exit 1)
	python3 -m uv run python -m bcb_ingest.cli carregar --serie $(SERIE) $(if $(DESDE),--desde $(DESDE),)

ingest-focus:
	@test -n "$(INDICADOR)" || (echo "uso: make ingest-focus INDICADOR=<nome>" && exit 1)
	python3 -m uv run python -m bcb_ingest.cli carregar-focus --indicador "$(INDICADOR)"

dbt:
	python3 -m uv run dbt build --project-dir dbt --profiles-dir dbt

dbt-docs:
	python3 -m uv run dbt docs generate --project-dir dbt --profiles-dir dbt
	python3 -m uv run dbt docs serve --project-dir dbt --profiles-dir dbt
