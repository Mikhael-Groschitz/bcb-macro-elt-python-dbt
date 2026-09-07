select *
from {{ ref('fct_erro_projecao') }}
where realizado is null
