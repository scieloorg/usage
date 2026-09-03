import logging
import resource
from itertools import chain
from time import monotonic

from django.conf import settings

from metrics.opensearch.mappings import get_index_mappings
from metrics.opensearch.names import generate_month_index_name, generate_year_index_name
from metrics.services import daily_payloads


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

    for granularity in ("month", "year"):
        started = monotonic()
        exported = _sync_documents_group(
            search_client=search_client,
            collection=job.collection.acron3,
            access_date=job.access_date,
            document_items=daily_payloads.iter_document_items(
                job.storage_path,
                granularity,
            ),
            granularity=granularity,
            job_id=job.job_id,
        )
        logging.info(
            "Daily metric job %s %s OpenSearch export completed in %.3f "
            "seconds; %s documents; peak RSS %.1f MiB.",
            job.pk,
            granularity,
            monotonic() - started,
            exported,
            _peak_rss_mib(),
        )


def _sync_documents_group(
    search_client,
    collection,
    access_date,
    document_items,
    granularity,
    job_id,
):
    try:
        first_item = next(document_items)
    except StopIteration:
        return 0

    index_prefix = settings.OPENSEARCH_INDEX_NAME
    index_date = access_date.isoformat()
    if granularity == "month":
        index_name = generate_month_index_name(
            index_prefix=index_prefix,
            collection=collection,
            date=index_date,
        )
    else:
        index_name = generate_year_index_name(
            index_prefix=index_prefix,
            collection=collection,
            date=index_date,
        )

    search_client.create_index_if_not_exists(
        index_name=index_name,
        mappings=get_index_mappings(collection, granularity),
    )
    return search_client.increment_document_items_for_daily_job(
        index_name=index_name,
        document_items=chain((first_item,), document_items),
        job_id=job_id,
    )


def _peak_rss_mib():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
