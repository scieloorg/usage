from time import monotonic

from django.conf import settings

from counter_api.constants import METRICS
from counter_api.exceptions import insufficient_information
from counter_api.extensions.contracts import (
    DISTRIBUTION_CROSSES,
    DISTRIBUTION_DIMENSIONS,
    DISTRIBUTION_ENTITIES,
)
from counter_api.extensions.query import (
    metric_composite_body,
    require_complete_period,
    usage_scope,
    validate_segmented_period,
)
from counter_api.metadata import fetch_metadata
from counter_api.query import ReportQuery
from counter_api.search import composite_pages

PAGE_SIZE = 1000
MAX_BUCKETS = 1000


class DistributionQuery:
    def __init__(self, client=None):
        usage_client = client or ReportQuery()
        self.client = usage_client.client
        self.report_query = usage_client

    def run(self, platform, begin, end, params):
        deadline = monotonic() + settings.COUNTER_QUERY_BUDGET_SECONDS
        dimensions, entity_type, entity_id, metric_type, segmented = self._parameters(
            platform,
            begin,
            end,
            params,
        )
        require_complete_period(platform, begin, end)

        key_field, entity_key = self._entity_filter(
            platform,
            entity_type,
            entity_id,
        )
        index_name, body = self._query_body(
            platform,
            begin,
            end,
            dimensions,
            entity_type,
            metric_type,
            key_field,
            entity_key,
            segmented,
        )
        total, buckets = self._buckets(
            index_name,
            body,
            dimensions,
            deadline,
        )

        return {
            "platform": platform.acron3,
            "begin_date": begin.isoformat(),
            "end_date": end.isoformat(),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "dimension": ",".join(dimensions),
            "dimensions": list(dimensions),
            "metric_type": metric_type,
            "total": total,
            "buckets": buckets,
        }

    def _parameters(self, platform, begin, end, params):
        dimensions = tuple(
            item.strip() for item in params.get("dimension", "").split(",") if item
        )
        entity_type = params.get("entity_type")
        entity_id = params.get("entity_id")
        metric_type = params.get("metric_type", "Total_Item_Requests")

        if (
            not dimensions
            or len(dimensions) > 2
            or any(dimension not in DISTRIBUTION_DIMENSIONS for dimension in dimensions)
            or (len(dimensions) == 2 and dimensions not in DISTRIBUTION_CROSSES)
            or metric_type not in METRICS
            or entity_type not in DISTRIBUTION_ENTITIES
            or not entity_id
        ):
            raise insufficient_information()

        if "journal" in dimensions and (
            entity_type != "collection" or platform.collection_type != "journals"
        ):
            raise insufficient_information()

        segmented = validate_segmented_period(
            begin,
            end,
            dimensions,
            metric_type,
        )

        return dimensions, entity_type, entity_id, metric_type, segmented

    def _entity_filter(self, platform, entity_type, entity_id):
        if entity_type == "collection":
            if entity_id != platform.acron3:
                raise insufficient_information()
            return None, None

        definition = DISTRIBUTION_ENTITIES[entity_type]
        if platform.collection_type != definition["collection_type"]:
            raise insufficient_information()

        key = self.report_query.resolve_item_id(
            platform,
            definition["report_id"],
            entity_id,
        )

        return definition["key_field"], key

    def _query_body(
        self,
        platform,
        begin,
        end,
        dimensions,
        entity_type,
        metric_type,
        key_field,
        entity_key,
        segmented,
    ):
        data_type = DISTRIBUTION_ENTITIES[entity_type].get("data_type")
        index_name, filters = usage_scope(
            platform,
            begin,
            end,
            segmented,
            data_type,
        )

        if key_field:
            filters.append({"term": {key_field: entity_key}})

        sources = []
        for dimension in dimensions:
            source_name = dimension
            field = DISTRIBUTION_DIMENSIONS[dimension]
            if segmented and dimension == "yop":
                source_name = "document_key"
                field = "document_key"

            sources.append(
                {
                    source_name: {
                        "terms": {
                            "field": field,
                            "missing_bucket": True,
                        }
                    }
                }
            )
        body = metric_composite_body(filters, sources, metric_type, PAGE_SIZE)

        return index_name, body

    def _buckets(self, index_name, body, dimensions, deadline):
        totals = {}
        raw_total = 0

        for buckets in composite_pages(self.client, index_name, body, deadline):
            metadata = self._metadata(buckets, dimensions, deadline)

            for bucket in buckets:
                count = int(bucket["count"]["value"])
                if count <= 0:
                    continue

                raw_total += count
                for combination in self._combinations(bucket, dimensions, metadata):
                    totals[combination] = totals.get(combination, 0) + count

                if len(totals) > MAX_BUCKETS:
                    raise insufficient_information()

        buckets = [
            {
                "value": value[0] if len(value) == 1 else " | ".join(value),
                "dimensions": dict(zip(dimensions, value)),
                "count": count,
            }
            for value, count in sorted(
                totals.items(), key=lambda item: (-item[1], item[0])
            )
        ]

        return raw_total, buckets

    def _metadata(self, buckets, dimensions, deadline):
        metadata_dimensions = {"subject_area", "journal"} & set(dimensions)
        if metadata_dimensions:
            dimension = next(iter(metadata_dimensions))
            keys = [
                bucket["key"][dimension]
                for bucket in buckets
                if bucket["key"].get(dimension)
            ]

            return fetch_metadata(self.client, "sources", keys, deadline)

        if "yop" not in dimensions:
            return {}

        keys = [
            bucket["key"]["document_key"]
            for bucket in buckets
            if bucket["key"].get("document_key")
        ]

        return fetch_metadata(self.client, "documents", keys, deadline)

    @staticmethod
    def _combinations(bucket, dimensions, metadata):
        combinations = [()]

        for dimension in dimensions:
            value = bucket["key"].get(dimension)
            if dimension == "subject_area":
                source = metadata.get(value, {})
                values = set(source.get("subject_areas") or []) or {"Unknown"}
            elif dimension == "journal":
                source = metadata.get(value, {})
                values = {source.get("title") or value or "Unknown"}
            elif dimension == "yop":
                document_key = bucket["key"].get("document_key")
                if document_key:
                    value = metadata.get(document_key, {}).get("publication_year")
                values = {f"{value or 1:04d}"}
            else:
                values = {"Unknown" if not value or value == "_unknown" else value}

            combinations = [
                combination + (dimension_value,)
                for combination in combinations
                for dimension_value in values
            ]

        return combinations
