with faixas as (
    select
        indicador,
        erro_absoluto,
        case
            when horizonte_dias <= 30 then '01 - até 30 dias'
            when horizonte_dias <= 90 then '02 - 31 a 90 dias'
            when horizonte_dias <= 180 then '03 - 91 a 180 dias'
            when horizonte_dias <= 365 then '04 - 181 a 365 dias'
            else '05 - mais de 365 dias'
        end as faixa_horizonte
    from {{ ref('fct_erro_projecao') }}
)

select
    indicador,
    faixa_horizonte,
    count(*) as quantidade_observacoes,
    median(erro_absoluto) as erro_absoluto_mediano
from faixas
group by indicador, faixa_horizonte
order by indicador, faixa_horizonte
