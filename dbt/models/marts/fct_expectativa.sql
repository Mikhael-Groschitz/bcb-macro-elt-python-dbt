select
    indicador,
    ano_referencia,
    data_coleta,
    horizonte_dias,
    media,
    mediana,
    numero_respondentes,
    indicador || '-' || ano_referencia || '-' || data_coleta as chave_natural
from {{ ref('int_focus_horizonte') }}
where base_calculo = 0
