import unittest
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
