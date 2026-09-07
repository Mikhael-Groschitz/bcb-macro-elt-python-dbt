with snapshot as (
    select * from {{ ref('snp_sgs_observacao') }}
),

comparacao as (
    select a.chave_natural
    from snapshot a
    inner join snapshot b
        on a.chave_natural = b.chave_natural
        and a.dbt_scd_id <> b.dbt_scd_id
    where a.dbt_valid_from < coalesce(b.dbt_valid_to, timestamp '9999-12-31')
      and coalesce(a.dbt_valid_to, timestamp '9999-12-31') > b.dbt_valid_from
)

select * from comparacao
