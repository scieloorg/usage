from elasticsearch import Elasticsearch, helpers, NotFoundError
from django.conf import settings

import logging


def get_elasticsearch_client(url=None, basic_auth=None, api_key=None):
    """
    Create an Elasticsearch client instance using Django settings.

    :param url: Elasticsearch URL. If None, it will be taken from Django settings.
    :param basic_auth: Basic authentication credentials. If None, it will be taken from Django settings.
    :param api_key: API key. If None, it will be taken from Django settings.
    """
    if not url:
        url = getattr(settings, "ES_URL", None)

    if not basic_auth:
        basic_auth = getattr(settings, "ES_BASIC_AUTH", None)

    if not api_key:
        api_key = getattr(settings, "ES_API_KEY", None)

    if basic_auth:
        client = Elasticsearch(url, basic_auth=basic_auth)
    elif api_key:
        client = Elasticsearch(url, api_key=api_key)
    else:
        client = Elasticsearch(url)

    return client
