with fonte as (
    select * from {{ source('raw', 'focus_expectativa') }}
),

deduplicado as (
    select
        indicador,
        indicador_detalhe,
        data_referencia as periodo_referencia,
        data_coleta,
        base_calculo,
        media,
        mediana,
        desvio_padrao,
        minimo,
        maximo,
        numero_respondentes,
        _carregado_em,
        row_number() over (
            partition by
                indicador, indicador_detalhe, data_referencia, data_coleta, base_calculo
            order by _carregado_em desc
        ) as rn
    from fonte
)

select
    indicador,
    indicador_detalhe,
    periodo_referencia,
    cast(periodo_referencia as integer) as ano_referencia,
    data_coleta,
    base_calculo,
    media,
    mediana,
    desvio_padrao,
    minimo,
    maximo,
    numero_respondentes,
    indicador || '-' || coalesce(indicador_detalhe, '') || '-' || periodo_referencia
        || '-' || data_coleta || '-' || base_calculo as chave_natural,
    _carregado_em
from deduplicado
where rn = 1
