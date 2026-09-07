with sgs as (
    select * from {{ ref('stg_sgs_observacao') }}
),

de_para as (
    select * from {{ ref('de_para_indicador') }}
),

ipca_anual as (
    select
        codigo_serie,
        cast(extract(year from data_observacao) as integer) as ano,
        count(*) as meses_disponiveis,
        (exp(sum(ln(1 + valor / 100.0))) - 1) * 100 as valor_realizado
    from sgs
    where codigo_serie = 433
    group by codigo_serie, extract(year from data_observacao)
),

fim_de_ano as (
    select
        codigo_serie,
        cast(extract(year from data_observacao) as integer) as ano,
        valor as valor_realizado,
        extract(month from data_observacao) as mes_da_ultima_observacao,
        row_number() over (
            partition by codigo_serie, extract(year from data_observacao)
            order by data_observacao desc
        ) as rn
    from sgs
    where codigo_serie in (1, 432)
),

pib_anual as (
    select
        codigo_serie,
        cast(extract(year from data_observacao) as integer) as ano,
        valor as valor_realizado
    from sgs
    where codigo_serie = 7326
),

unificado as (
    select codigo_serie, ano, valor_realizado, meses_disponiveis = 12 as ano_completo
    from ipca_anual

    union all

    select codigo_serie, ano, valor_realizado, mes_da_ultima_observacao = 12 as ano_completo
    from fim_de_ano
    where rn = 1

    union all

    select codigo_serie, ano, valor_realizado, true as ano_completo
    from pib_anual
)

select
    dp.indicador_focus,
    u.codigo_serie,
    u.ano,
    u.valor_realizado,
    u.ano_completo
from unificado u
inner join de_para dp on dp.codigo_serie_sgs = u.codigo_serie
