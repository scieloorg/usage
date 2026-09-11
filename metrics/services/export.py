import logging
from itertools import chain
from time import monotonic

from django.conf import settings

from log_manager_config.choices import OpenSearchPartitionStrategy
from metrics.opensearch.mappings import get_index_mappings
from metrics.opensearch.names import (
    generate_analytics_index_name,
    generate_month_index_name,
)
from metrics.services import daily_payloads, memory


def daily_metric_payload_exists(job):
    if not job.storage_path:
        return False
    if not daily_payloads.resolve_storage_path(job.storage_path).is_file():
        logging.warning("Daily metric payload not found for job %s.", job.pk)
        return False
    return True


def export_daily_metric_payload(search_client, job):
    if not job.job_id:
        raise RuntimeError("Daily metric job has no payload hash.")
    if not daily_metric_payload_exists(job):
        raise RuntimeError(f"Daily metric payload not found for job {job.pk}.")

    for dataset in ("counter", "analytics"):
        started = monotonic()
        exported = _sync_documents_group(
            search_client=search_client,
            collection=job.collection,
            access_date=job.access_date,
            document_items=daily_payloads.iter_document_items(
                job.storage_path,
                dataset,
            ),
            dataset=dataset,
            access_day=job.access_date.isoformat(),
        )
        logging.info(
            "Daily metric job %s %s OpenSearch export completed in %.3f "
            "seconds; %s documents; %s.",
            job.pk,
            dataset,
            monotonic() - started,
            exported,
            memory.format_snapshot(),
        )


def _sync_documents_group(
    search_client,
    collection,
    access_date,
    document_items,
    dataset,
    access_day,
):
    try:
        first_item = next(document_items)
    except StopIteration:
        return 0

    index_prefix = settings.OPENSEARCH_INDEX_NAME
    index_date = access_date.isoformat()
    collection_code = collection.acron3
    if dataset == "counter":
        index_name = generate_month_index_name(
            index_prefix=index_prefix,
            collection=collection_code,
        )
    else:
        index_name = generate_analytics_index_name(
            index_prefix=index_prefix,
            collection=collection_code,
        )

    config = getattr(collection, "log_manager_config", None)
    primary_shards = getattr(config, "opensearch_primary_shards", 1)
    partition_strategy = getattr(
        config,
        "opensearch_partition_strategy",
        OpenSearchPartitionStrategy.ROLLOVER,
    )
    mappings = get_index_mappings(dataset)
    write_index = search_client.prepare_usage_index(
        alias_name=index_name,
        mappings=mappings,
        partition_strategy=partition_strategy,
        access_date=index_date,
        primary_shards=primary_shards,
    )
    exported = search_client.increment_document_items_for_day(
        index_name=write_index,
        document_items=chain((first_item,), document_items),
        access_day=access_day,
        annual=dataset == "analytics",
        resolve_existing_indexes=True,
    )
    search_client.rollover_usage_index(
        alias_name=write_index,
        mappings=mappings,
        primary_shards=primary_shards,
        read_alias=index_name if write_index != index_name else None,
    )
    return exported
