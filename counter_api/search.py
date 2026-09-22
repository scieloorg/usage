from time import monotonic

from opensearchpy import NotFoundError
from opensearchpy.exceptions import OpenSearchException

from counter_api.exceptions import service_unavailable


def remaining_time(deadline, limit=None):
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise service_unavailable()
    if limit is not None:
        return min(remaining, limit)
    return remaining


def search(client, index_name, body, deadline, limit=None):
    timeout = remaining_time(deadline, limit)
    body["timeout"] = f"{max(1, int(timeout * 1000))}ms"
    try:
        response = client.search(
            index=index_name,
            body=body,
            request_timeout=timeout,
        )
    except NotFoundError:
        raise
    except OpenSearchException:
        raise service_unavailable()

    if response.get("timed_out") or response.get("_shards", {}).get("failed"):
        raise service_unavailable()

    return response


def composite_pages(client, index_name, body, deadline):
    after = None

    while True:
        if after:
            body["aggs"]["rows"]["composite"]["after"] = after

        response = search(client, index_name, body, deadline)
        page = response["aggregations"]["rows"]

        yield page.get("buckets", [])

        after = page.get("after_key")
        if not after:
            return
