import logging

from django.conf import settings
from opensearchpy import NotFoundError, OpenSearch, helpers

from metrics.opensearch.mappings import get_index_mappings
from metrics.opensearch.names import generate_month_index_name, generate_year_index_name
from metrics.opensearch.painless import (
    build_idempotent_job_increment_action,
    merge_metric_document,
)


class OpenSearchUsageClient:
    def __init__(self, url=None, basic_auth=None, api_key=None, verify_certs=None):
        self.bulk_chunk_size = getattr(
            settings,
            "OPENSEARCH_BULK_CHUNK_SIZE",
            500,
        )
        if self.bulk_chunk_size <= 0:
            raise ValueError("OpenSearch bulk chunk size must be greater than zero.")

        self.client = self.get_opensearch_client(url, basic_auth, api_key, verify_certs)
        logging.info(
            "OpenSearch HTTP request compression is %s; bulk chunk size is %s.",
            "enabled"
            if getattr(settings, "OPENSEARCH_HTTP_COMPRESS", True)
            else "disabled",
            self.bulk_chunk_size,
        )

    def get_opensearch_client(
        self,
        url=None,
        basic_auth=None,
        api_key=None,
        verify_certs=None,
    ):
        url = url or getattr(settings, "OPENSEARCH_URL", None)
        basic_auth = basic_auth or getattr(settings, "OPENSEARCH_BASIC_AUTH", None)
        api_key = api_key or getattr(settings, "OPENSEARCH_API_KEY", None)
        if verify_certs is None:
            verify_certs = getattr(settings, "OPENSEARCH_VERIFY_CERTS", False)
        http_compress = getattr(settings, "OPENSEARCH_HTTP_COMPRESS", True)

        if basic_auth:
            return OpenSearch(
                url,
                http_auth=tuple(basic_auth),
                verify_certs=verify_certs,
                http_compress=http_compress,
            )
        if api_key:
            return OpenSearch(
                url,
                api_key=api_key,
                verify_certs=verify_certs,
                http_compress=http_compress,
            )
        return OpenSearch(
            url,
            verify_certs=verify_certs,
            http_compress=http_compress,
        )

    def ping(self):
        try:
            return self.client.ping()
        except Exception as exc:
            logging.error("Error pinging OpenSearch client: %s", exc)
            return False

    def create_index(self, index_name, mappings, ping_client=False):
        if ping_client and not self.ping():
            return

        response = self.client.indices.create(
            index=index_name,
            body={
                "settings": {"index": {"number_of_replicas": 0}},
                "mappings": mappings,
            },
        )
        logging.info("Index %s created: %s", index_name, response)

    def create_index_if_not_exists(self, index_name, mappings, ping_client=False):
        if ping_client and not self.ping():
            return

        if not self.client.indices.exists(index=index_name):
            self.create_index(
                index_name=index_name,
                mappings=mappings,
                ping_client=False,
            )

    def ensure_usage_indexes(self, collection, access_date, index_prefix=None):
        index_prefix = index_prefix or getattr(
            settings,
            "OPENSEARCH_INDEX_NAME",
            "usage",
        )
        year_index = generate_year_index_name(index_prefix, collection, access_date)
        month_index = generate_month_index_name(index_prefix, collection, access_date)

        self.create_index_if_not_exists(
            year_index,
            get_index_mappings(collection, "year"),
        )
        self.create_index_if_not_exists(
            month_index,
            get_index_mappings(collection, "month"),
        )

        return {"year": year_index, "month": month_index}

    def index_documents(self, index_name, documents, ping_client=False):
        if ping_client and not self.ping():
            return

        if not documents:
            return

        helpers.bulk(
            self.client,
            (
                {"_index": index_name, "_id": doc_id, "_source": document}
                for doc_id, document in documents.items()
            ),
        )

    def increment_document_items_for_daily_job(
        self,
        index_name,
        document_items,
        job_id,
        ping_client=False,
    ):
        if ping_client and not self.ping():
            return

        succeeded, _failed = helpers.bulk(
            self.client,
            (
                build_idempotent_job_increment_action(
                    index_name=index_name,
                    doc_id=doc_id,
                    document=document,
                    job_id=job_id,
                )
                for doc_id, document in document_items
            ),
            chunk_size=self.bulk_chunk_size,
        )
        return succeeded

    def delete_documents(self, index_name, doc_ids, ping_client=False):
        if ping_client and not self.ping():
            return

        if not doc_ids:
            return

        helpers.bulk(
            self.client,
            (
                {"_op_type": "delete", "_index": index_name, "_id": doc_id}
                for doc_id in doc_ids
            ),
        )

    def delete_documents_by_key(self, index_name, data, ping_client=False):
        if ping_client and not self.ping():
            return False

        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "terms": {
                                key: values if isinstance(values, list) else [values],
                            }
                        }
                        for key, values in data.items()
                    ]
                }
            }
        }

        try:
            self.client.delete_by_query(index=index_name, body=query)
            return True
        except Exception as exc:
            logging.error("Failed to delete documents from %s: %s", index_name, exc)
            return False

    def fetch_documents_by_ids(self, index_name, doc_ids, ping_client=False):
        if ping_client and not self.ping():
            return {}

        if not doc_ids:
            return {}

        try:
            response = self.client.mget(index=index_name, body={"ids": doc_ids})
        except NotFoundError:
            return {}

        documents = {}
        for document in response.get("docs", []):
            if document.get("found"):
                documents[document["_id"]] = document["_source"]
        return documents

    def fetch_documents_by_key(self, index_name, data, ping_client=False):
        if ping_client and not self.ping():
            return {}

        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "terms": {
                                key: values if isinstance(values, list) else [values],
                            }
                        }
                        for key, values in data.items()
                    ]
                }
            }
        }

        try:
            return {
                hit["_id"]: hit["_source"]
                for hit in helpers.scan(self.client, index=index_name, query=query)
            }
        except NotFoundError:
            return {}

    def sync_documents(self, index_name, documents, operation="add", ping_client=False):
        if ping_client and not self.ping():
            return

        if not documents:
            return

        existing_documents = self.fetch_documents_by_ids(
            index_name=index_name,
            doc_ids=list(documents.keys()),
        )
        upserts = {}
        deletes = []

        for doc_id, document in documents.items():
            merged = merge_metric_document(
                existing_documents.get(doc_id),
                document,
                operation=operation,
            )
            if merged is None:
                if doc_id in existing_documents:
                    deletes.append(doc_id)
                continue
            upserts[doc_id] = merged

        if upserts:
            self.index_documents(index_name=index_name, documents=upserts)
        if deletes:
            self.delete_documents(index_name=index_name, doc_ids=deletes)
