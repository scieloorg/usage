import unittest

from scielo_usage_counter.values import (
    CONTENT_TYPE_ABSTRACT,
    CONTENT_TYPE_FULL_TEXT,
    DEFAULT_SCIELO_ISSN,
    MEDIA_FORMAT_HTML,
    MEDIA_FORMAT_PDF,
)

from metrics.counter.access import extraction


class TestExtraction(unittest.TestCase):
    def test_normalizes_source_fields_for_journal(self):
        data = extraction.extract(
            "scl",
            {
                "scielo_issn": "1234-5678",
                "pid_v2": "S0102-67202020000100001",
                "media_language": "en",
                "media_format": MEDIA_FORMAT_PDF,
                "content_type": CONTENT_TYPE_FULL_TEXT,
                "publication_year": "2024",
                "journal_main_title": "Journal Title",
                "journal_subject_area_capes": ["Health Sciences"],
                "journal_subject_area_wos": ["Medicine"],
                "journal_acronym": "testjou",
                "journal_publisher_name": ["SciELO"],
            },
        )

        self.assertEqual(data["source_type"], "journal")
        self.assertEqual(data["source_id"], "1234-5678")
        self.assertEqual(data["source_main_title"], "Journal Title")
        self.assertEqual(data["source_acronym"], "testjou")

    def test_normalizes_source_fields_for_books(self):
        data = extraction.extract(
            "books",
            {
                "source_type": "book",
                "source_id": "q7gtd",
                "document_type": "chapter",
                "book_id": "q7gtd",
                "book_title": "Book Title",
                "title_pid_generic": "book:q7gtd",
                "pid_generic": "book:q7gtd/chapter:03",
                "media_language": "en",
                "media_format": MEDIA_FORMAT_HTML,
                "content_type": CONTENT_TYPE_FULL_TEXT,
                "publication_year": "2023",
            },
        )

        self.assertEqual(data["source_type"], "book")
        self.assertEqual(data["source_id"], "q7gtd")
        self.assertEqual(data["scielo_issn"], DEFAULT_SCIELO_ISSN)
        self.assertEqual(data["source_main_title"], "Book Title")
        self.assertEqual(data["title_pid_generic"], "BOOK:Q7GTD")

    def test_preserves_access_url_and_free_to_read(self):
        data = extraction.extract(
            "books",
            {
                "source_type": "book",
                "source_id": "c2248",
                "document_type": "book",
                "book_id": "c2248",
                "book_title": "Book Title",
                "title_pid_generic": "book:c2248",
                "pid_generic": "book:c2248",
                "media_language": "pt",
                "media_format": MEDIA_FORMAT_PDF,
                "content_type": CONTENT_TYPE_FULL_TEXT,
                "access_url": "/id/c2248/pdf/freitas-9788599662830.pdf",
                "source_access_type": "free_to_read",
            },
        )

        self.assertEqual(data["access_url"], "/id/c2248/pdf/freitas-9788599662830.pdf")
        self.assertEqual(data["counter_access_type"], "Free_To_Read")

    def test_tolerates_malformed_media_language(self):
        data = extraction.extract(
            "books",
            {
                "source_type": "book",
                "source_id": "q7gtd",
                "document_type": "book",
                "book_id": "q7gtd",
                "pid_generic": "book:q7gtd",
                "media_language": "'",
                "media_format": MEDIA_FORMAT_HTML,
                "content_type": CONTENT_TYPE_FULL_TEXT,
            },
        )

        self.assertEqual(data["media_language"], "un")

    def test_sets_document_title_by_type(self):
        chapter = extraction.extract(
            "books",
            {
                "source_type": "book",
                "source_id": "q7gtd",
                "document_type": "chapter",
                "book_id": "q7gtd",
                "chapter_id": "03",
                "pid_generic": "book:q7gtd/chapter:03",
                "book_title": "Book Title",
                "chapter_title": "Chapter Title",
                "media_format": MEDIA_FORMAT_HTML,
                "media_language": "en",
                "content_type": CONTENT_TYPE_FULL_TEXT,
            },
        )
        book = extraction.extract(
            "books",
            {
                "source_type": "book",
                "source_id": "q7gtd",
                "document_type": "book",
                "book_id": "q7gtd",
                "pid_generic": "book:q7gtd",
                "book_title": "Book Title",
                "media_format": MEDIA_FORMAT_HTML,
                "media_language": "en",
                "content_type": CONTENT_TYPE_FULL_TEXT,
            },
        )
        article = extraction.extract(
            "scl",
            {
                "scielo_issn": "1234-5678",
                "pid_v3": "jGJccQ7bFdbz6wy3nfXGVdv",
                "article_title": "Article Title",
                "media_format": MEDIA_FORMAT_HTML,
                "content_type": CONTENT_TYPE_FULL_TEXT,
            },
        )

        self.assertEqual(chapter["document_title"], "Chapter Title")
        self.assertEqual(book["document_title"], "Book Title")
        self.assertEqual(article["document_title"], "Article Title")

    def test_normalizes_collection_document_types(self):
        preprint = extraction.extract(
            "preprints",
            {
                "pid_generic": "10.1590/SciELOPreprints.1234",
                "media_format": MEDIA_FORMAT_HTML,
                "content_type": CONTENT_TYPE_FULL_TEXT,
            },
        )
        dataset = extraction.extract(
            "data",
            {
                "pid_generic": "10.48331/scielodata.abc123",
                "media_format": MEDIA_FORMAT_HTML,
                "content_type": CONTENT_TYPE_ABSTRACT,
            },
        )
        article = extraction.extract(
            "scl",
            {
                "scielo_issn": "1234-5678",
                "pid_v3": "jGJccQ7bFdbz6wy3nfXGVdv",
                "media_format": MEDIA_FORMAT_HTML,
                "content_type": CONTENT_TYPE_FULL_TEXT,
            },
        )

        self.assertEqual(preprint["source_type"], "preprint_server")
        self.assertEqual(preprint["document_type"], "preprint")
        self.assertEqual(dataset["source_type"], "data_repository")
        self.assertEqual(dataset["document_type"], "dataset")
        self.assertEqual(article["source_type"], "journal")
        self.assertEqual(article["document_type"], "article")

    def test_empty_or_none_translated_url_returns_empty_dict(self):
        self.assertEqual(extraction.extract("scl", None), {})
        self.assertEqual(extraction.extract("scl", {}), {})

    def test_counter_access_type_defaults_to_open(self):
        data = extraction.extract(
            "scl",
            {
                "scielo_issn": "1234-5678",
                "pid_v3": "abc123",
                "media_format": MEDIA_FORMAT_HTML,
                "content_type": CONTENT_TYPE_FULL_TEXT,
            },
        )
        self.assertEqual(data["counter_access_type"], "Open")

    def test_commercial_access_type_maps_to_controlled(self):
        data = extraction.extract(
            "scl",
            {
                "scielo_issn": "1234-5678",
                "pid_v3": "abc123",
                "media_format": MEDIA_FORMAT_HTML,
                "content_type": CONTENT_TYPE_FULL_TEXT,
                "source_access_type": "commercial",
            },
        )
        self.assertEqual(data["counter_access_type"], "Controlled")
