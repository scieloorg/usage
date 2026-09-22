from datetime import date
from time import monotonic

from django.conf import settings
from opensearchpy import NotFoundError

from counter_api.dates import iter_months
from counter_api.search import search
from metrics.opensearch.client import OpenSearchUsageClient
from metrics.opensearch.names import generate_month_status_index_name

PAGE_SIZE = 1000


def available_months(platform):
    index_name = generate_month_status_index_name(settings.OPENSEARCH_INDEX_NAME)
    client = OpenSearchUsageClient().client
    deadline = monotonic() + settings.COUNTER_QUERY_BUDGET_SECONDS
    current_month = date.today().strftime("%Y-%m")
    months = []
    after = None

    while True:
        body = {
            "size": 0,
            "track_total_hits": False,
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"collection": platform.acron3}},
                        {"term": {"complete": True}},
                        {"range": {"month": {"lt": current_month}}},
                    ]
                }
            },
            "aggs": {
                "months": {
                    "composite": {
                        "size": PAGE_SIZE,
                        "sources": [{"month": {"terms": {"field": "month"}}}],
                    }
                }
            },
        }
        if after:
            body["aggs"]["months"]["composite"]["after"] = after

        try:
            response = search(client, index_name, body, deadline)
        except NotFoundError:
            return []

        page = response["aggregations"]["months"]
        months.extend(
            date.fromisoformat(f"{bucket['key']['month']}-01")
            for bucket in page["buckets"]
        )
        after = page.get("after_key")
        if not after:
            return months


def split_period(platform, begin, end):
    requested = list(iter_months(begin, end))
    complete = set(available_months(platform))

    if not complete:
        return [], requested, []

    first_available = min(complete)
    available = [month for month in requested if month in complete]
    unavailable = [month for month in requested if month < first_available]
    pending = [
        month
        for month in requested
        if month not in complete and month not in unavailable
    ]

    return available, pending, unavailable
