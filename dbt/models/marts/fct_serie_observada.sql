select
    codigo_serie,
    data_observacao,
    valor,
    chave_natural
from {{ ref('snp_sgs_observacao') }}
where dbt_valid_to is null
