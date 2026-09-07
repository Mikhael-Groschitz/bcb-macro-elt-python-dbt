select
    indicador,
    indicador_detalhe,
    ano_referencia,
    data_coleta,
    base_calculo,
    media,
    mediana,
    desvio_padrao,
    numero_respondentes,
    make_date(ano_referencia, 12, 31) as data_referencia_fim_ano,
    date_diff('day', data_coleta, make_date(ano_referencia, 12, 31)) as horizonte_dias
from {{ ref('stg_focus_expectativa') }}
