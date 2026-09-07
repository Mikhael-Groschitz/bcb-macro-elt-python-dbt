with fonte as (
    select * from {{ source('raw', 'sgs_observacao') }}
),

deduplicado as (
    select
        codigo_serie,
        data_referencia as data_observacao,
        valor,
        _carregado_em,
        row_number() over (
            partition by codigo_serie, data_referencia
            order by _carregado_em desc
        ) as rn
    from fonte
)

select
    codigo_serie,
    data_observacao,
    valor,
    codigo_serie || '-' || data_observacao as chave_natural,
    _carregado_em
from deduplicado
where rn = 1
