-- Ver README, seção "Snapshot (SCD Tipo 2)".

select
    codigo_serie,
    data_observacao,
    valor,
    dbt_valid_from,
    dbt_valid_to
from snapshots.snp_sgs_observacao
where chave_natural = '1-2024-06-03'
order by dbt_valid_from;
