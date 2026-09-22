from time import monotonic

from django.conf import settings
from opensearchpy import NotFoundError

from counter_api.constants import COMPOSITE_PAGE_SIZE
from counter_api.exceptions import incongruous_filter, invalid_filter
from counter_api.identifiers import ITEM_ID_FIELDS
from counter_api.metadata import fetch_metadata
from counter_api.search import composite_pages, search
from counter_api.yop import yop_filter
from metrics.opensearch.client import OpenSearchUsageClient
from metrics.opensearch.names import generate_metadata_alias, generate_month_index_name

ITEM_GROUP_FIELDS = (
    "source_key",
    "document_key",
    "metric_scope",
    "data_type",
    "parent_data_type",
    "access_type",
    "access_method",
    "publication_year",
)
PLATFORM_GROUP_FIELDS = (
    "metric_scope",
    "data_type",
    "access_type",
    "access_method",
)
TITLE_GROUP_FIELDS = (
    "source_key",
    "metric_scope",
    "data_type",
    "parent_data_type",
    "access_type",
    "access_method",
    "publication_year",
)


class ReportQuery:
    def __init__(self, client=None):
        usage_client = client or OpenSearchUsageClient()
        self.client = usage_client.client
        self.deadline = monotonic() + settings.COUNTER_QUERY_BUDGET_SECONDS

    def fetch(self, platform, months, report_id=None, params=None):
        if not months:
            return

        for buckets in self._fetch_buckets(platform.acron3, months, report_id, params):
            source_keys = {bucket["key"].get("source_key") for bucket in buckets}
            document_keys = {bucket["key"].get("document_key") for bucket in buckets}
            source_keys.discard(None)
            document_keys.discard(None)

            sources = fetch_metadata(
                self.client,
                "sources",
                source_keys,
                self.deadline,
            )

            documents = fetch_metadata(
                self.client,
                "documents",
                document_keys,
                self.deadline,
            )

            for bucket in buckets:
                key = bucket["key"]
                yield (
                    bucket,
                    sources.get(key.get("source_key"), {}),
                    documents.get(key.get("document_key"), {}),
                )

    def resolve_item_id(self, platform, report_id, item_id):
        field, key = self.resolve_item_filter(platform, report_id, item_id)

        return key

    def resolve_item_filter(self, platform, report_id, item_id):
        namespace, separator, value = item_id.partition(":")
        if not separator or not value:
            raise invalid_filter("item_id")

        fields = ITEM_ID_FIELDS.get(namespace.lower())
        if not fields:
            raise invalid_filter("item_id")

        if report_id.startswith("tr"):
            entities = ("sources",)
        elif namespace.lower() in {"print_issn", "online_issn", "isbn"}:
            entities = ("sources",)
        elif namespace.lower() == "proprietary":
            entities = ("documents", "sources")
        else:
            entities = ("documents",)

        hits = []
        for entity in entities:
            direct_field = "source_id" if entity == "sources" else "document_id"
            candidates = [
                field
                for field in fields
                if field != "source_id" and field != "document_id"
            ]
            if namespace.lower() == "proprietary":
                candidates.append(direct_field)

            index_name = generate_metadata_alias(settings.OPENSEARCH_INDEX_NAME, entity)
            body = {
                "size": 2,
                "_source": False,
                "track_total_hits": False,
                "query": {
                    "bool": {
                        "filter": [{"term": {"collection": platform.acron3}}],
                        "should": [
                            {"term": {candidate: value}} for candidate in candidates
                        ],
                        "minimum_should_match": 1,
                    }
                },
            }
            try:
                response = search(
                    self.client,
                    index_name,
                    body,
                    self.deadline,
                    limit=5,
                )
            except NotFoundError:
                response = {"hits": {"hits": []}}

            key_field = "source_key" if entity == "sources" else "document_key"
            hits.extend((key_field, hit["_id"]) for hit in response["hits"]["hits"])

        if not hits:
            raise invalid_filter("item_id")
        if len(hits) > 1:
            raise incongruous_filter("item_id")

        return hits[0]

    def _fetch_buckets(self, collection, months, report_id, params):
        index_name = generate_month_index_name(
            settings.OPENSEARCH_INDEX_NAME,
            collection,
        )
        body = self._query_body(months, None, report_id, params)

        try:
            yield from composite_pages(
                self.client,
                index_name,
                body,
                self.deadline,
            )
        except NotFoundError:
            return

    def _query_body(self, months, after, report_id, params=None):
        params = params or {}
        fields = ITEM_GROUP_FIELDS
        if report_id == "pr":
            fields = PLATFORM_GROUP_FIELDS
        elif report_id and report_id.startswith("tr"):
            fields = TITLE_GROUP_FIELDS

        sources = []
        for field in fields:
            sources.append(
                {
                    field: {
                        "terms": {
                            "field": field,
                            "missing_bucket": True,
                        }
                    }
                }
            )

        sources.insert(
            2,
            {
                "month": {
                    "date_histogram": {
                        "field": "month",
                        "calendar_interval": "1M",
                        "format": "yyyy-MM",
                    }
                }
            },
        )

        composite = {
            "size": COMPOSITE_PAGE_SIZE,
            "sources": sources,
        }
        if after:
            composite["after"] = after

        filters = [{"terms": {"month": [month.strftime("%Y-%m") for month in months]}}]
        for parameter, field in (
            ("Access_Type", "access_type"),
            ("Access_Method", "access_method"),
        ):
            if params.get(parameter):
                filters.append({"terms": {field: params[parameter]}})

        if report_id == "ir" and params.get("Data_Type"):
            filters.append({"terms": {"data_type": params["Data_Type"]}})
        if report_id == "ir":
            filters.append({"term": {"metric_scope": "item"}})

        if params.get("Item_Key"):
            field = params.get("Item_Key_Field")
            if not field:
                field = "source_key" if report_id.startswith("tr") else "document_key"
            filters.append({"term": {field: params["Item_Key"]}})

        if report_id in {"tr", "tr_j3", "tr_b3", "ir"} and params.get("YOP"):
            clause = yop_filter(params["YOP"])
            if clause:
                filters.append(clause)

        return {
            "size": 0,
            "track_total_hits": False,
            "query": {"bool": {"filter": filters}},
            "aggs": {
                "rows": {
                    "composite": composite,
                    "aggs": {
                        "total_requests": {"sum": {"field": "total_requests"}},
                        "total_investigations": {
                            "sum": {"field": "total_investigations"}
                        },
                        "unique_requests": {"sum": {"field": "unique_requests"}},
                        "unique_investigations": {
                            "sum": {"field": "unique_investigations"}
                        },
                    },
                }
            },
        }
