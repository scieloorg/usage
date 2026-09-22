DOWNLOAD_FORMATS = ("json", "csv", "xlsx")
SEGMENT_DIMENSIONS = {"country", "language"}
RANKING_GROUPS = {"", "country", "language", "country,language"}
RANKING_ENTITIES = {
    "journals": {
        "collection_type": "journals",
        "parent_type": "collection",
        "key_field": "source_key",
        "metadata": "sources",
    },
    "books": {
        "collection_type": "books",
        "parent_type": "collection",
        "key_field": "source_key",
        "metadata": "sources",
    },
    "articles": {
        "collection_type": "journals",
        "parent_type": "journal",
        "key_field": "document_key",
        "metadata": "documents",
        "data_type": "Article",
    },
    "chapters": {
        "collection_type": "books",
        "parent_type": "book",
        "key_field": "document_key",
        "metadata": "documents",
        "data_type": "Book_Segment",
    },
    "preprints": {
        "collection_type": "preprints",
        "parent_type": "collection",
        "key_field": "document_key",
        "metadata": "documents",
    },
    "datasets": {
        "collection_type": "data",
        "parent_type": "collection",
        "key_field": "document_key",
        "metadata": "documents",
    },
}
DISTRIBUTION_DIMENSIONS = {
    "country": "country_code",
    "language": "content_language",
    "yop": "publication_year",
    "subject_area": "source_key",
    "journal": "source_key",
}
DISTRIBUTION_CROSSES = (
    ("country", "language"),
    ("country", "yop"),
    ("language", "yop"),
    ("journal", "language"),
)
DISTRIBUTION_ENTITIES = {
    "collection": {},
    "journal": {
        "collection_type": "journals",
        "key_field": "source_key",
        "report_id": "tr",
    },
    "book": {
        "collection_type": "books",
        "key_field": "source_key",
        "report_id": "tr",
    },
    "article": {
        "collection_type": "journals",
        "key_field": "document_key",
        "report_id": "ir",
        "data_type": "Article",
    },
    "chapter": {
        "collection_type": "books",
        "key_field": "document_key",
        "report_id": "ir",
        "data_type": "Book_Segment",
    },
    "preprint": {
        "collection_type": "preprints",
        "key_field": "document_key",
        "report_id": "ir",
    },
    "dataset": {
        "collection_type": "data",
        "key_field": "document_key",
        "report_id": "ir",
    },
}
DISTRIBUTION_CAPABILITIES = (
    *DISTRIBUTION_DIMENSIONS,
    *(",".join(dimensions) for dimensions in DISTRIBUTION_CROSSES),
)
