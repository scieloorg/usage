# SciELO Usage

[![CI](https://github.com/scieloorg/usage/actions/workflows/ci.yml/badge.svg)](https://github.com/scieloorg/usage/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Django](https://img.shields.io/badge/django-5.2-green)
![Wagtail](https://img.shields.io/badge/wagtail-7.3-teal)

Application for processing SciELO access logs, extracting COUNTER R5.1 metrics, and exporting monthly/yearly usage documents to OpenSearch.

## Quick Start

Local development runs with Docker Compose using `local.yml`.

```bash
make build
make django_migrate
make django_createsuperuser
make up
```

Admin: http://localhost:8009/admin

Main local services:

| Service | Port |
|---|---:|
| Django/Wagtail | 8009 |
| PostgreSQL | 5439 |
| Redis | 6399 |
| Mailhog | 8029 |

## Full Pipeline Setup

After the app is running, open a Django shell:

```bash
make django_shell
```

Seed the base data and resources:

```python
from collection.tasks import task_load_collections
from log_manager_config.tasks import task_load_log_manager_collection_settings
from resources.tasks import task_load_geoip, task_load_robots

log_config = [
    {
        "acronym": "scl",
        "directory_name": "SciELO Brasil",
        "path": "/app/logs/scielo.br",
        "quantity": 1,
        "e-mail": "tecnologia@scielo.org",
        "translator_class": "opac",
    }
]

task_load_collections.delay()
task_load_log_manager_collection_settings.delay(data=log_config)
task_load_robots.delay()
task_load_geoip.delay()
```

Load sources and documents before processing logs. For a first run, restrict document synchronization to a smaller date range:

```python
from document.tasks import (
    task_load_dataset_metadata_into_documents,
    task_load_documents_from_article_meta,
    task_load_documents_from_opac,
    task_load_preprints_into_documents,
    task_sync_documents_from_scielo_books,
)
from source.tasks import (
    task_load_sources_from_article_meta,
    task_load_sources_from_scielo_books,
)

task_load_sources_from_article_meta.delay(collections=["scl"])
task_load_sources_from_scielo_books.delay(limit=1000)

date_range = {"from_date": "2025-01-01", "until_date": "2025-12-31"}
task_load_documents_from_article_meta.delay(**date_range)
task_load_documents_from_opac.delay(collection="scl", **date_range)
task_load_preprints_into_documents.delay(**date_range)
task_load_dataset_metadata_into_documents.delay(**date_range)
task_sync_documents_from_scielo_books.delay()
```

Before starting the log pipeline, confirm in the admin that each collection has an active Log Manager configuration pointing to a readable log directory mounted in the container.

For the example above, place a log file under the configured directory:

```bash
mkdir -p <mounted-logs-dir>/scielo.br
cp metrics/tests/fixtures/usage.log <mounted-logs-dir>/scielo.br/usage-2021-05-21.log
```

Run the full Search -> Validate -> Parse -> Export chain for a date range:

```python
from log_manager.tasks import task_search_log_files

task_search_log_files.delay(
    collections=["scl"],
    from_date="2021-05-21",
    until_date="2021-05-21",
    trigger_validation=True,
)
```

Monitor execution with:

```bash
make logs
```

## Commands

```bash
make help                    # list available targets
make app_version             # show VERSION
make build                   # build local images
make build_no_cache          # build local images without cache
make up                      # start local services
make logs                    # follow service logs
make stop                    # stop local services
make restart                 # restart local services
make ps                      # list running services
make django_bash             # open bash in the django container
make django_shell            # open Django shell
make django_createsuperuser  # create an admin user
make django_migrate          # apply migrations
make django_makemigrations   # create migrations
make django_makemessages     # update translation messages
make django_compilemessages  # compile translation messages
make wagtail_update_translation_field
make wagtail_sync
make test                    # run pytest
make django_test             # run pytest
make django_fast             # run pytest --failfast
make lint                    # run flake8
make format_check            # run black/isort checks
make precommit               # run pre-commit hooks
```

Use `compose=production.yml` or another Compose file when needed:

```bash
make ps compose=production.yml
```

Run one test path:

```bash
docker compose -f local.yml run --rm django pytest metrics/tests/test_opensearch.py
```

## Pipeline

The log pipeline is coordinated by Celery tasks:

1. Search configured directories for new `.log` and `.gz` files.
2. Validate log samples and detect usage date.
3. Parse requests with `scielo_usage_counter`.
4. Aggregate COUNTER R5.1 metrics.
5. Export idempotent monthly/yearly documents to OpenSearch.

Metadata synchronization keeps sources and documents updated from ArticleMeta, OPAC, SciELO Books, SciELO Preprints, and SciELO Data.

## Periodic Tasks

Configure the default schedule manually in Wagtail/Admin through `django-celery-beat`
`PeriodicTask` records. Exact cron times may vary by installation, but the default
operational setup should include:

| Task | Suggested schedule | Notes |
|---|---|---|
| `[Metadata] Daily Sync Routine (Auto)` | Daily, early morning | Refreshes sources and documents before log processing. Use the `load` queue. |
| `[Log Pipeline] Daily Routine (Auto)` | Daily, after metadata sync | Runs Search -> Validate -> Parse -> Export for new logs. Use the `load` queue. |
| `[Metrics] Resume Log Exports` | Every 15-30 minutes | Retries errored or stale daily metric export jobs. |
| `[Metrics] Resume Stale Parsing Logs` | Every 30-60 minutes | Marks stale `PAR` logs for retry. |
| `[Metrics] Cleanup Daily Payloads` | Daily or weekly | Removes old exported daily payload files. |
| `[Reports] Populate All Reports` | Daily, after log processing | Refreshes weekly, monthly, and yearly log report tables. |

Optional operational tasks:

| Task | Suggested schedule | Notes |
|---|---|---|
| `[Reports] Generate Log Report Summary (Manual)` | Manual or scheduled as needed | Sends summary emails using configured collection contacts. |
| `[Resources] Load Robots Data` | Weekly | Refreshes robots list used during parsing. |
| `[Resources] Load Geolocation Data` | Monthly | Refreshes GeoIP data used during parsing. |

## Version

Project release version is stored in `VERSION`.
