import calendar

from django.conf import settings

from metrics.opensearch.mappings import MONTH_STATUS_INDEX_MAPPINGS
from metrics.opensearch.names import generate_month_status_index_name

MARK_DAY_SCRIPT = """
ctx._source.day_mask = (ctx._source.day_mask ?: 0L) | params.day_mask;
ctx._source.complete = ctx._source.day_mask == params.complete_mask;
"""


def _month_values(month_date):
    month = month_date.strftime("%Y-%m")
    days = calendar.monthrange(month_date.year, month_date.month)[1]

    return month, (1 << days) - 1


def mark_days_exported(search_client, collection, month_date, day_mask):
    index_name = generate_month_status_index_name(settings.OPENSEARCH_INDEX_NAME)
    search_client.create_alias_if_not_exists(index_name, MONTH_STATUS_INDEX_MAPPINGS)

    month, complete_mask = _month_values(month_date)

    search_client.client.update(
        index=index_name,
        id=f"{collection}:{month}",
        body={
            "script": {
                "source": MARK_DAY_SCRIPT,
                "params": {"day_mask": day_mask, "complete_mask": complete_mask},
            },
            "scripted_upsert": True,
            "upsert": {
                "collection": collection,
                "month": month,
                "day_mask": 0,
                "complete": False,
            },
        },
        retry_on_conflict=3,
        refresh="wait_for",
    )


def replace_month_status(search_client, collection, month_date, day_mask):
    index_name = generate_month_status_index_name(settings.OPENSEARCH_INDEX_NAME)
    search_client.create_alias_if_not_exists(index_name, MONTH_STATUS_INDEX_MAPPINGS)

    month, complete_mask = _month_values(month_date)

    search_client.client.index(
        index=index_name,
        id=f"{collection}:{month}",
        body={
            "collection": collection,
            "month": month,
            "day_mask": day_mask,
            "complete": day_mask == complete_mask,
        },
        refresh="wait_for",
    )
