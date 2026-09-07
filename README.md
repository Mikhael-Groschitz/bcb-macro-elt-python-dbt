# Expectativa vs. Realizado — BCB (Python + dbt)

O Boletim Focus do Banco Central publica o que o mercado **projeta** para
IPCA, Selic, câmbio e PIB. O SGS publica o que **de fato aconteceu** com esses
mesmos indicadores. O produto final deste projeto é o cruzamento dos dois:
qual o erro histórico da projeção, e quanto ele diminui conforme a data de
referência se aproxima — respondido por um mart dbt alimentado por dados
ingeridos em Python direto das APIs do BCB.

Este é o quinto projeto de um portfólio que já cobre SQL Server, Azure,
Spark/Airflow e Kafka. O que ele precisa provar, e que os outros não provam:
Python como engenharia de verdade (pacote, tipagem, testes), consumo de API
como fonte de dados (paginação, contrato instável, estado incremental), e dbt
com snapshots (SCD Tipo 2) capturando revisão histórica de série temporal.

## Status do projeto

Estou construindo isto em cinco fases, validando cada uma de ponta a ponta
antes de passar para a próxima. Por enquanto:

- [x] **Fase 1 — Pacote e cliente HTTP**: cliente HTTP com retry, backoff e
  timeout explícito, contratos Pydantic do SGS e do Focus confirmados por
  chamada real às duas APIs, decodificadores dos dois formatos de erro,
  CLI de smoke test, 26 testes sem rede real
- [x] **Fase 2 — Extração do SGS**: janelamento de até 10 anos, watermark por
  série em `_controle.ingestao`, lookback de 90 dias para capturar revisão de
  dados já publicados, landing em JSON e upsert idempotente em
  `raw.sgs_observacao`, 21 testes novos
- [ ] **Fase 3 — Extração do Focus**: paginação `$top`/`$skip` com `$orderby`
  determinístico, carga incremental por data de coleta
- [ ] **Fase 4 — dbt**: staging, snapshot SCD2 sobre as revisões do SGS,
  marts de erro de projeção
- [ ] **Fase 5 — CI e apresentação**: GitHub Actions, CLI completa
  (`ingest`/`status`/`reset`), README final com o achado analítico

O achado final — o cruzamento entre projeção e realizado — e uma leitura
consolidada de trade-offs olhando o pipeline inteiro ficam para o fechamento,
depois de "Decisões e trade-offs", quando as cinco fases estiverem prontas.

## Arquitetura

```mermaid
flowchart TD
    A[APIs do BCB<br/>SGS + Focus/Olinda] -->|Python: bcb_ingest| B[landing/<br/>JSON bruto por requisição]
    B --> C[raw.* no DuckDB<br/>uma linha por observação]
    C -->|dbt| D[staging]
    D --> E[snapshots<br/>SCD Tipo 2]
    E --> F[intermediate]
    F --> G[marts<br/>fct_erro_projecao]
    G --> H[consultas/<br/>achado final]

    style A fill:#e8e8e8,stroke:#888
    style B fill:#fff3cd,stroke:#c9971f
    style C fill:#fff3cd,stroke:#c9971f
    style G fill:#d4edda,stroke:#2e7d32
```

Hoje a extração do SGS já grava landing e `raw.*` (caixas cinza e amarelas).
Faltam a extração completa do Focus e todo o dbt (caixas verdes).

## Versões fixadas

| Pacote | Faixa | Por quê |
|---|---|---|
| httpx | `>=0.28,<0.29` | cliente HTTP; API estável de `Client`/`Limits`/`Timeout` |
| pydantic | `>=2.13,<3` | v2, `extra="forbid"` e `field_validator` |
| structlog | `>=26.1,<27` | logging JSON com `contextvars` para bind de contexto entre camadas |
| pyarrow | `>=25,<26` | reservado para landing em Parquet — ainda não usado |
| duckdb | `>=1.5,<2` | `raw.sgs_observacao` e `_controle.ingestao` |
| pytest / respx / ruff / mypy | ver `pyproject.toml` | dev only |

Sem `pandas` — a ingestão usa `httpx` + `pydantic` + `pyarrow` + `duckdb`.

## Decisões e trade-offs

**Cliente síncrono (`httpx.Client`), não `asyncio`.** Isto é um pipeline de
ingestão em lote — um processo que roda, busca, grava e termina — não um
servidor com muitas conexões concorrentes de entrada. Testa mais simples com
`respx`, sem event loop. Paralelizar janelas de data no futuro resolve com
`concurrent.futures.ThreadPoolExecutor` sobre o mesmo cliente (`httpx.Client`
é thread-safe) em vez de reescrever tudo em `asyncio`.

**`client.py` nunca decodifica corpo de resposta, nem sucesso nem erro.**
Decide só por status code e exceção de transporte. É essa decisão que resolve
os dois formatos de erro completamente diferentes do BCB (ver "Peculiaridades
das APIs" abaixo) sem acoplar o cliente genérico a nenhum dos dois — quem
decodifica `{"error": ...}` (SGS) ou `/* {"codigo": ...} */` (Olinda) é o
módulo específico (`sgs.py`/`focus.py`), a partir do texto bruto carregado na
exceção `ErroRequisicaoInvalida`.

**Retry só em 429, 5xx e timeout — nunca em outro 4xx.** Um 4xx diferente de
429 é erro do chamador (URL errada, parâmetro inválido) e estoura na hora,
sem retentativa. Isso inclui o 406 de janela grande do SGS: repetir a mesma
requisição não muda nada, o problema é o parâmetro enviado.

**Backoff exponencial com jitter e respeito a `Retry-After`.** A espera entre
tentativas é `min(teto, base * 2^(tentativa-1))` mais um jitter aleatório de
até metade desse valor, para evitar que várias execuções simultâneas
sincronizem suas retentativas. Quando a resposta traz o header `Retry-After`
com um valor numérico, ele tem prioridade sobre o cálculo; um `Retry-After`
em formato de data (não numérico) é ignorado e cai de volta no cálculo
padrão.

**Requisição condicional para o SGS.** A API confirma suporte a `ETag`
(header presente na resposta) mas não a `Last-Modified`. `client.py` aceita
um `etag_anterior` opcional, envia `If-None-Match` e trata 304 como retorno
normal — sem erro, sem retry. O Focus/Olinda não devolve nenhum header de
cache condicional, então sua estratégia de incremental precisa ser watermark
próprio, não cache HTTP.

**`Decimal` para o valor do SGS, `float` para os agregados do Focus.** O SGS
manda `valor` como string (`"5.1816"`) — convertida direto para
`Decimal(string)` preserva exatamente a representação de origem, sem erro de
arredondamento binário, relevante para taxa/índice que alimenta contas
financeiras a jusante. O Focus manda `Media`/`Mediana` como número JSON nativo
— o serviço já perdeu qualquer precisão além de double IEEE-754 ao
serializar; promover a `Decimal` seria precisão falsa, e são agregados
estatísticos de pesquisa (média entre ~30-90 respondentes por observação).

**`extra="forbid"` em todos os contratos.** O objetivo é falhar alto e com
mensagem clara quando um campo mudar, nunca propagar dado malformado adiante.
Como cada recurso Focus tem seu próprio modelo Pydantic (não um contrato
genérico compartilhado no nível do item), isso é seguro por construção — os
esquemas realmente divergem entre `ExpectativasMercadoAnuais`,
`ExpectativasMercadoSelic` e `ExpectativaMercadoMensais`. Anual e Mensal usam
`DataReferencia` (formato `"aaaa"` e `"MM/aaaa"`, respectivamente); Selic não
tem `DataReferencia` — usa `Reuniao` (ex. `"R5/2028"`), porque a expectativa
de Selic é por reunião do Copom, não por data calendário.

**Nomenclatura dos campos Focus mantém o casing original da API**
(`Indicador`, `Media`, mas `numeroRespondentes`, `baseCalculo` minúsculos) em
vez de normalizar tudo para `snake_case` com `Field(alias=...)` em cada campo
— menos boilerplate, menos risco de erro de digitação no alias. Suprimido via
`ruff` (regra `N815`) só no arquivo de contratos.

**Datas em formatos diferentes por API.** SGS usa `dd/MM/aaaa` (exige parser
customizado); Focus usa ISO `aaaa-MM-dd` (Pydantic parseia nativo). É uma
inconsistência real entre as duas APIs do próprio BCB.

**Logging separado por responsabilidade.** `client.py` loga eventos de
transporte (tentativa, status, duração) via `structlog`; quem chama
(`sgs.py`) faz o bind do contexto de domínio (código da série, operação)
antes de invocar — as duas camadas se combinam na mesma linha de log sem
acoplamento. A configuração de logging só é aplicada pela CLI, nunca como
efeito colateral de importar o pacote. `httpx` também loga via `logging`
padrão do Python (`HTTP Request: GET ... "HTTP/1.1 200 OK"`); por isso todo
log — `structlog` e stdlib — vai para `stderr`, deixando `stdout` livre só
para a saída de dados da CLI (uma linha JSON por observação).

**CLI com `argparse`, não uma dependência externa.** Um único subcomando não
justifica o peso extra de `click`/`typer`.

**Janelamento de até 10 anos.** `particionar_janelas` divide qualquer
intervalo em pedaços de no máximo 10 anos, replicando exatamente o limite
confirmado do SGS (mesma data um ano múltiplo de 10 à frente ainda passa; um
dia a mais já quebra). Reaproveita o mesmo cálculo tanto na primeira carga
histórica quanto no lookback incremental, para não ter dois caminhos de código
fazendo a mesma coisa.

**Lookback de 90 dias em vez de só pegar o que é novo.** Toda carga
incremental reprocessa os últimos 90 dias, não só a partir da última
observação. Séries do SGS são revisadas depois de publicadas — um valor de
uma data passada muda — e é esse reprocessamento que dá ao snapshot dbt da
Fase 4 alguma coisa para capturar como SCD Tipo 2.

**Idempotência via upsert, não log append-only.** `raw.sgs_observacao` tem
chave primária `(codigo_serie, data_referencia)` e a carga faz
`INSERT ... ON CONFLICT DO UPDATE`. Rodar a mesma janela duas vezes não
duplica linha; se o valor mudou (revisão), a linha existente é atualizada em
vez de uma nova ser criada. Isso empurra a responsabilidade de guardar
histórico de revisão para o snapshot dbt (que compara execuções sucessivas),
em vez de `raw` virar um log crescente que a Fase 4 precisaria deduplicar.

**Hash por observação, não por janela.** `_hash_payload` é o SHA-256 do item
bruto individual (`{"data": ..., "valor": ...}`), não da resposta inteira da
janela — cada linha carrega a prova de exatamente qual JSON de origem gerou
aquele valor, o que importa mais que ter um hash único por arquivo de landing
(esse já existe como artefato auditável por si só).

**Timeout de leitura de 30s, não 15s.** O valor original da Fase 1 olhava só
para o endpoint `/ultimos/{n}` (payload minúsculo) e ficou apertado demais
para janelas históricas de 10 anos, que rotineiramente passam de 15s de
resposta — o retry cobre isso sem falha visível, mas quase dobra o tempo
total da carga. Com 30s de timeout, as mesmas janelas respondem de forma
consistente sem nenhuma retentativa (números em "Números" abaixo).

## Peculiaridades das APIs do BCB

- **O erro de janela grande do SGS é HTTP 406, não 400/422**, e o corpo é um
  objeto JSON (`{"error", "message", "syntax"}`), não uma lista como a
  resposta de sucesso. O limite de janela é `<=` 10 anos: uma janela de
  exatamente 10 anos passa (200), 10 anos e 1 dia já quebra (406).
- **O corpo de erro do Olinda não é JSON puro** — vem envelopado em
  comentário JS: `/*{"codigo": 400, "mensagem": "..."}*/`. Um
  `response.json()` direto falha nesse formato.
- **Nem todo campo do Focus aparece com `$select` restrito.** O recurso
  `ExpectativasMercadoAnuais` tem os campos `IndicadorDetalhe` (nullable) e
  `DesvioPadrao`, que só aparecem numa consulta sem `$select` — um contrato
  derivado de uma amostra reduzida fica incompleto e quebra com
  `extra="forbid"` na primeira resposta completa.
- **Sintaxe OData v2/v3 não funciona no Olinda** — `substringof(...)`
  devolve 400; a sintaxe correta é `contains(campo, 'valor')` (OData v4).
- O indicador de PIB no Focus é `"PIB Total"`, não `"PIB"` sozinho — existem
  variantes como `"PIB Agropecuária"`.
- **Uma janela de 10 anos do SGS pode levar bem mais que alguns segundos.**
  O tempo de resposta varia de ~5s a ~21s dependendo da janela, mesmo para
  payloads pequenos (menos de 100KB) — a latência parece dominada pelo lado
  do servidor, não pelo tamanho da resposta, então não dá para presumi-la
  baixa só porque o payload é pequeno.

## Persistência

**Landing**: `landing/sgs/serie={codigo}/janela={inicio}_{fim}.json`, com as
datas da janela em ISO (`aaaa-mm-dd`) — ordena como string e não tem
ambiguidade de formato, ao contrário do `dd/MM/aaaa` que a API usa na query.

**`raw.sgs_observacao`**: `codigo_serie`, `data_referencia` (DATE),
`valor` (DECIMAL(18,6) — mesma razão da Fase 1: nunca float para valor de
série), `_carregado_em`, `_execucao_id`, `_hash_payload`, com chave primária
`(codigo_serie, data_referencia)`.

**`_controle.ingestao`**: uma linha por série, com `data_ultima_observacao`,
o horizonte (`horizonte_inicio`/`horizonte_fim`) e a contagem de linhas da
última execução — é o que decide, na próxima carga, se busca desde `--desde`
(sem watermark ainda) ou desde `data_ultima_observacao - lookback_dias`.

## Números

47 testes automatizados, execução completa em cerca de 4,8s, sem chamada de
rede. Cobertura de `bcb_ingest`: 80% no total — `armazenamento.py`, `db.py`
e `estado.py` em 100%, `janelas.py` 100%, `client.py` 98%, `contratos.py`
97%, `focus.py` 100%, `sgs.py` 91%; `cli.py` e `logging_config.py` ficam em
0% porque são validados pelo smoke test manual (`make validar`), não por
teste de unidade.

O smoke test da CLI (`ultimos --serie 1 --n 5`) contra a API real do SGS
roda em cerca de 0,9s e devolve o mesmo resultado em execuções consecutivas.

**Carga histórica das três séries diárias**, `--desde 1995-01-01` até hoje
(2026-09-07), 4 janelas de 10 anos cada:

| Série | Linhas carregadas | Duração |
|---|---|---|
| 1 (dólar venda) | 7.952 | 166,0s (timeout de 15s: 1 retentativa) |
| 11 (Selic) | 7.952 | 168,0s (timeout de 15s: 3 retentativas) |
| 12 (CDI) | 7.952 | 125,8s (timeout de 30s: 0 retentativas) |

`bcb.duckdb`: 4,1MB. `landing/sgs/`: 1,1MB em 12 arquivos JSON (4 janelas ×
3 séries).

**Idempotência**: uma carga incremental imediata da série 1 (sem `--desde`,
watermark + lookback de 90 dias) busca 65 linhas do período recente em 1,1s;
a contagem total em `raw.sgs_observacao` para a série 1 permanece em 7.952
antes e depois, porque o upsert atualiza as linhas existentes em vez de
duplicá-las.

## Como rodar

```bash
# instalar o uv, se ainda não tiver
python -m pip install uv

# sincronizar o ambiente (cria .venv e instala deps + dev)
make setup            # equivalente: uv sync --extra dev

# testes, sem rede real
make test              # equivalente: uv run pytest -v

# lint e formatação
make lint               # equivalente: uv run ruff check . && uv run ruff format --check .

# tipagem estrita
make typecheck    # equivalente: uv run mypy bcb_ingest

# smoke test contra a API real do SGS — imprime 5 observações tipadas
uv run python -m bcb_ingest.cli ultimos --serie 1 --n 5

# carga histórica de uma série (primeira vez, precisa de --desde)
uv run python -m bcb_ingest.cli carregar --serie 1 --desde 1995-01-01
# equivalente: make ingest SERIE=1 DESDE=1995-01-01

# carga incremental (já existe watermark, --desde é ignorado)
uv run python -m bcb_ingest.cli carregar --serie 1
# equivalente: make ingest SERIE=1
```

Em ambientes sem GNU Make, use os comandos `uv run ...` equivalentes listados
acima.
