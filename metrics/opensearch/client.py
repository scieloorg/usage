import logging

from django.conf import settings
from opensearchpy import NotFoundError, OpenSearch, helpers

from metrics.opensearch.mappings import get_index_mappings, get_index_settings
from metrics.opensearch.names import (
    generate_analytics_index_name,
    generate_month_index_name,
    generate_physical_index_name,
)
from metrics.opensearch.painless import (
    build_idempotent_annual_day_increment_action,
    build_idempotent_day_increment_action,
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

    def create_index(
        self,
        index_name,
        mappings,
        ping_client=False,
        primary_shards=1,
    ):
        if ping_client and not self.ping():
            return

        response = self.client.indices.create(
            index=index_name,
            body={
                "settings": get_index_settings(primary_shards),
                "mappings": mappings,
            },
        )
        logging.info("Index %s created: %s", index_name, response)

    def create_index_if_not_exists(
        self,
        index_name,
        mappings,
        ping_client=False,
        primary_shards=1,
    ):
        if ping_client and not self.ping():
            return

        if not self.client.indices.exists(index=index_name):
            self.create_index(
                index_name=index_name,
                mappings=mappings,
                primary_shards=primary_shards,
                ping_client=False,
            )

    def create_alias_if_not_exists(
        self,
        alias_name,
        mappings,
        primary_shards=1,
        ping_client=False,
    ):
        if ping_client and not self.ping():
            return
        if self.client.indices.exists_alias(name=alias_name):
            return

        physical_name = generate_physical_index_name(alias_name)
        if not self.client.indices.exists(index=physical_name):
            self.client.indices.create(
                index=physical_name,
                body={
                    "settings": get_index_settings(primary_shards),
                    "mappings": mappings,
                    "aliases": {alias_name: {}},
                },
            )
            return

        self.client.indices.put_alias(index=physical_name, name=alias_name)

    def ensure_usage_indexes(self, collection, access_date, index_prefix=None):
        index_prefix = index_prefix or getattr(
            settings,
            "OPENSEARCH_INDEX_NAME",
            "usage",
        )
        month_index = generate_month_index_name(index_prefix, collection, access_date)
        analytics_index = generate_analytics_index_name(
            index_prefix,
            collection,
            access_date,
        )

        self.create_alias_if_not_exists(
            month_index,
            get_index_mappings("counter"),
        )
        self.create_alias_if_not_exists(
            analytics_index,
            get_index_mappings("analytics"),
        )

        return {"counter": month_index, "analytics": analytics_index}

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

    def index_document_items(self, index_name, document_items, ping_client=False):
        if ping_client and not self.ping():
            return 0

        succeeded, _failed = helpers.bulk(
            self.client,
            (
                {"_index": index_name, "_id": doc_id, "_source": document}
                for doc_id, document in document_items
            ),
            chunk_size=self.bulk_chunk_size,
        )
        return succeeded

    def increment_document_items_for_day(
        self,
        index_name,
        document_items,
        access_day,
        annual=False,
        ping_client=False,
    ):
        if ping_client and not self.ping():
            return

        action_builder = (
            build_idempotent_annual_day_increment_action
            if annual
            else build_idempotent_day_increment_action
        )
        succeeded, _failed = helpers.bulk(
            self.client,
            (
                action_builder(
                    index_name=index_name,
                    doc_id=doc_id,
                    document=document,
                    access_day=access_day,
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
