import unittest

from scielo_usage_counter.values import (
    MEDIA_FORMAT_UNDEFINED,
    MEDIA_FORMAT_PDF,
    MEDIA_FORMAT_HTML,
    CONTENT_TYPE_UNDEFINED,
    CONTENT_TYPE_FULL_TEXT,
    CONTENT_TYPE_ABSTRACT,
)

from metrics.utils import (
    standardize_media_language,
    standardize_pid_v2,
    standardize_pid_v3,
    is_valid_item_access_data,
)


class TestUtils(unittest.TestCase):
    def test_standardize_media_language_en_us_is_valid(self):
        media_language = 'en-US'
        standardized = standardize_media_language(media_language)
        self.assertEqual(standardized, 'en')

    def test_standardize_media_language_esp_is_valid(self):
        media_language = 'esp'
        standardized = standardize_media_language(media_language)
        self.assertEqual(standardized, 'es')

    def test_standardize_media_language_pt_br_is_valid(self):
        media_language = 'pt-BR'
        standardized = standardize_media_language(media_language)
        self.assertEqual(standardized, 'pt')

    def test_standardize_media_language_es_is_valid(self):
        media_language = 'spa'
        standardized = standardize_media_language(media_language)
        self.assertEqual(standardized, 'es')

    def test_standardize_media_language_en_gb_is_valid(self):
        media_language = 'en-GB'
        standardized = standardize_media_language(media_language)
        self.assertEqual(standardized, 'en')

    def test_standardize_pid_v3_is_valid(self):
        pid_v3 = 'jGJccQ7bFdbz6wy3nfXGVdv'
        standardized = standardize_pid_v3(pid_v3)
        self.assertEqual(standardized, 'jGJccQ7bFdbz6wy3nfXGVdv')

    def test_standardize_pid_v2_is_valid(self):
        pid_v2 = 'S0102-67202020000100001'
        standardized = standardize_pid_v2(pid_v2)
        self.assertEqual(standardized, 'S0102-67202020000100001')

    def test_is_valid_item_access_data_valid(self):
        data = {
            'scielo_issn': '1234-5678',
            'pid_v2': 'S0102-67202020000100001',
            'pid_v3': 'jGJccQ7bFdbz6wy3nfXGVdv',
            'media_format': MEDIA_FORMAT_PDF,
            'content_type': CONTENT_TYPE_FULL_TEXT,
        }
        self.assertTrue(is_valid_item_access_data(data))

    def test_is_valid_item_access_data_missing_scielo_issn(self):
        data = {
            'scielo_issn': '',
            'pid_v2': 'S0102-67202020000100001',
            'pid_v3': 'jGJccQ7bFdbz6wy3nfXGVdv',
            'media_format': MEDIA_FORMAT_PDF,
            'content_type': CONTENT_TYPE_FULL_TEXT,
        }
        self.assertFalse(is_valid_item_access_data(data))

    def test_is_valid_item_access_data_undefined_media_format(self):
        data = {
            'scielo_issn': '1234-5678',
            'pid_v2': 'S0102-67202020000100001',
            'pid_v3': 'jGJccQ7bFdbz6wy3nfXGVdv',
            'media_format': MEDIA_FORMAT_UNDEFINED,
            'content_type': CONTENT_TYPE_FULL_TEXT,
        }
        self.assertFalse(is_valid_item_access_data(data))

    def test_is_valid_item_access_data_undefined_content_type(self):
        data = {
            'scielo_issn': '1234-5678',
            'pid_v2': 'S0102-67202020000100001',
            'pid_v3': 'jGJccQ7bFdbz6wy3nfXGVdv',
            'media_format': MEDIA_FORMAT_PDF,
            'content_type': CONTENT_TYPE_UNDEFINED,
        }
        self.assertFalse(is_valid_item_access_data(data))

    def test_is_valid_item_access_data_missing_pid_v2_and_pid_v3(self):
        data = {
            'scielo_issn': '1234-5678',
            'pid_v2': '',
            'pid_v3': '',
            'media_format': MEDIA_FORMAT_PDF,
            'content_type': CONTENT_TYPE_FULL_TEXT,
        }
        self.assertFalse(is_valid_item_access_data(data))

    def test_is_valid_item_access_data_media_format_html(self):
        data = {
            'scielo_issn': '1234-5678',
            'pid_v2': 'S0102-67202020000100001',
            'pid_v3': 'jGJccQ7bFdbz6wy3nfXGVdv',
            'media_format': MEDIA_FORMAT_HTML,
            'content_type': CONTENT_TYPE_FULL_TEXT,
        }
        self.assertTrue(is_valid_item_access_data(data))

    def test_is_valid_item_access_data_content_type_abstract(self):
        data = {
            'scielo_issn': '1234-5678',
            'pid_v2': 'S0102-67202020000100001',
            'pid_v3': 'jGJccQ7bFdbz6wy3nfXGVdv',
            'media_format': MEDIA_FORMAT_PDF,
            'content_type': CONTENT_TYPE_ABSTRACT
        }
        self.assertTrue(is_valid_item_access_data(data))
