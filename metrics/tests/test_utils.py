import unittest

from scielo_usage_counter.values import (
    MEDIA_FORMAT_UNDEFINED,
    MEDIA_FORMAT_PDF,
    MEDIA_FORMAT_HTML,
    CONTENT_TYPE_UNDEFINED,
    CONTENT_TYPE_FULL_TEXT,
    CONTENT_TYPE_ABSTRACT,
    SCIELO_ISSN_DEFAULT,
)

from metrics.utils import is_valid_item_access_data


class TestUtils(unittest.TestCase):
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

    def test_is_valid_item_acess_data_dataverse(self):
        data = {
            'scielo_issn': SCIELO_ISSN_DEFAULT,
            'pid_v2': None,
            'pid_v3': None,
            'pid_generic': 'DOI:10.48331/SCIELODATA.JLMAIY',
            'media_format': MEDIA_FORMAT_HTML,
            'content_type': CONTENT_TYPE_ABSTRACT,
        }
        self.assertTrue(is_valid_item_access_data(data))