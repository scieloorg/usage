import unittest

from scielo_usage_counter.values import (
    CONTENT_TYPE_ABSTRACT,
    CONTENT_TYPE_FULL_TEXT,
    CONTENT_TYPE_UNDEFINED,
    DEFAULT_SCIELO_ISSN,
    MEDIA_FORMAT_HTML,
    MEDIA_FORMAT_PDF,
    MEDIA_FORMAT_UNDEFINED,
)

from metrics.counter.access import validation


class TestValidation(unittest.TestCase):
    def test_valid_journal_access(self):
        data = {
            "scielo_issn": "1234-5678",
            "pid_v2": "S0102-67202020000100001",
            "pid_v3": "jGJccQ7bFdbz6wy3nfXGVdv",
            "media_language": "en",
            "media_format": MEDIA_FORMAT_PDF,
            "content_type": CONTENT_TYPE_FULL_TEXT,
        }
        result, _ = validation.is_valid(data)
        self.assertTrue(result)

    def test_valid_book_source(self):
        data = {
            "source_type": "book",
            "source_id": "q7gtd",
            "scielo_issn": DEFAULT_SCIELO_ISSN,
            "pid_generic": "BOOK:Q7GTD",
            "media_language": "en",
            "media_format": MEDIA_FORMAT_HTML,
            "content_type": CONTENT_TYPE_FULL_TEXT,
        }
        result, _ = validation.is_valid(data)
        self.assertTrue(result)

    def test_undefined_media_format_is_invalid(self):
        data = {
            "scielo_issn": "1234-5678",
            "pid_v2": "S0102-67202020000100001",
            "pid_v3": "jGJccQ7bFdbz6wy3nfXGVdv",
            "media_language": "en",
            "media_format": MEDIA_FORMAT_UNDEFINED,
            "content_type": CONTENT_TYPE_FULL_TEXT,
        }
        result, _ = validation.is_valid(data)
        self.assertFalse(result)

    def test_undefined_content_type_is_invalid(self):
        data = {
            "scielo_issn": "1234-5678",
            "pid_v2": "S0102-67202020000100001",
            "pid_v3": "jGJccQ7bFdbz6wy3nfXGVdv",
            "media_language": "en",
            "media_format": MEDIA_FORMAT_PDF,
            "content_type": CONTENT_TYPE_UNDEFINED,
        }
        result, _ = validation.is_valid(data)
        self.assertFalse(result)

    def test_missing_all_pids_is_invalid(self):
        data = {
            "scielo_issn": "1234-5678",
            "pid_v2": "",
            "pid_v3": "",
            "media_language": "en",
            "media_format": MEDIA_FORMAT_PDF,
            "content_type": CONTENT_TYPE_FULL_TEXT,
        }
        result, _ = validation.is_valid(data)
        self.assertFalse(result)

    def test_html_format_is_valid(self):
        data = {
            "scielo_issn": "1234-5678",
            "pid_v2": "S0102-67202020000100001",
            "pid_v3": "jGJccQ7bFdbz6wy3nfXGVdv",
            "media_language": "en",
            "media_format": MEDIA_FORMAT_HTML,
            "content_type": CONTENT_TYPE_FULL_TEXT,
        }
        result, _ = validation.is_valid(data)
        self.assertTrue(result)

    def test_abstract_content_type_is_valid(self):
        data = {
            "scielo_issn": "1234-5678",
            "pid_v2": "S0102-67202020000100001",
            "pid_v3": "jGJccQ7bFdbz6wy3nfXGVdv",
            "media_language": "en",
            "media_format": MEDIA_FORMAT_PDF,
            "content_type": CONTENT_TYPE_ABSTRACT,
        }
        result, _ = validation.is_valid(data)
        self.assertTrue(result)

    def test_dataset_without_source_or_language_is_valid(self):
        data = {
            "document_type": "dataset",
            "scielo_issn": DEFAULT_SCIELO_ISSN,
            "pid_v2": None,
            "pid_v3": None,
            "pid_generic": "DOI:10.48331/SCIELODATA.JLMAIY",
            "media_language": "un",
            "media_format": MEDIA_FORMAT_HTML,
            "content_type": CONTENT_TYPE_ABSTRACT,
        }
        result, _ = validation.is_valid(data)
        self.assertTrue(result)

    def test_missing_media_language_is_invalid(self):
        data = {
            "scielo_issn": "1234-5678",
            "pid_v2": "S0102-67202020000100001",
            "pid_v3": "jGJccQ7bFdbz6wy3nfXGVdv",
            "media_language": "",
            "media_format": MEDIA_FORMAT_PDF,
            "content_type": CONTENT_TYPE_FULL_TEXT,
        }
        result, _ = validation.is_valid(data)
        self.assertFalse(result)

    def test_missing_scielo_issn_for_article_is_invalid(self):
        data = {
            "scielo_issn": "",
            "pid_v2": "S0102-67202020000100001",
            "pid_v3": "jGJccQ7bFdbz6wy3nfXGVdv",
            "media_language": "en",
            "media_format": MEDIA_FORMAT_PDF,
            "content_type": CONTENT_TYPE_FULL_TEXT,
        }
        result, _ = validation.is_valid(data)
        self.assertFalse(result)

    def test_preprint_requires_pid_generic(self):
        data = {
            "document_type": "preprint",
            "pid_v2": None,
            "pid_v3": "abc123",
            "pid_generic": "",
            "media_language": "en",
            "media_format": MEDIA_FORMAT_HTML,
            "content_type": CONTENT_TYPE_FULL_TEXT,
        }
        result, _ = validation.is_valid(data)
        self.assertFalse(result)

    def test_chapter_requires_source_id(self):
        data = {
            "document_type": "chapter",
            "source_id": "",
            "scielo_issn": DEFAULT_SCIELO_ISSN,
            "pid_generic": "BOOK:Q7GTD/CHAPTER:03",
            "media_language": "en",
            "media_format": MEDIA_FORMAT_HTML,
            "content_type": CONTENT_TYPE_FULL_TEXT,
        }
        result, _ = validation.is_valid(data)
        self.assertFalse(result)

    def test_non_dict_input_is_invalid(self):
        result, check = validation.is_valid(None)
        self.assertFalse(result)
        self.assertEqual(check["code"], "invalid_format")
