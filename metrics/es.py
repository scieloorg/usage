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


def create_index(index_name, mappings=None, client=None, url=None, basic_auth=None, api_key=None):
    """
    Create an Elasticsearch index. 

    :param index_name: Name of the index to create.
    :param mappings: Mappings for the index. If None, default mappings will be used.
    :param client: Elasticsearch client instance. If None, a new client will be created.
    :param url: Elasticsearch URL. If None, it will be taken from Django settings.
    :param basic_auth: Basic authentication credentials. If None, it will be taken from Django settings.
    :param api_key: API key. If None, it will be taken from Django settings.
    """
    if not client:
        client = get_elasticsearch_client(url, basic_auth, api_key)

    if not mappings:
        mappings = {
            "properties": {
                "collection": {
                    "type": "keyword"
                },
                "journal": {
                    "type": "keyword"
                },
                "pid_v2": {
                    "type": "keyword"
                },
                "pid_v3": {
                    "type": "keyword"
                },
                "pid_generic": {
                    "type": "keyword"
                },
                "media_language": {
                    "type": "keyword"
                },
                "country_code": {
                    "type": "keyword"
                },
                "date": {
                    "type": "date",
                    "format": "yyyy-MM-dd"
                },
                "year": {
                    "type": "integer"
                },
                "month": {
                    "type": "integer"
                },
                "day": {
                    "type": "integer"
                },
                "total_requests": {
                    "type": "integer"
                },
                "total_investigations": {
                    "type": "integer"
                },
                "unique_requests": {
                    "type": "integer"
                },
                "unique_investigations": {
                    "type": "integer"
                }
            }
        }

    resp = client.indices.create(
        index=index_name,
        mappings=mappings,
    )
    logging.info(f"Index {index_name} created: {resp}")


def delete_index(index_name, client=None, url=None, basic_auth=None, api_key=None):
    """
    Delete an Elasticsearch index.

    :param index_name: Name of the index to delete.
    :param client: Elasticsearch client instance. If None, a new client will be created.
    :param url: Elasticsearch URL. If None, it will be taken from Django settings.
    :param basic_auth: Basic authentication credentials. If None, it will be taken from Django settings.
    :param api_key: API key. If None, it will be taken from Django settings.
    """
    if not client:
        client = get_elasticsearch_client(url, basic_auth, api_key)
    client.indices.delete(index=index_name)


def index_document(index_name, doc_id, document, client=None, url=None, basic_auth=None, api_key=None):
    """
    Index a document in Elasticsearch.

    :param index_name: Name of the index.
    :param doc_id: ID of the document.
    :param document: Document to index.
    :param client: Elasticsearch client instance. If None, a new client will be created.
    :param url: Elasticsearch URL. If None, it will be taken from Django settings.
    :param basic_auth: Basic authentication credentials. If None, it will be taken from Django settings.
    :param api_key: API key. If None, it will be taken from Django settings.
    """
    if not client:
        client = get_elasticsearch_client(url, basic_auth, api_key)
    client.index(index=index_name, id=doc_id, document=document)

