import logging
from itertools import islice

from django.conf import settings
from opensearchpy import NotFoundError, OpenSearch, RequestError, helpers

from log_manager_config.choices import OpenSearchPartitionStrategy
from metrics.opensearch.mappings import get_index_settings
from metrics.opensearch.names import (
    generate_initial_index_name,
    generate_rollover_index_name,
    generate_yearly_write_alias,
)
from metrics.opensearch.painless import (
    build_idempotent_annual_day_increment_action,
    build_idempotent_day_increment_action,
    merge_metric_document,
)

DOCUMENT_INDEX_LOOKUP_BATCH_SIZE = 1000


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

        physical_name = generate_initial_index_name(alias_name)
        if not self.client.indices.exists(index=physical_name):
            self._create_index_with_alias(
                physical_name,
                alias_name,
                mappings,
                primary_shards,
            )
        if not self.client.indices.exists_alias(index=physical_name, name=alias_name):
            self.client.indices.put_alias(index=physical_name, name=alias_name)

    def prepare_usage_index(
        self,
        alias_name,
        mappings,
        partition_strategy,
        access_date,
        primary_shards=1,
    ):
        if partition_strategy == OpenSearchPartitionStrategy.YEARLY:
            write_alias = generate_yearly_write_alias(alias_name, access_date)
            self._ensure_rollover_alias(
                write_alias,
                mappings,
                primary_shards,
                read_alias=alias_name,
            )
            return write_alias

        if partition_strategy != OpenSearchPartitionStrategy.ROLLOVER:
            raise ValueError(
                f"Unsupported OpenSearch partition strategy: {partition_strategy}."
            )

        self._ensure_rollover_alias(alias_name, mappings, primary_shards)
        return alias_name

    def _ensure_rollover_alias(
        self,
        alias_name,
        mappings,
        primary_shards,
        read_alias=None,
    ):
        if self.client.indices.exists_alias(name=alias_name):
            self._get_write_index(alias_name)
            self._ensure_read_alias(alias_name, read_alias)
            return

        physical_name = generate_rollover_index_name(alias_name)
        alias_definitions = {alias_name: {"is_write_index": True}}
        if read_alias and read_alias != alias_name:
            alias_definitions[read_alias] = {}
        if not self.client.indices.exists(index=physical_name):
            self._create_index_with_alias_definitions(
                physical_name=physical_name,
                alias_definitions=alias_definitions,
                mappings=mappings,
                primary_shards=primary_shards,
            )
        if not self.client.indices.exists_alias(index=physical_name, name=alias_name):
            self.client.indices.put_alias(
                index=physical_name,
                name=alias_name,
                body={"is_write_index": True},
            )
        if read_alias and not self.client.indices.exists_alias(
            index=physical_name,
            name=read_alias,
        ):
            self.client.indices.put_alias(index=physical_name, name=read_alias)

    def _create_index_with_alias(
        self,
        physical_name,
        alias_name,
        mappings,
        primary_shards,
        alias_options=None,
    ):
        self._create_index_with_alias_definitions(
            physical_name=physical_name,
            alias_definitions={alias_name: alias_options or {}},
            mappings=mappings,
            primary_shards=primary_shards,
        )

    def _create_index_with_alias_definitions(
        self,
        physical_name,
        alias_definitions,
        mappings,
        primary_shards,
    ):
        try:
            self.client.indices.create(
                index=physical_name,
                body={
                    "settings": get_index_settings(primary_shards),
                    "mappings": mappings,
                    "aliases": alias_definitions,
                },
            )
        except RequestError:
            if not self.client.indices.exists(index=physical_name):
                raise

    def _ensure_read_alias(self, write_alias, read_alias):
        if not read_alias or read_alias == write_alias:
            return
        for index_name in self.client.indices.get_alias(name=write_alias):
            if not self.client.indices.exists_alias(
                index=index_name,
                name=read_alias,
            ):
                self.client.indices.put_alias(index=index_name, name=read_alias)

    def rollover_usage_index(
        self,
        alias_name,
        mappings,
        primary_shards=1,
        read_alias=None,
    ):
        body = {
            "conditions": {
                "max_size": getattr(
                    settings,
                    "OPENSEARCH_ROLLOVER_MAX_SIZE",
                    "50gb",
                )
            },
            "settings": get_index_settings(primary_shards),
            "mappings": mappings,
        }
        if read_alias and read_alias != alias_name:
            body["aliases"] = {read_alias: {}}

        response = self.client.indices.rollover(
            alias=alias_name,
            body=body,
        )
        if response.get("rolled_over"):
            self._ensure_read_alias(alias_name, read_alias)
        return response

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
        resolve_existing_indexes=False,
        ping_client=False,
    ):
        if ping_client and not self.ping():
            return

        action_builder = (
            build_idempotent_annual_day_increment_action
            if annual
            else build_idempotent_day_increment_action
        )
        if resolve_existing_indexes:
            return self._increment_items_in_existing_indexes(
                index_name,
                document_items,
                access_day,
                action_builder,
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

    def _increment_items_in_existing_indexes(
        self,
        alias_name,
        document_items,
        access_day,
        action_builder,
    ):
        write_index = self._get_write_index(alias_name)
        succeeded = 0
        batch_size = min(self.bulk_chunk_size, DOCUMENT_INDEX_LOOKUP_BATCH_SIZE)

        while True:
            batch = list(islice(document_items, batch_size))
            if not batch:
                return succeeded

            existing_indexes = self._find_existing_document_indexes(
                alias_name,
                [doc_id for doc_id, _document in batch],
            )
            batch_succeeded, _failed = helpers.bulk(
                self.client,
                (
                    action_builder(
                        index_name=existing_indexes.get(doc_id, write_index),
                        doc_id=doc_id,
                        document=document,
                        access_day=access_day,
                    )
                    for doc_id, document in batch
                ),
                chunk_size=self.bulk_chunk_size,
            )
            succeeded += batch_succeeded

    def _get_write_index(self, alias_name):
        indexes = self.client.indices.get_alias(name=alias_name)
        write_indexes = [
            index_name
            for index_name, index_data in indexes.items()
            if index_data.get("aliases", {}).get(alias_name, {}).get("is_write_index")
        ]
        if len(write_indexes) == 1:
            return write_indexes[0]
        if len(indexes) == 1:
            return next(iter(indexes))
        raise RuntimeError(f"Alias {alias_name} has no unique write index.")

    def _find_existing_document_indexes(self, alias_name, doc_ids):
        response = self.client.search(
            index=alias_name,
            body={
                "size": len(doc_ids) * 2,
                "_source": False,
                "query": {"ids": {"values": doc_ids}},
            },
        )
        indexes = {}
        for hit in response.get("hits", {}).get("hits", []):
            doc_id = hit["_id"]
            if doc_id in indexes and indexes[doc_id] != hit["_index"]:
                raise RuntimeError(
                    f"Document {doc_id} exists in multiple indexes behind "
                    f"alias {alias_name}."
                )
            indexes[doc_id] = hit["_index"]
        return indexes

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
