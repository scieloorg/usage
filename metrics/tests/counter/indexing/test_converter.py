from scielo_usage_counter.values import CONTENT_TYPE_ABSTRACT, CONTENT_TYPE_FULL_TEXT

from metrics.counter.indexing import converter


def _article(country="BR", language="pt", session="session-1"):
    return {
        "collection": "scl",
        "source_key": "0101-0101",
        "document_type": "article",
        "pid_v3": "abc123",
        "user_session_id": session,
        "click_timestamps": {"00:05": 1},
        "access_country_code": country,
        "content_language": language,
        "content_type": CONTENT_TYPE_FULL_TEXT,
        "access_date": "2026-08-20",
        "publication_year": "2025",
        "source": {
            "source_type": "journal",
            "source_id": "0101-0101",
            "main_title": "Journal title that must not be copied",
        },
        "document": {"title": "Article title that must not be copied"},
    }


def test_counter_facts_are_monthly_and_reference_metadata_keys():
    documents = dict(converter.iter_partitioned_values([_article()], "counter"))

    assert len(documents) == 1
    document_id, document = next(iter(documents.items()))
    assert document_id.startswith("k1_")
    assert document["month"] == "2026-08"
    assert document["publication_year"] == 2025
    assert document["data_type"] == "Article"
    assert document["parent_data_type"] == "Journal"
    assert document["total_requests"] == 1
    assert document["unique_requests"] == 1
    assert document["source_key"].startswith("k1_")
    assert document["document_key"].startswith("k1_")
    assert "source" not in document
    assert "document" not in document
    assert "country_code" not in document
    assert "content_language" not in document
    assert "year" not in document


def test_analytics_builds_annual_country_and_language_matrix():
    values = [
        _article(country="BR", language="pt", session="same-session"),
        _article(country="US", language="pt", session="same-session"),
    ]
    documents = list(converter.iter_partitioned_values(values, "analytics"))

    assert len(documents) == 2
    assert {item["year"] for _key, item in documents} == {"2026"}
    assert {item["country_code"] for _key, item in documents} == {"BR", "US"}
    assert {item["content_language"] for _key, item in documents} == {"pt"}
    assert all("collection" not in item for _key, item in documents)
    assert all(item["source_key"].startswith("k1_") for _key, item in documents)
    assert all(item["document_key"].startswith("k1_") for _key, item in documents)
    assert all("month" not in item for _key, item in documents)
    assert all("counter_key" not in item for _key, item in documents)
    assert all("projection" not in item for _key, item in documents)
    assert all("daily_metrics" not in item for _key, item in documents)


def test_analytics_combines_the_same_dimensions_across_months():
    january = _article()
    february = {**_article(), "access_date": "2026-02-20"}

    documents = dict(
        converter.iter_partitioned_values([january, february], "analytics")
    )

    assert len(documents) == 1
    document = next(iter(documents.values()))
    assert document["year"] == "2026"
    assert document["total_requests"] == 2


def test_book_and_chapter_keep_item_and_title_scopes():
    chapter = {
        **_article(),
        "collection": "books",
        "source_key": "book-1",
        "document_type": "chapter",
        "pid_v3": None,
        "pid_generic": "BOOK:BOOK-1/CHAPTER:01",
        "title_pid_generic": "BOOK:BOOK-1",
        "source": {"source_type": "book", "source_id": "book-1"},
    }

    documents = dict(converter.iter_partitioned_values([chapter], "counter"))

    assert len(documents) == 2
    assert {item["metric_scope"] for item in documents.values()} == {"item", "title"}
    assert {item["data_type"] for item in documents.values()} == {
        "Book",
        "Book_Segment",
    }
    assert all(item["total_requests"] == 1 for item in documents.values())
    assert all(item["publication_year"] == 2025 for item in documents.values())


def test_book_investigation_counts_item_and_title_scopes():
    book = {
        **_article(),
        "collection": "books",
        "source_key": "book-1",
        "document_type": "book",
        "pid_v3": None,
        "pid_generic": "BOOK:BOOK-1",
        "title_pid_generic": "BOOK:BOOK-1",
        "content_type": CONTENT_TYPE_ABSTRACT,
        "source": {"source_type": "book", "source_id": "book-1"},
    }

    documents = dict(converter.iter_partitioned_values([book], "counter"))

    assert len(documents) == 2
    assert {item["metric_scope"] for item in documents.values()} == {"item", "title"}
    assert all(item["total_investigations"] == 1 for item in documents.values())
    assert all(item["unique_investigations"] == 1 for item in documents.values())


def test_whole_book_request_counts_each_identified_chapter_once():
    book = {
        **_article(),
        "collection": "books",
        "source_key": "book-1",
        "document_type": "book",
        "pid_v3": None,
        "pid_generic": "BOOK:BOOK-1",
        "title_pid_generic": "BOOK:BOOK-1",
        "segment_pid_generics": [
            "BOOK:BOOK-1/CHAPTER:01",
            "BOOK:BOOK-1/CHAPTER:02",
            "BOOK:BOOK-1/CHAPTER:03",
        ],
        "source": {"source_type": "book", "source_id": "book-1"},
    }
    chapter = {
        **book,
        "document_type": "chapter",
        "pid_generic": "BOOK:BOOK-1/CHAPTER:01",
        "segment_pid_generics": [],
    }

    for dataset in ("counter", "analytics"):
        documents = dict(converter.iter_partitioned_values([book, chapter], dataset))
        items = [item for item in documents.values() if item["metric_scope"] == "item"]
        titles = [
            item for item in documents.values() if item["metric_scope"] == "title"
        ]

        assert len(items) == 3
        assert len(titles) == 1
        assert sum(item["total_requests"] for item in items) == 4
        assert sum(item["unique_requests"] for item in items) == 3
        assert titles[0]["total_requests"] == 2
        assert titles[0]["unique_requests"] == 1


def test_whole_book_without_identifiable_chapters_counts_one_item():
    book = {
        **_article(),
        "collection": "books",
        "source_key": "book-1",
        "document_type": "book",
        "pid_v3": None,
        "pid_generic": "BOOK:BOOK-1",
        "title_pid_generic": "BOOK:BOOK-1",
        "segment_pid_generics": [],
        "source": {"source_type": "book", "source_id": "book-1"},
    }

    documents = dict(converter.iter_partitioned_values([book], "counter"))

    assert len(documents) == 2
    assert {item["metric_scope"] for item in documents.values()} == {"item", "title"}
    assert all(item["total_requests"] == 1 for item in documents.values())


def test_compact_keys_and_output_are_deterministic():
    first = list(converter.iter_partitioned_values([_article()], "counter"))
    second = list(converter.iter_partitioned_values([_article()], "counter"))
    assert first == second


def test_empty_iterable_returns_empty():
    assert list(converter.iter_partitioned_values((), "counter")) == []
