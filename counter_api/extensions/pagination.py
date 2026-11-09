from django.core import signing

from counter_api.exceptions import CounterAPIError

CURSOR_SALT = "counter_api.ranking.groups.v1"


def pagination_error(message):
    return CounterAPIError(3060, message, 400)


def cursor_scope(platform, begin, end, params):
    return {
        "platform": platform.acron3,
        "begin_date": begin.isoformat(),
        "end_date": end.isoformat(),
        **{
            name: params.get(name) or None
            for name in (
                "entity_type",
                "parent_type",
                "parent_id",
                "group_by",
                "country",
                "language",
                "yop",
                "subject_area",
            )
        },
        "metric_type": params.get("metric_type", "Total_Item_Requests"),
        "coverage_policy": params.get("coverage_policy", "allow_partial"),
    }


def read_cursor(cursor, scope):
    if cursor is None:
        return None

    try:
        payload = signing.loads(cursor, salt=CURSOR_SALT)
    except signing.BadSignature:
        raise pagination_error("Invalid ranking cursor")

    if not isinstance(payload, dict) or not isinstance(payload.get("after"), dict):
        raise pagination_error("Invalid ranking cursor")
    if payload.get("scope") != scope:
        raise pagination_error("Ranking cursor does not match the query")

    return payload["after"]


def next_cursor(after, scope):
    if after is None:
        return None

    return signing.dumps({"scope": scope, "after": after}, salt=CURSOR_SALT)
