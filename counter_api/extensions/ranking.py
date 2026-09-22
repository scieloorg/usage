from heapq import heappush, heappushpop
from time import monotonic

from django.conf import settings

from counter_api.constants import METADATA_BATCH_SIZE, METRICS
from counter_api.exceptions import insufficient_information
from counter_api.extensions.contracts import RANKING_ENTITIES, RANKING_GROUPS
from counter_api.extensions.query import usage_scope, validate_segmented_period
from counter_api.metadata import fetch_metadata
from counter_api.query import ReportQuery
from counter_api.search import composite_pages, search
from counter_api.yop import matches_yop, yop_filter
from metrics.opensearch.names import generate_metadata_alias

RANKING_PAGE_SIZE = 1000
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000
MAX_GROUPS = 20
MAX_RESULTS = 10000
MAX_FILTER_KEYS = 10000


class RankingQuery:
    def __init__(self, client=None):
        usage_client = client or ReportQuery()
        self.client = usage_client.client
        self.report_query = usage_client

    def run(self, platform, begin, end, params):
        deadline = monotonic() + settings.COUNTER_QUERY_BUDGET_SECONDS
        (
            relation,
            parent_type,
            parent_id,
            limit,
            group_by,
            metric_type,
            segmented,
        ) = self._parameters(platform, begin, end, params)
        parent_key = self._parent_key(platform, parent_type, parent_id)
        key_batches = self._key_batches(platform, params, deadline)
        groups = self._ranked_groups(
            platform,
            begin,
            end,
            relation,
            params,
            parent_key,
            metric_type,
            group_by,
            key_batches,
            limit,
            deadline,
            segmented,
        )

        return {
            "platform": platform.acron3,
            "begin_date": begin.isoformat(),
            "end_date": end.isoformat(),
            "parent_type": parent_type,
            "parent_id": parent_id,
            "entity_type": params["entity_type"],
            "metric_type": metric_type,
            "groups": self._result_groups(groups, relation, group_by, deadline),
        }

    def _parameters(self, platform, begin, end, params):
        entity_type = params.get("entity_type")
        relation = RANKING_ENTITIES.get(entity_type)
        parent_type = params.get("parent_type")
        parent_id = params.get("parent_id")

        if not relation or platform.collection_type != relation["collection_type"]:
            raise insufficient_information()
        if parent_type != relation["parent_type"] or not parent_id:
            raise insufficient_information()

        try:
            limit = int(params.get("limit", DEFAULT_LIMIT))
        except (TypeError, ValueError):
            raise insufficient_information()

        if limit < 1 or limit > MAX_LIMIT:
            raise insufficient_information()

        group_by = params.get("group_by", "")
        if group_by not in RANKING_GROUPS:
            raise insufficient_information()

        metric_type = params.get("metric_type", "Total_Item_Requests")
        if metric_type not in METRICS:
            raise insufficient_information()

        if params.get("yop"):
            values = [value for value in params["yop"].split("|") if value]
            if not yop_filter(values):
                raise insufficient_information()

        dimensions = set(group_by.split(",")) if group_by else set()
        dimensions.update(
            dimension for dimension in ("country", "language") if params.get(dimension)
        )
        segmented = validate_segmented_period(
            begin,
            end,
            dimensions,
            metric_type,
        )
        if segmented and params.get("yop") and relation["metadata"] != "documents":
            raise insufficient_information()

        return (
            relation,
            parent_type,
            parent_id,
            limit,
            group_by,
            metric_type,
            segmented,
        )

    def _parent_key(self, platform, parent_type, parent_id):
        if parent_type == "collection":
            if parent_id != platform.acron3:
                raise insufficient_information()
            return None

        return self.report_query.resolve_item_id(platform, "tr", parent_id)

    def _key_batches(self, platform, params, deadline):
        subject_area = params.get("subject_area")
        if not subject_area:
            return [None]

        source_keys = self._source_keys(platform, subject_area, deadline)

        return [
            source_keys[start : start + METADATA_BATCH_SIZE]
            for start in range(0, len(source_keys), METADATA_BATCH_SIZE)
        ]

    def _ranked_groups(
        self,
        platform,
        begin,
        end,
        relation,
        params,
        parent_key,
        metric_type,
        group_by,
        key_batches,
        limit,
        deadline,
        segmented,
    ):
        groups = {}

        for source_keys in key_batches:
            index_name, body = self._query_body(
                platform,
                begin,
                end,
                relation["key_field"],
                relation.get("data_type"),
                parent_key,
                metric_type,
                group_by,
                params,
                source_keys,
                segmented,
            )

            for buckets in composite_pages(self.client, index_name, body, deadline):
                yop_keys = self._yop_keys(
                    buckets,
                    relation["key_field"],
                    params,
                    deadline,
                    segmented,
                )

                self._collect_groups(
                    groups,
                    buckets,
                    relation["key_field"],
                    limit,
                    yop_keys,
                )

        return groups

    def _collect_groups(self, groups, buckets, entity_key, limit, yop_keys):
        for bucket in buckets:
            count = int(bucket["count"]["value"])
            key = bucket["key"][entity_key]
            if count <= 0 or not key:
                continue
            if yop_keys is not None and key not in yop_keys:
                continue

            group = tuple(
                bucket["key"].get(dimension)
                for dimension in ("country_code", "content_language")
                if dimension in bucket["key"]
            )
            winners = groups.setdefault(group, [])
            if len(groups) > MAX_GROUPS or len(groups) * limit > MAX_RESULTS:
                raise insufficient_information()

            inverted_key = bytes(255 - byte for byte in key.encode("utf-8"))
            candidate = (count, inverted_key, key)
            if len(winners) < limit:
                heappush(winners, candidate)
            elif candidate > winners[0]:
                heappushpop(winners, candidate)

    def _yop_keys(self, buckets, entity_key, params, deadline, segmented):
        if not segmented or not params.get("yop"):
            return None

        values = [value for value in params["yop"].split("|") if value]
        keys = [
            bucket["key"].get(entity_key)
            for bucket in buckets
            if bucket["key"].get(entity_key)
        ]
        metadata = fetch_metadata(self.client, "documents", keys, deadline)

        return {
            key
            for key in keys
            if matches_yop(metadata.get(key, {}).get("publication_year"), values)
        }

    def _result_groups(self, groups, relation, group_by, deadline):
        winner_keys = {item[2] for winners in groups.values() for item in winners}
        metadata = fetch_metadata(
            self.client,
            relation["metadata"],
            winner_keys,
            deadline,
        )
        dimensions = [
            dimension for dimension in ("country", "language") if dimension in group_by
        ]
        result = []

        for group, winners in sorted(groups.items(), key=lambda item: str(item[0])):
            items = []
            for count, _, key in sorted(winners, key=lambda item: (-item[0], item[2])):
                item = metadata.get(key, {})
                items.append(
                    {
                        "id": key,
                        "title": item.get("title") or "",
                        "count": count,
                    }
                )

            labels = [
                "Unknown" if not value or value == "_unknown" else value
                for value in group
            ]
            result.append({"dimensions": dict(zip(dimensions, labels)), "items": items})

        return result

    def _query_body(
        self,
        platform,
        begin,
        end,
        entity_key,
        data_type,
        parent_key,
        metric_type,
        group_by,
        params,
        source_keys,
        segmented,
    ):
        index_name, filters = usage_scope(
            platform,
            begin,
            end,
            segmented,
            data_type,
        )

        if parent_key:
            filters.append({"term": {"source_key": parent_key}})
        if params.get("country"):
            filters.append({"term": {"country_code": params["country"]}})
        if params.get("language"):
            filters.append({"term": {"content_language": params["language"]}})
        if source_keys:
            filters.append({"terms": {"source_key": source_keys}})
        if params.get("yop") and not segmented:
            values = [value for value in params["yop"].split("|") if value]
            clause = yop_filter(values)
            if not clause:
                raise insufficient_information()
            filters.append(clause)

        dimensions = []
        if "country" in group_by:
            dimensions.append("country_code")
        if "language" in group_by:
            dimensions.append("content_language")
        dimensions.append(entity_key)

        sources = [
            {field: {"terms": {"field": field, "missing_bucket": True}}}
            for field in dimensions
        ]
        body = {
            "size": 0,
            "track_total_hits": False,
            "query": {"bool": {"filter": filters}},
            "aggs": {
                "rows": {
                    "composite": {"size": RANKING_PAGE_SIZE, "sources": sources},
                    "aggs": {"count": {"sum": {"field": METRICS[metric_type]}}},
                }
            },
        }

        return index_name, body

    def _source_keys(self, platform, subject_area, deadline):
        index_name = generate_metadata_alias(settings.OPENSEARCH_INDEX_NAME, "sources")
        body = {
            "size": METADATA_BATCH_SIZE,
            "_source": False,
            "track_total_hits": False,
            "sort": [{"_id": "asc"}],
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"collection": platform.acron3}},
                        {"term": {"subject_areas": subject_area}},
                    ]
                }
            },
        }
        keys = []

        while True:
            response = search(self.client, index_name, body, deadline)
            hits = response["hits"]["hits"]
            keys.extend(hit["_id"] for hit in hits)
            if len(keys) > MAX_FILTER_KEYS:
                raise insufficient_information()

            if len(hits) < METADATA_BATCH_SIZE:
                return keys

            body["search_after"] = hits[-1]["sort"]
