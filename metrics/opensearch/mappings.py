_METRIC_PROPERTIES = {
    "total_requests": {"type": "long"},
    "total_investigations": {"type": "long"},
    "unique_requests": {"type": "long"},
    "unique_investigations": {"type": "long"},
}

_COUNTER_DIMENSIONS = {
    "metric_scope": {"type": "keyword"},
    "data_type": {"type": "keyword"},
    "parent_data_type": {"type": "keyword"},
    "article_version": {"type": "keyword"},
    "access_type": {"type": "keyword"},
    "access_method": {"type": "keyword"},
}


_BASE_METRIC_PROPERTIES = {
    "collection": {"type": "keyword"},
    "source_key": {"type": "keyword"},
    "document_key": {"type": "keyword"},
    "month": {"type": "date", "format": "yyyy-MM"},
    "applied_days": {
        "type": "keyword",
        "index": False,
        "doc_values": False,
    },
    **_COUNTER_DIMENSIONS,
    **_METRIC_PROPERTIES,
}


MONTH_INDEX_MAPPINGS = {
    "dynamic": False,
    "properties": {
        **_BASE_METRIC_PROPERTIES,
        "daily_metrics": {"type": "object", "dynamic": False},
    },
}

ANALYTICS_INDEX_MAPPINGS = {
    "dynamic": False,
    "_source": {
        "excludes": [
            "year",
            "source_key",
            "document_key",
            *_COUNTER_DIMENSIONS,
            "country_code",
            "content_language",
        ]
    },
    "properties": {
        "year": {"type": "keyword"},
        "source_key": {"type": "keyword"},
        "document_key": {"type": "keyword"},
        **_COUNTER_DIMENSIONS,
        "applied_day_masks": {
            "type": "long",
            "index": False,
            "doc_values": False,
        },
        "country_code": {"type": "keyword"},
        "content_language": {"type": "keyword"},
        **_METRIC_PROPERTIES,
    },
}

SOURCE_INDEX_MAPPINGS = {
    "dynamic": False,
    "properties": {
        "key": {"type": "keyword"},
        "collection": {"type": "keyword"},
        "source_id": {"type": "keyword"},
        "source_type": {"type": "keyword"},
        "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
        "scielo_issn": {"type": "keyword"},
        "acronym": {"type": "keyword"},
        "publisher_name": {"type": "keyword"},
        "access_type": {"type": "keyword"},
        "country": {"type": "keyword"},
        "subject_areas": {"type": "keyword"},
        "wos_subject_areas": {"type": "keyword"},
        "identifiers": {"type": "flat_object"},
        "active": {"type": "boolean"},
        "updated": {"type": "date"},
    },
}

DOCUMENT_INDEX_MAPPINGS = {
    "dynamic": False,
    "properties": {
        "key": {"type": "keyword"},
        "collection": {"type": "keyword"},
        "document_id": {"type": "keyword"},
        "document_type": {"type": "keyword"},
        "source_key": {"type": "keyword"},
        "parent_document_key": {"type": "keyword"},
        "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
        "publication_year": {"type": "integer"},
        "default_lang": {"type": "keyword"},
        "text_langs": {"type": "keyword"},
        "identifiers": {"type": "flat_object"},
        "active": {"type": "boolean"},
        "updated": {"type": "date"},
    },
}

_DATASET_MAPPINGS = {
    "counter": MONTH_INDEX_MAPPINGS,
    "analytics": ANALYTICS_INDEX_MAPPINGS,
    "sources": SOURCE_INDEX_MAPPINGS,
    "documents": DOCUMENT_INDEX_MAPPINGS,
}


def get_index_mappings(dataset):
    try:
        return _DATASET_MAPPINGS[dataset]
    except KeyError as exc:
        raise ValueError(f"Unknown OpenSearch dataset: {dataset}.") from exc


def get_index_settings(primary_shards=1):
    if primary_shards <= 0:
        raise ValueError("OpenSearch primary shards must be greater than zero.")

    return {
        "index": {
            "number_of_shards": primary_shards,
            "number_of_replicas": 0,
            "codec": "best_compression",
        }
    }
