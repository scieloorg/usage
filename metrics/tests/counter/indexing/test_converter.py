import unittest

from scielo_usage_counter.values import (
    CONTENT_TYPE_ABSTRACT,
    CONTENT_TYPE_FULL_TEXT,
    DEFAULT_SCIELO_ISSN,
    MEDIA_FORMAT_HTML,
)

from metrics.counter.indexing import converter as index_docs


class TestConverter(unittest.TestCase):
    def test_creates_month_and_year_views_for_book_chapter(self):
        data = {
            "books|q7gtd|||BOOK:Q7GTD/CHAPTER:03|browser|1.0|127.0.0.1|BR|en|html|full_text": {
                "collection": "books",
                "source_key": "q7gtd",
                "document_type": "chapter",
                "pid_v2": None,
                "pid_v3": None,
                "pid_generic": "BOOK:Q7GTD/CHAPTER:03",
                "document": {"title": "Chapter Title"},
                "title_pid_generic": "BOOK:Q7GTD",
                "user_session_id": "browser|1.0|127.0.0.1|2024-01-15|10",
                "click_timestamps": {"00:05": 1},
                "access_country_code": "BR",
                "content_language": "en",
                "content_type": CONTENT_TYPE_FULL_TEXT,
                "access_date": "2024-01-15",
                "access_month": "202401",
                "access_year": "2024",
                "source": {
                    "source_type": "book",
                    "source_id": "q7gtd",
                    "scielo_issn": DEFAULT_SCIELO_ISSN,
                    "main_title": "Book Title",
                    "identifiers": {"book_id": "q7gtd", "isbn": "9788578791889"},
                    "city": "Sao Paulo",
                    "country": "BR",
                    "subject_area_capes": [],
                    "subject_area_wos": [],
                    "acronym": None,
                    "publisher_name": ["SciELO Books"],
                },
                "publication_year": "2023",
            }
        }

        metrics_data = index_docs.convert(data)

        self.assertEqual(set(metrics_data.keys()), {"month", "year"})
        self.assertEqual(len(metrics_data["month"]), 2)
        self.assertEqual(len(metrics_data["year"]), 2)

        month_item = metrics_data["month"][
            "books|q7gtd|||BOOK:Q7GTD/CHAPTER:03|2024-01|Open|Regular|2023"
        ]
        self.assertEqual(month_item["access"], {"month": "2024-01"})
        self.assertIn("daily_metrics", month_item)
        self.assertNotIn("access_country_code", month_item)
        self.assertNotIn("content_language", month_item)
        self.assertEqual(month_item["document"]["id"], "BOOK:Q7GTD/CHAPTER:03")
        self.assertEqual(month_item["document"]["type"], "chapter")
        self.assertEqual(month_item["document"]["title"], "Chapter Title")
        self.assertEqual(month_item["document"]["parent_id"], "BOOK:Q7GTD")
        self.assertEqual(month_item["document"]["publication_year"], "2023")
        self.assertEqual(month_item["document"]["identifiers"]["book_id"], "q7gtd")
        self.assertEqual(month_item["document"]["identifiers"]["chapter_id"], "03")
        self.assertEqual(month_item["document"]["identifiers"]["isbn"], "9788578791889")
        self.assertNotIn("pid_generic", month_item["document"]["identifiers"])
        self.assertEqual(month_item["counter"]["metric_scope"], "item")
        self.assertEqual(month_item["counter"]["data_type"], "Book_Segment")
        self.assertEqual(month_item["total_requests"], 1)
        self.assertEqual(month_item["unique_requests"], 1)
        self.assertNotIn("scielo_issn", month_item["source"])
        self.assertNotIn("book_id", month_item["source"].get("identifiers", {}))
        self.assertEqual(month_item["source"]["publisher_name"], ["SciELO Books"])

        month_title = metrics_data["month"][
            "title|books|q7gtd|||BOOK:Q7GTD|2024-01|Open|Regular|2023"
        ]
        self.assertEqual(month_title["document"]["id"], "BOOK:Q7GTD")
        self.assertEqual(month_title["document"]["type"], "book")
        self.assertEqual(month_title["document"]["title"], "Book Title")
        self.assertNotIn("parent_id", month_title["document"])
        self.assertEqual(month_title["counter"]["metric_scope"], "title")
        self.assertEqual(month_title["counter"]["data_type"], "Book")
        self.assertEqual(month_title["total_requests"], 1)
        self.assertEqual(month_title["total_investigations"], 1)
        self.assertEqual(month_title["unique_requests"], 1)
        self.assertEqual(month_title["unique_investigations"], 1)

        year_item = metrics_data["year"][
            "books|q7gtd|||BOOK:Q7GTD/CHAPTER:03|en|BR|2024|Open|Regular|2023"
        ]
        self.assertEqual(
            year_item["access"],
            {"year": "2024", "country_code": "BR", "content_language": "en"},
        )
        self.assertNotIn("daily_metrics", year_item)
        self.assertEqual(year_item["document"]["title"], "Chapter Title")
        self.assertEqual(year_item["counter"]["metric_scope"], "item")
        self.assertEqual(year_item["total_requests"], 1)

        year_title = metrics_data["year"][
            "title|books|q7gtd|||BOOK:Q7GTD|en|BR|2024|Open|Regular|2023"
        ]
        self.assertEqual(year_title["counter"]["metric_scope"], "title")
        self.assertEqual(year_title["document"]["title"], "Book Title")
        self.assertNotIn("daily_metrics", year_title)
        self.assertEqual(year_title["total_requests"], 1)
        self.assertEqual(year_title["total_investigations"], 1)
        self.assertEqual(year_title["unique_requests"], 1)
        self.assertEqual(year_title["unique_investigations"], 1)

    def test_maps_counter_data_types_for_preprint_and_dataset(self):
        data = {
            "preprints|scielo-preprints|||10.1590/SCIELOPREPRINTS.1234|sess|BR|un|html|full_text": {
                "collection": "preprints",
                "source_key": "scielo-preprints",
                "document_type": "preprint",
                "pid_generic": "10.1590/SCIELOPREPRINTS.1234",
                "user_session_id": "browser|1.0|127.0.0.1|2024-01-15|10",
                "click_timestamps": {"00:05": 1},
                "access_country_code": "BR",
                "content_language": "un",
                "content_type": CONTENT_TYPE_FULL_TEXT,
                "access_date": "2024-01-15",
                "access_year": "2024",
                "source": {
                    "source_type": "preprint_server",
                    "source_id": "scielo-preprints",
                    "main_title": "SciELO Preprints",
                },
                "publication_year": "2024",
            },
            "data|scielo-data|||10.48331/SCIELODATA.ABC123|sess|BR|un|html|abstract": {
                "collection": "data",
                "source_key": "scielo-data",
                "document_type": "dataset",
                "pid_generic": "10.48331/SCIELODATA.ABC123",
                "user_session_id": "browser|1.0|127.0.0.1|2024-01-15|10",
                "click_timestamps": {"00:05": 1},
                "access_country_code": "BR",
                "content_language": "un",
                "content_type": CONTENT_TYPE_ABSTRACT,
                "access_date": "2024-01-15",
                "access_year": "2024",
                "source": {
                    "source_type": "data_repository",
                    "source_id": "scielo-data",
                    "main_title": "SciELO Data",
                },
                "publication_year": "2024",
            },
        }

        metrics_data = index_docs.convert(data)
        preprint_doc = metrics_data["month"][
            "preprints|scielo-preprints|||10.1590/SCIELOPREPRINTS.1234|2024-01|Open|Regular|2024"
        ]
        dataset_doc = metrics_data["month"][
            "data|scielo-data|||10.48331/SCIELODATA.ABC123|2024-01|Open|Regular|2024"
        ]

        self.assertEqual(preprint_doc["counter"]["data_type"], "Article")
        self.assertEqual(preprint_doc["document"]["type"], "preprint")
        self.assertEqual(preprint_doc["document"]["id"], "10.1590/SCIELOPREPRINTS.1234")
        self.assertEqual(preprint_doc["counter"]["article_version"], "Preprint")
        self.assertEqual(dataset_doc["counter"]["data_type"], "Dataset")
        self.assertNotIn("article_version", dataset_doc["counter"])

    def test_dedupes_book_unique_item_across_formats(self):
        data = {
            "books|c2248|||BOOK:C2248/CHAPTER:03|sess|BR|pt|html|full_text": {
                "collection": "books",
                "source_key": "c2248",
                "document_type": "chapter",
                "pid_v2": None,
                "pid_v3": None,
                "pid_generic": "BOOK:C2248/CHAPTER:03",
                "title_pid_generic": "BOOK:C2248",
                "user_session_id": "browser|1.0|127.0.0.1|2024-01-15|10",
                "click_timestamps": {"00:05": 1},
                "access_country_code": "BR",
                "content_language": "pt",
                "content_type": CONTENT_TYPE_FULL_TEXT,
                "access_date": "2024-01-15",
                "access_month": "202401",
                "access_year": "2024",
                "source": {
                    "source_type": "book",
                    "source_id": "c2248",
                    "main_title": "C2248 Book",
                    "identifiers": {"book_id": "c2248", "isbn": "9788599662830"},
                    "publisher_name": ["SciELO Books"],
                },
                "publication_year": "2018",
            },
            "books|c2248|||BOOK:C2248/CHAPTER:03|sess|BR|pt|pdf|full_text": {
                "collection": "books",
                "source_key": "c2248",
                "document_type": "chapter",
                "pid_v2": None,
                "pid_v3": None,
                "pid_generic": "BOOK:C2248/CHAPTER:03",
                "title_pid_generic": "BOOK:C2248",
                "user_session_id": "browser|1.0|127.0.0.1|2024-01-15|10",
                "click_timestamps": {"00:45": 1},
                "access_country_code": "BR",
                "content_language": "pt",
                "content_type": CONTENT_TYPE_FULL_TEXT,
                "access_date": "2024-01-15",
                "access_month": "202401",
                "access_year": "2024",
                "source": {
                    "source_type": "book",
                    "source_id": "c2248",
                    "main_title": "C2248 Book",
                    "identifiers": {"book_id": "c2248", "isbn": "9788599662830"},
                    "publisher_name": ["SciELO Books"],
                },
                "publication_year": "2018",
            },
        }

        metrics_data = index_docs.convert(data)
        month_item = metrics_data["month"][
            "books|c2248|||BOOK:C2248/CHAPTER:03|2024-01|Open|Regular|2018"
        ]
        month_title = metrics_data["month"][
            "title|books|c2248|||BOOK:C2248|2024-01|Open|Regular|2018"
        ]

        self.assertEqual(month_item["total_requests"], 2)
        self.assertEqual(month_item["total_investigations"], 2)
        self.assertEqual(month_item["unique_requests"], 1)
        self.assertEqual(month_item["unique_investigations"], 1)
        self.assertEqual(month_title["unique_requests"], 1)
        self.assertEqual(month_title["unique_investigations"], 1)

    def test_skips_book_landing_page_from_item_scope(self):
        data = {
            "books|c2248|||BOOK:C2248|sess|BR|pt|html|abstract": {
                "collection": "books",
                "source_key": "c2248",
                "document_type": "book",
                "pid_v2": None,
                "pid_v3": None,
                "pid_generic": "BOOK:C2248",
                "document": {"title": "C2248 Book"},
                "title_pid_generic": "BOOK:C2248",
                "user_session_id": "browser|1.0|127.0.0.1|2024-01-15|10",
                "click_timestamps": {"00:05": 1},
                "access_country_code": "BR",
                "content_language": "pt",
                "content_type": CONTENT_TYPE_ABSTRACT,
                "access_date": "2024-01-15",
                "access_month": "202401",
                "access_year": "2024",
                "source": {
                    "source_type": "book",
                    "source_id": "c2248",
                    "main_title": "C2248 Book",
                    "identifiers": {"book_id": "c2248", "isbn": "9788599662830"},
                    "publisher_name": ["SciELO Books"],
                },
                "publication_year": "2018",
            },
        }

        metrics_data = index_docs.convert(data)
        self.assertEqual(
            set(metrics_data["month"].keys()),
            {"title|books|c2248|||BOOK:C2248|2024-01|Open|Regular|2018"},
        )
        self.assertEqual(
            set(metrics_data["year"].keys()),
            {"title|books|c2248|||BOOK:C2248|pt|BR|2024|Open|Regular|2018"},
        )

    def test_whole_book_without_segments_counts_as_book_segment(self):
        data = {
            "books|c2248|||BOOK:C2248|sess|BR|pt|pdf|full_text": {
                "collection": "books",
                "source_key": "c2248",
                "document_type": "book",
                "pid_v2": None,
                "pid_v3": None,
                "pid_generic": "BOOK:C2248",
                "document": {"title": "C2248 Book"},
                "title_pid_generic": "BOOK:C2248",
                "user_session_id": "browser|1.0|127.0.0.1|2024-01-15|10",
                "click_timestamps": {"00:05": 1},
                "access_country_code": "BR",
                "content_language": "pt",
                "content_type": CONTENT_TYPE_FULL_TEXT,
                "access_date": "2024-01-15",
                "access_month": "202401",
                "access_year": "2024",
                "source": {
                    "source_type": "book",
                    "source_id": "c2248",
                    "main_title": "C2248 Book",
                    "identifiers": {"book_id": "c2248"},
                    "publisher_name": ["SciELO Books"],
                },
                "publication_year": "2018",
            },
        }

        metrics_data = index_docs.convert(data)
        month_item = metrics_data["month"][
            "books|c2248|||BOOK:C2248|2024-01|Open|Regular|2018"
        ]
        month_title = metrics_data["month"][
            "title|books|c2248|||BOOK:C2248|2024-01|Open|Regular|2018"
        ]

        self.assertEqual(month_item["counter"]["data_type"], "Book_Segment")
        self.assertEqual(month_item["counter"]["metric_scope"], "item")
        self.assertEqual(month_item["document"]["id"], "BOOK:C2248")
        self.assertNotIn("parent_id", month_item["document"])
        self.assertEqual(month_title["counter"]["data_type"], "Book")
        self.assertEqual(month_title["counter"]["metric_scope"], "title")

    def test_aggregates_multiple_chapters_at_title_level(self):
        data = {
            "books|q7gtd|||BOOK:Q7GTD/CHAPTER:01|session1|BR|en|html|full_text": {
                "collection": "books",
                "source_key": "q7gtd",
                "document_type": "chapter",
                "pid_generic": "BOOK:Q7GTD/CHAPTER:01",
                "title_pid_generic": "BOOK:Q7GTD",
                "user_session_id": "session1",
                "click_timestamps": {"00:05": 1},
                "content_type": CONTENT_TYPE_FULL_TEXT,
                "access_date": "2024-01-15",
                "access_year": "2024",
                "source": {
                    "source_type": "book",
                    "source_id": "q7gtd",
                    "scielo_issn": DEFAULT_SCIELO_ISSN,
                    "main_title": "Book Title",
                    "identifiers": {"book_id": "q7gtd"},
                    "publisher_name": ["SciELO Books"],
                },
                "publication_year": "2023",
            },
            "books|q7gtd|||BOOK:Q7GTD/CHAPTER:02|session1|BR|en|html|full_text": {
                "collection": "books",
                "source_key": "q7gtd",
                "document_type": "chapter",
                "pid_generic": "BOOK:Q7GTD/CHAPTER:02",
                "title_pid_generic": "BOOK:Q7GTD",
                "user_session_id": "session1",
                "click_timestamps": {"00:10": 1},
                "content_type": CONTENT_TYPE_FULL_TEXT,
                "access_date": "2024-01-15",
                "access_year": "2024",
                "source": {
                    "source_type": "book",
                    "source_id": "q7gtd",
                    "scielo_issn": DEFAULT_SCIELO_ISSN,
                    "main_title": "Book Title",
                    "identifiers": {"book_id": "q7gtd"},
                    "publisher_name": ["SciELO Books"],
                },
                "publication_year": "2023",
            },
        }

        metrics_data = index_docs.convert(data)
        self.assertEqual(len(metrics_data["month"]), 3)
        self.assertEqual(len(metrics_data["year"]), 3)

        month_title = metrics_data["month"][
            "title|books|q7gtd|||BOOK:Q7GTD|2024-01|Open|Regular|2023"
        ]
        self.assertEqual(month_title["total_requests"], 2)
        self.assertEqual(month_title["total_investigations"], 2)
        self.assertEqual(month_title["unique_requests"], 1)
        self.assertEqual(month_title["unique_investigations"], 1)

    def test_double_click_collapses_same_url_within_30_seconds(self):
        from datetime import datetime

        from metrics.counter.access import accumulation

        results = {}
        counter_access = {
            "collection": "books",
            "source_type": "book",
            "source_id": "c2248",
            "scielo_issn": DEFAULT_SCIELO_ISSN,
            "pid_v2": None,
            "pid_v3": None,
            "pid_generic": "BOOK:C2248/CHAPTER:03",
            "title_pid_generic": "BOOK:C2248",
            "media_language": "pt",
            "media_format": MEDIA_FORMAT_HTML,
            "content_type": CONTENT_TYPE_FULL_TEXT,
            "publication_year": "2018",
            "source_main_title": "C2248 Book",
        }
        base_line = {
            "client_name": "browser",
            "client_version": "1.0",
            "ip_address": "127.0.0.1",
            "country_code": "BR",
            "url": "/id/c2248/03?from=search",
        }

        accumulation.accumulate(
            results,
            counter_access,
            {**base_line, "local_datetime": datetime(2024, 1, 15, 10, 0, 5)},
        )
        accumulation.accumulate(
            results,
            counter_access,
            {**base_line, "local_datetime": datetime(2024, 1, 15, 10, 0, 20)},
        )

        metrics_data = index_docs.convert(results)
        month_item = metrics_data["month"][
            "books|c2248|||BOOK:C2248/CHAPTER:03|2024-01|Open|Regular|2018"
        ]
        self.assertEqual(month_item["total_requests"], 1)
        self.assertEqual(month_item["unique_requests"], 1)

    def test_article_pipeline_sets_journal_parent(self):
        data = {
            "scl|1234-5678||abc123||sess|BR|en|pdf|full_text": {
                "collection": "scl",
                "source_key": "1234-5678",
                "document_type": "article",
                "pid_v2": None,
                "pid_v3": "abc123",
                "pid_generic": None,
                "document": {"title": "Article Title"},
                "user_session_id": "sess",
                "click_timestamps": {"00:05": 1},
                "access_country_code": "BR",
                "content_language": "en",
                "content_type": CONTENT_TYPE_FULL_TEXT,
                "access_date": "2024-01-15",
                "access_year": "2024",
                "source": {
                    "source_type": "journal",
                    "source_id": "1234-5678",
                    "scielo_issn": "1234-5678",
                    "main_title": "Test Journal",
                },
                "publication_year": "2024",
            }
        }

        metrics_data = index_docs.convert(data)
        month_doc = list(metrics_data["month"].values())[0]

        self.assertEqual(month_doc["counter"]["data_type"], "Article")
        self.assertEqual(month_doc["counter"]["parent_data_type"], "Journal")
        self.assertEqual(month_doc["counter"]["metric_scope"], "item")
        self.assertEqual(month_doc["document"]["type"], "article")
        self.assertEqual(month_doc["total_requests"], 1)
        self.assertEqual(month_doc["total_investigations"], 1)

    def test_non_dict_input_returns_empty(self):
        result = index_docs.convert(None)
        self.assertEqual(result, {"month": {}, "year": {}})
