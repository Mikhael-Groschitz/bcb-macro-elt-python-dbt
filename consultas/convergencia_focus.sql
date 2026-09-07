-- Rodar com: uv run python -c "import duckdb; print(duckdb.connect('bcb.duckdb').sql(open('consultas/convergencia_focus.sql').read()))"

select *
from main_marts.mart_convergencia_focus
order by indicador, faixa_horizonte;
