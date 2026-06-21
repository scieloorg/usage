DISPLAY_TEXT_MAPPING = {
    "type": "text",
    "index": False,
}

IDENTIFIERS_MAPPING = {"type": "object", "dynamic": True}

DOCUMENT_MAPPINGS = {
    "properties": {
        "id": {"type": "keyword"},
        "type": {"type": "keyword"},
        "title": DISPLAY_TEXT_MAPPING,
        "parent_id": {"type": "keyword"},
        "publication_year": {"type": "integer"},
        "identifiers": IDENTIFIERS_MAPPING,
    }
}

SOURCE_MAPPINGS = {
    "properties": {
        "id": {"type": "keyword"},
        "type": {"type": "keyword"},
        "title": DISPLAY_TEXT_MAPPING,
        "scielo_issn": {"type": "keyword"},
        "acronym": {"type": "keyword"},
        "publisher_name": DISPLAY_TEXT_MAPPING,
        "access_type": {"type": "keyword"},
        "city": {"type": "keyword"},
        "country": {"type": "keyword"},
        "subject_area_capes": {"type": "keyword"},
        "subject_area_wos": {"type": "keyword"},
        "identifiers": IDENTIFIERS_MAPPING,
    }
}

COUNTER_MAPPINGS = {
    "properties": {
        "metric_scope": {"type": "keyword"},
        "data_type": {"type": "keyword"},
        "parent_data_type": {"type": "keyword"},
        "article_version": {"type": "keyword"},
        "access_type": {"type": "keyword"},
        "access_method": {"type": "keyword"},
    }
}

MONTH_ACCESS_MAPPINGS = {
    "properties": {
        "month": {"type": "date", "format": "yyyy-MM"},
    }
}

YEAR_ACCESS_MAPPINGS = {
    "properties": {
        "year": {"type": "date", "format": "yyyy"},
        "country_code": {"type": "keyword"},
        "content_language": {"type": "keyword"},
    }
}

METRIC_PROPERTIES = {
    "total_requests": {"type": "integer"},
    "total_investigations": {"type": "integer"},
    "unique_requests": {"type": "integer"},
    "unique_investigations": {"type": "integer"},
}


def _build_index_mappings(granularity):
    properties = {
        "collection": {"type": "keyword"},
        "source": SOURCE_MAPPINGS,
        "document": DOCUMENT_MAPPINGS,
        "access": MONTH_ACCESS_MAPPINGS
        if granularity == "month"
        else YEAR_ACCESS_MAPPINGS,
        "counter": COUNTER_MAPPINGS,
        "applied_jobs": {"type": "keyword", "index": False},
        **METRIC_PROPERTIES,
    }
    if granularity == "month":
        properties["daily_metrics"] = {"type": "object", "dynamic": True}
    return {"properties": properties}


YEAR_INDEX_MAPPINGS = _build_index_mappings("year")
MONTH_INDEX_MAPPINGS = _build_index_mappings("month")
BOOKS_YEAR_INDEX_MAPPINGS = _build_index_mappings("year")
BOOKS_MONTH_INDEX_MAPPINGS = _build_index_mappings("month")


def get_index_mappings(collection, granularity):
    if granularity not in {"month", "year"}:
        raise ValueError("Granularity must be 'month' or 'year'.")

    if collection == "books":
        return (
            BOOKS_MONTH_INDEX_MAPPINGS
            if granularity == "month"
            else BOOKS_YEAR_INDEX_MAPPINGS
        )

    return MONTH_INDEX_MAPPINGS if granularity == "month" else YEAR_INDEX_MAPPINGS
