select
    e.indicador,
    e.ano_referencia,
    e.data_coleta,
    e.horizonte_dias,
    e.mediana as projecao,
    r.valor_realizado as realizado,
    r.valor_realizado - e.mediana as erro,
    abs(r.valor_realizado - e.mediana) as erro_absoluto,
    case
        when r.valor_realizado - e.mediana > 0 then 'subestimou'
        when r.valor_realizado - e.mediana < 0 then 'superestimou'
        else 'acertou'
    end as vies,
    e.chave_natural
from {{ ref('fct_expectativa') }} e
inner join {{ ref('int_sgs_realizado_anual') }} r
    on r.indicador_focus = e.indicador
    and r.ano = e.ano_referencia
where r.ano_completo
