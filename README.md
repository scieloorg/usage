# SciELO Usage Metrics Pipeline

A modernized platform for processing and indexing SciELO usage logs into OpenSearch, adhering to COUNTER R5.1 standards.

## Quick Start (Dev Installation)

To build and run the application locally:

1. `make build compose=local.yml`
2. `make django_migrate`
3. `make django_createsuperuser`
4. `make up`

The application will be accessible at [http://localhost:8009/admin](http://localhost:8009/admin).

---

## Key Commands

All commands run inside Docker via the `local.yml` compose file unless noted.

```bash
make build                           # build images
make up                              # start all services (django, postgres, redis, celery worker+beat, mailhog)
make django_shell                    # Django shell via docker compose
make django_test                     # run full test suite (pytest)
make django_fast                     # tests with --failfast
make django_migrate                  # apply migrations
make django_makemigrations           # generate new migrations
make django_createsuperuser          # create Wagtail admin user
make logs                            # follow all service logs
make ps                              # list compose services
make django_bash                     # open a bash shell in the django container
make django_compilemessages          # compile translation files
```

**Run a single test file/path:**
```bash
docker compose -f local.yml run --rm django pytest path/to/test_file.py
```

## Architecture & Data Pipeline

### Apps

| App | Purpose |
|---|---|
| `log_manager` | Log file discovery, validation, and status tracking |
| `log_manager_config` | Collection-specific configuration (paths, emails, expected logs/day) |
| `metrics` | Daily metric jobs, OpenSearch export, COUNTER R5.1 aggregation |
| `document` | Unified metadata model for articles, books, chapters, datasets, and preprints |
| `source` | Journal, book, preprint server, and data repository metadata |
| `reports` | Weekly, monthly, and yearly log processing reports |
| `resources` | Robot user-agent patterns and GeoIP MMDB management |
| `tracker` | Discarded line tracking and error logging |
| `core` | Wagtail pages, users, shared utilities, and external API collectors |
| `collection` | SciELO collection management |

### Core Collectors (`core/collectors/`)

| Collector | Source |
|---|---|
| `articlemeta.py` | ArticleMeta REST/Thrift API |
| `opac.py` | SciELO OPAC endpoint |
| `preprints.py` | SciELO Preprints OAI-PMH |
| `dataverse.py` | SciELO Data (Dataverse) |
| `scielo_books.py` | SciELO Books CouchDB changes feed |

### Log Ingestion Pipeline

The ingestion is fully automated via the **`[Log Pipeline] Daily Routine (Auto)`** task. It follows a strictly ordered sequence using Celery Chords:

- **Search**: Scans configured directories for new `.log` or `.gz` files.
- **Validate**: Performs statistical sampling to ensure log integrity and detect the usage date.
- **Parse**: Extracts metrics using `scielo_usage_counter`, performs URL translation, and aggregates data.
- **Export**: Pushes results to OpenSearch using idempotent upsert scripts.

### Metadata Synchronization

Metadata is kept in sync with SciELO sources (ArticleMeta, OPAC, Books, etc.) via the **`[Metadata] Daily Sync Routine (Auto)`** task, which runs parallel workers to ensure documents and sources are always up to date.

## Supported Log Formats

| Format | Description |
|---|---|
| NCSA Extended | Standard Apache combined log format with optional domain prefix and IP list fields. |
| BunnyCDN | Pipe-delimited format with Unix timestamps (7 or 10 digits), country codes, and request IDs. |

## Environment Variables

Runtime configuration is loaded from `.envs/.local/` or `.envs/.production/` through the Compose files.

### Core Services

| Variable | Default | Description |
|---|---|---|
| `OPENSEARCH_URL` | `http://localhost:9200/` | OpenSearch cluster URL |
| `OPENSEARCH_INDEX_NAME` | `usage` | OpenSearch index prefix |
| `OPENSEARCH_BASIC_AUTH` | `admin:admin` | OpenSearch basic auth credentials |
| `OPENSEARCH_VERIFY_CERTS` | `False` | Verify SSL certificates for OpenSearch connections |
| `USE_LOCAL_SCIELO_LIBS` | `0` | Mount local `scielo_log_validator` and `scielo_usage_counter` repos for development |
| `DJANGO_SETTINGS_MODULE` | `config.settings.local` | Django settings module |
| `REDIS_URL` | — | Redis connection URL for Celery |

### Collector Endpoints

| Variable | Default | Description |
|---|---|---|
| `ARTICLEMETA_COLLECT_URL` | `http://articlemeta.scielo.org/api/v1/article/counter_dict` | ArticleMeta counter metadata endpoint |
| `ARTICLEMETA_MAX_RETRIES` | `5` | ArticleMeta retry attempts |
| `ARTICLEMETA_SLEEP_TIME` | `30` | Delay between ArticleMeta retries, in seconds |
| `OPAC_ENDPOINT` | `https://www.scielo.br/api/v1/counter_dict` | OPAC counter metadata endpoint |
| `OPAC_MAX_RETRIES` | `5` | OPAC retry attempts |
| `OPAC_SLEEP_TIME` | `30` | Delay between OPAC retries, in seconds |
| `OAI_PMH_PREPRINT_ENDPOINT` | `https://preprints.scielo.org/index.php/scielo/oai` | SciELO Preprints OAI-PMH endpoint |
| `OAI_METADATA_PREFIX` | `oai_dc` | OAI-PMH metadata prefix |
| `OAI_PMH_MAX_RETRIES` | `5` | OAI-PMH retry attempts |
| `DATAVERSE_ENDPOINT` | `https://data.scielo.org/api` | SciELO Data Dataverse API endpoint |
| `DATAVERSE_ROOT_COLLECTION` | `scielodata` | Dataverse root collection alias |
| `DATAVERSE_SLEEP_TIME` | `30` | Dataverse request timeout/retry delay, in seconds |
| `SCIELO_BOOKS_BASE_URL` | `http://localhost:5984` | SciELO Books CouchDB base URL |
| `SCIELO_BOOKS_DB_NAME` | `scielobooks_1a` | SciELO Books CouchDB database name |
| `SCIELO_BOOKS_TIMEOUT` | `60` | SciELO Books request timeout, in seconds |
| `SCIELO_BOOKS_LIMIT` | `1000` | SciELO Books changes-feed page size |

## OpenSearch Storage Strategy

The OpenSearch export keeps monthly usage documents with nested daily metrics, while index names depend on collection size:

- **Large and xlarge collections**: annual indices, such as `usage_monthly_scl_2024` and `usage_yearly_scl_2024`.
- **Small collections**: stable collection indices, such as `usage_monthly_books` and `usage_yearly_books`.
- **One Document per Month**: Each document/PID has one monthly document per metric scope.
- **Daily Nested Metrics**: Daily granularity is preserved inside each monthly document using a `daily_metrics` object.
- **Atomic Upserts**: Data is merged using OpenSearch **Painless Scripts**, allowing multiple logs for the same day/month to be processed without data duplication or loss.

## Management & Monitoring

All pipelines can be monitored through the **Wagtail Admin**:

- **Log Manager**: Monitor the status of individual log files (`QUEUED`, `PARSING`, `PROCESSED`).
- **Daily Metric Jobs**: Track the history of daily processing and OpenSearch export attempts.
- **Log Config**: Manage collection-specific settings, log paths, and notification emails.

Internally, log file statuses are stored as short codes such as `QUE`, `PAR`, and `PRO`, with labels displayed in the admin.

### Useful Commands

- `make django_shell`: Access the Django interactive shell.
- `make django_bash`: Open a bash shell in the Django container.
- `make logs`: Follow Docker Compose logs.
- `make ps`: Show running services.
- `docker compose -f local.yml run --rm django pytest path/to/test_file.py`: Run a single test file or path.
- `docker logs -f scielo_usage_local_celeryworker`: Monitor real-time task execution.

## Dependencies

- [scielo_log_validator](https://github.com/scieloorg/scielo_log_validator) — log file validation
- [scielo_usage_counter](https://github.com/scieloorg/scielo_usage_counter) — COUNTER R5.1 metrics extraction
- [device_detector](https://github.com/thinkwelltwd/device_detector) — client name/version detection
- [opensearch-py](https://github.com/opensearch-project/opensearch-py) — OpenSearch client
