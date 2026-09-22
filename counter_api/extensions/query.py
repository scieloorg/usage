from django.conf import settings

from counter_api.availability import split_period
from counter_api.constants import METRICS
from counter_api.dates import iter_months
from counter_api.exceptions import (
    insufficient_information,
    invalid_dates,
    service_unavailable,
)
from counter_api.extensions.contracts import SEGMENT_DIMENSIONS
from metrics.opensearch.names import (
    generate_analytics_index_name,
    generate_month_index_name,
)


def metric_composite_body(filters, sources, metric_type, page_size):
    return {
        "size": 0,
        "track_total_hits": False,
        "query": {"bool": {"filter": filters}},
        "aggs": {
            "rows": {
                "composite": {"size": page_size, "sources": sources},
                "aggs": {"count": {"sum": {"field": METRICS[metric_type]}}},
            }
        },
    }


def require_complete_period(platform, begin, end):
    _, pending, unavailable = split_period(platform, begin, end)
    missing = [*unavailable, *pending]
    if missing:
        months = "|".join(month.strftime("%Y-%m") for month in sorted(missing))
        raise service_unavailable(f"Usage data incomplete for {months}")


def validate_segmented_period(begin, end, dimensions, metric_type):
    segmented = bool(SEGMENT_DIMENSIONS & set(dimensions))
    if not segmented:
        return False
    if begin.month != 1 or end.month != 12:
        raise invalid_dates()
    if metric_type.startswith("Unique_"):
        raise insufficient_information()

    return True


def usage_scope(platform, begin, end, segmented, data_type=None):
    if segmented:
        index_name = generate_analytics_index_name(
            settings.OPENSEARCH_INDEX_NAME,
            platform.acron3,
        )
        periods = [str(year) for year in range(begin.year, end.year + 1)]
        filters = [{"terms": {"year": periods}}]
    else:
        index_name = generate_month_index_name(
            settings.OPENSEARCH_INDEX_NAME,
            platform.acron3,
        )
        periods = [month.strftime("%Y-%m") for month in iter_months(begin, end)]
        filters = [{"terms": {"month": periods}}]

    filters.extend(
        [
            {"term": {"metric_scope": "item"}},
            {"term": {"access_method": "Regular"}},
        ]
    )
    if data_type:
        filters.append({"term": {"data_type": data_type}})

    return index_name, filters
