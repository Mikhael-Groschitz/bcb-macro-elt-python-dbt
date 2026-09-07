{% snapshot snp_sgs_observacao %}

{{
    config(
        target_schema='snapshots',
        unique_key='chave_natural',
        strategy='check',
        check_cols=['valor'],
    )
}}

select
    codigo_serie,
    data_observacao,
    valor,
    chave_natural
from {{ ref('stg_sgs_observacao') }}

{% endsnapshot %}
