import logging
from time import sleep

import requests
from articlemeta.client import RestfulClient, ThriftClient
from django.conf import settings


def fetch_article_counter_dict(
    from_date,
    until_date,
    offset=0,
    limit=1000,
    collection=None,
    issn=None,
):
    for attempt in range(1, settings.ARTICLEMETA_MAX_RETRIES + 1):
        params = {
            "from": from_date,
            "until": until_date,
            "offset": offset,
            "limit": limit,
        }

        if collection:
            params["collection"] = collection

        if issn:
            params["issn"] = issn

        response = requests.get(settings.ARTICLEMETA_COLLECT_URL, params=params)

        try:
            response.raise_for_status()
            logging.info(response.url)
        except requests.exceptions.HTTPError:
            logging.warning(
                "Failed to collect data from %s. Waiting %d seconds before retry %d of %d",
                response.url,
                settings.ARTICLEMETA_SLEEP_TIME,
                attempt,
                settings.ARTICLEMETA_MAX_RETRIES,
            )
            sleep(settings.ARTICLEMETA_SLEEP_TIME)
        else:
            return response.json()

    return {}


def iter_journals(collection="scl", mode="rest"):
    if mode == "rest":
        client = RestfulClient()
    elif mode == "thrift":
        client = ThriftClient()
    else:
        raise ValueError(f"Unsupported ArticleMeta mode: {mode}")

    for journal in client.journals(collection=collection):
        yield journal
