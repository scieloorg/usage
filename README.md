# SciELO Usage

[![CI](https://github.com/scieloorg/usage/actions/workflows/ci.yml/badge.svg)](https://github.com/scieloorg/usage/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Django](https://img.shields.io/badge/django-5.2-green)
![Wagtail](https://img.shields.io/badge/wagtail-7.3-teal)

Aplicação para catalogar e validar logs de acesso às coleções SciELO, calcular
métricas COUNTER R5.1 e disponibilizá-las no OpenSearch. Também reúne metadados
de documentos e fontes, além de relatórios operacionais dos logs.

## Componentes e fluxo

O Django/Wagtail administra coleções, diretórios de logs, metadados, jobs e
relatórios. PostgreSQL guarda esses registros; Redis é o broker das tarefas
Celery. O processamento segue estas etapas:

1. **Search:** encontra arquivos nos diretórios ativos de cada coleção e os
   registra no catálogo.
2. **Validation:** verifica o conteúdo e determina a data provável do acesso.
   Arquivos legíveis reprovados ficam `INV`; falhas de leitura ficam `ERR`.
3. **Parsing:** reúne os arquivos elegíveis por coleção e dia em um
   `DailyMetricJob`, calcula as métricas e grava um payload diário recuperável.
4. **Export:** atualiza os índices COUNTER mensais e analíticos anuais no
   OpenSearch. Repetições do mesmo dia são tratadas de forma idempotente.

Os coletores de ArticleMeta, OPAC, SciELO Books, Preprints e Dataverse
alimentam os modelos `Source` e `Document` no PostgreSQL. Uma tarefa separada
sincroniza esses metadados com os índices `usage_sources` e `usage_documents`.
Os índices de métricas usam os aliases `usage_monthly_<coleção>` e
`usage_yearly_analytics_<coleção>` (prefixo configurável). A estratégia física
de particionamento e o número de shards são definidos por coleção no admin.

## Desenvolvimento local

O projeto usa Docker Compose (`local.yml`), Python 3.11, Django 5.2 e Wagtail
7.3. Prepare as variáveis locais exigidas pelo Compose e ajuste o volume de logs
de `local.yml` para um diretório existente no seu computador. O Compose local
inicia Django, PostgreSQL, Redis e Mailhog; **OpenSearch é externo** e precisa
estar acessível para executar a exportação.

```bash
make build
make up
make django_migrate
make django_createsuperuser
```

Admin: http://localhost:8009/admin

| Serviço | Porta local |
|---|---:|
| Django/Wagtail | 8009 |
| PostgreSQL | 5439 |
| Redis | 6399 |
| Mailhog | 8029 |

Antes de processar logs, carregue as coleções e suas configurações pelo admin
ou pelas tarefas de seed. Confira os diretórios ativos, as permissões de
leitura, os recursos de robôs/GeoIP e os metadados necessários à coleção.
O seed contém diretórios para diferentes fontes; ajuste os caminhos para o
ambiente antes de iniciar o Search.

Para acionar uma execução específica, abra o shell:

```bash
make django_shell
```

```python
from log_manager.tasks import task_search_log_files

task_search_log_files.delay(
    collections=["scl"],
    from_date="2026-01-01",
    until_date="2026-01-01",
    trigger_validation=True,
    parse_queue_name="parse_xlarge",
)
```

`from_date`/`until_date` delimitam a busca; a data usada nas métricas vem da
validação do conteúdo. Para operar por etapas, execute Search sem
`trigger_validation` e agende Validation e Parsing separadamente. A task
`[Metadata] Sync OpenSearch metadata` atualiza os índices de fontes e
documentos após a coleta de metadados.

Para acompanhar a execução local:

```bash
make logs
```

## Comandos úteis

```bash
make help           # lista os alvos disponíveis
make app_version    # mostra VERSION
make ps             # mostra os contêineres
make django_shell   # abre o shell do Django
make django_migrate # aplica migrações
make test           # executa pytest
make lint           # executa flake8
make format_check   # confere Black e isort
```

Os alvos aceitam `compose=<arquivo>`; o padrão é `local.yml`. Não publique
arquivos de configuração de ambiente que contenham credenciais.

## Configuração das tarefas

As opções de parsing aceitam listas separadas por vírgulas:

| Variável | Padrão | Finalidade |
|---|---|---|
| `DEFAULT_PARSE_QUEUE` | `parse_small` | Fila usada quando nenhuma fila de parsing é informada. |
| `PARSING_METADATA_CACHE_COLLECTIONS` | Coleções definidas em `config/settings/base.py` | Habilita cache de metadados durante o parsing. |
| `PARSING_METADATA_CACHE_RELEASE_COLLECTIONS` | `scl` | Libera o cache ao concluir o job. |

Cada contêiner de worker inicia um processo Celery. O entrypoint aceita
`CELERY_WORKER_QUEUES`, `CELERY_WORKER_CONCURRENCY`,
`CELERY_WORKER_PREFETCH_MULTIPLIER`, `CELERY_WORKER_NAME` e
`CELERY_WORKER_LOG_LEVEL`. A fila `load` atende Search, Validation e coleta de
metadados; filas `parse_tiny`, `parse_small`, `parse_medium`, `parse_large` e
`parse_xlarge` atendem os jobs diários. A configuração da fila não substitui
o agrupamento dos arquivos por coleção e dia em um único `DailyMetricJob`.

Ao cadastrar uma tarefa periódica no `django-celery-beat`, `queue` determina
onde a própria task será executada. O argumento `parse_queue_name`, nas tasks
de Search/Validation, determina a fila dos jobs de parsing subsequentes. São
configurações diferentes. Mantenha tarefas periódicas desativadas durante
backfills que possam concorrer com a mesma coleção e data.

| Variável | Padrão | Uso |
|---|---:|---|
| `CELERY_DAILY_JOB_SOFT_TIME_LIMIT_SECONDS` | 79200 (22h) | Limite suave do job diário. |
| `CELERY_DAILY_JOB_TIME_LIMIT_SECONDS` | 86400 (24h) | Limite rígido do job diário. |
| `CELERY_REDIS_VISIBILITY_TIMEOUT_SECONDS` | 3600 (1h) | Prazo de reentrega de mensagens não confirmadas. |

Os dois limites do job precisam ser positivos e o suave deve ser menor que o
rígido. Para jobs longos em HML, configure o visibility timeout em 93600 (26h)
em **todos** os processos que compartilham o broker (Django, beat e workers).
Um prazo maior também atrasa a reentrega após perda abrupta de um worker.

## Rotina e verificação

As tarefas periódicas são registros do `django-celery-beat` configurados no
admin, não um cronograma fixo no repositório. Conforme a coleção, programe a
coleta de fontes/documentos, Search/Validation/Parsing, sincronização de
metadados com OpenSearch e atualização dos relatórios. Há tasks próprias para
retomar jobs de exportação e logs com parsing obsoleto; use-as após conferir
que não há workers ainda executando os mesmos jobs.

O catálogo distingue `CRE` (encontrado), `QUE` (validado), `PAR` (em parsing),
`PRO` (processado), `INV` (conteúdo inválido), `ERR` (erro) e `IGN` (ignorado
deliberadamente). O `DailyMetricJob` registra o andamento por coleção e data.
Os relatórios no admin resumem os estados dos logs.

Para importar métricas históricas de outro sistema, existe o comando
`import_legacy_matomo`, com validação prévia (`--preflight`) e execução
explícita (`--execute`). Essa importação é separada da rotina diária de logs.

Para executar os testes dentro do Compose:

```bash
docker compose -f local.yml run --rm django pytest
```

## Versão

A versão da aplicação fica em `VERSION`. Atualizar o arquivo não publica uma
imagem nem altera uma instalação existente.
