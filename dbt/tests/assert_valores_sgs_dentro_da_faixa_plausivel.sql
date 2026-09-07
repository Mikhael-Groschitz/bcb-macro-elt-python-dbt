select *
from {{ ref('stg_sgs_observacao') }}
where
    (codigo_serie = 1 and (valor <= 0 or valor > 50))
    or (codigo_serie in (11, 12, 432) and (valor < 0 or valor > 100))
    or (codigo_serie = 433 and (valor < -5 or valor > 10))
    or (codigo_serie = 7326 and (valor < -15 or valor > 15))
