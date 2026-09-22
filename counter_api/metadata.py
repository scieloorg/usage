from django.conf import settings
from opensearchpy import NotFoundError

from counter_api.constants import METADATA_BATCH_SIZE
from counter_api.search import remaining_time
from metrics.opensearch.names import generate_metadata_alias


def fetch_metadata(client, entity, keys, deadline):
    if not keys:
        return {}

    index_name = generate_metadata_alias(settings.OPENSEARCH_INDEX_NAME, entity)
    documents = {}
    keys = sorted(set(keys))

    for start in range(0, len(keys), METADATA_BATCH_SIZE):
        remaining = remaining_time(deadline)

        batch = keys[start : start + METADATA_BATCH_SIZE]
        try:
            response = client.mget(
                index=index_name,
                body={"ids": batch},
                request_timeout=remaining,
            )
        except NotFoundError:
            return documents

        for document in response.get("docs", []):
            if document.get("found"):
                documents[document["_id"]] = document["_source"]

    return documents
