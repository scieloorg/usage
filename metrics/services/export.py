import logging

from django.conf import settings

from metrics.opensearch.mappings import get_index_mappings
from metrics.opensearch.names import generate_month_index_name, generate_year_index_name
from metrics.services import daily_payloads


def load_daily_metric_payload(job):
    if not job.storage_path:
        return None
    try:
        return daily_payloads.read_payload(job.storage_path)
    except FileNotFoundError:
        logging.warning("Daily metric payload not found for job %s.", job.pk)
        return None


def export_daily_metric_payload(search_client, job, payload):
    if not job.job_id:
        raise RuntimeError("Daily metric job has no payload hash.")

    export_documents(
        search_client=search_client,
        documents=payload.get("documents") or {},
        collection=payload.get("collection") or job.collection.acron3,
        job_id=job.job_id,
    )


def export_documents(search_client, documents, collection, job_id):
    if not documents:
        return

    _sync_documents_group(
        search_client=search_client,
        collection=collection,
        documents=documents.get("month", {}),
        granularity="month",
        job_id=job_id,
    )
    _sync_documents_group(
        search_client=search_client,
        collection=collection,
        documents=documents.get("year", {}),
        granularity="year",
        job_id=job_id,
    )


def _sync_documents_group(
    search_client,
    collection,
    documents,
    granularity,
    job_id,
):
    if not documents:
        return

    grouped_documents = {}
    index_prefix = settings.OPENSEARCH_INDEX_NAME

    for doc_id, document in documents.items():
        access = document.get("access") or {}
        if granularity == "month":
            index_name = generate_month_index_name(
                index_prefix=index_prefix,
                collection=collection,
                date=f"{access.get('month')}-01",
            )
            mappings = get_index_mappings(collection, "month")
        else:
            index_name = generate_year_index_name(
                index_prefix=index_prefix,
                collection=collection,
                date=f"{access.get('year')}-01-01",
            )
            mappings = get_index_mappings(collection, "year")

        grouped_documents.setdefault(
            index_name, {"mappings": mappings, "documents": {}}
        )
        grouped_documents[index_name]["documents"][doc_id] = document

    for index_name, payload in grouped_documents.items():
        search_client.create_index_if_not_exists(
            index_name=index_name,
            mappings=payload["mappings"],
        )
        search_client.increment_documents_for_daily_job(
            index_name=index_name,
            documents=payload["documents"],
            job_id=job_id,
        )
