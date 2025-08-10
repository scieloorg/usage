from django.test import TestCase

from core.utils import standardizer


class StandardizerStandardizeCodeAndNameTest(TestCase):

    def test_standardize_code_and_name_returns_both(self):
        expected = [{"code": "CE", "name": "Ceará"}]
        text = "Ceará / CE"
        result = standardizer.standardize_code_and_name(text)
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)

    def test_standardize_code_and_name_returns_acronym(self):
        expected = [{"code": "CE", }]
        text = "CE"
        result = standardizer.standardize_code_and_name(text)
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)

    def test_standardize_code_and_name_returns_name(self):
        expected = [{"name": "Ceará"}]
        text = "Ceará"
        result = standardizer.standardize_code_and_name(text)
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)

    def test_standardize_code_and_name_returns_more_than_one_both(self):
        expected = [{"code": "CE", "name": "Ceará"},
            {"code": "SP", "name": "São Paulo"}]
        text = "Ceará / CE, São Paulo / SP"
        result = standardizer.standardize_code_and_name(text)
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)

    def test_standardize_code_and_name_returns_more_than_one_acronym(self):
        expected = [{"code": "CE", }, {"code": "SP", }]
        text = "CE / SP"
        result = standardizer.standardize_code_and_name(text)
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)

    def test_standardize_code_and_name_returns_more_than_one_name(self):
        expected = [{"name": "Ceará"}, {"name": "São Paulo"}]
        text = "Ceará - São Paulo"
        result = standardizer.standardize_code_and_name(text)
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)


class StandardizerStandardizeNameTest(TestCase):

    def test_standardize_name(self):
        expected = ["Txto 1", "Texto 2", "Texto 3"]
        text = "Txto 1,    Texto 2,    Texto   3"
        result = standardizer.standardize_name(text)
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertEqual({"name": expected[i]}, item)


class StandardizerStandardizeLanguageCode(TestCase):
    def test_standardize_language_code_en_us_is_valid(self):
        language_code = 'en-US'
        standardized = standardizer.standardize_language_code(language_code)
        self.assertEqual(standardized, 'en')

    def test_standardize_language_code_esp_is_valid(self):
        language_code = 'esp'
        standardized = standardizer.standardize_language_code(language_code)
        self.assertEqual(standardized, 'es')

    def test_standardize_language_code_pt_br_is_valid(self):
        language_code = 'pt-BR'
        standardized = standardizer.standardize_language_code(language_code)
        self.assertEqual(standardized, 'pt')

    def test_standardize_language_code_es_is_valid(self):
        language_code = 'spa'
        standardized = standardizer.standardize_language_code(language_code)
        self.assertEqual(standardized, 'es')

    def test_standardize_language_code_en_gb_is_valid(self):
        language_code = 'en-GB'
        standardized = standardizer.standardize_language_code(language_code)
        self.assertEqual(standardized, 'en')


class StandardizerStandardizePIDV3(TestCase):
    def test_standardize_pid_v3_is_valid(self):
        pid_v3 = 'jGJccQ7bFdbz6wy3nfXGVdv'
        standardized = standardizer.standardize_pid_v3(pid_v3)
        self.assertEqual(standardized, 'jGJccQ7bFdbz6wy3nfXGVdv')


class StandardizerStandardizePIDV2(TestCase):
    def test_standardize_pid_v2_is_valid(self):
        pid_v2 = 'S0102-67202020000100001'
        standardized = standardizer.standardize_pid_v2(pid_v2)
        self.assertEqual(standardized, 'S0102-67202020000100001')


class StandardizerStandardizeDOI(TestCase):
    def test_standardize_doi_is_valid(self):
        doi = '10.1590/S0102-67202020000100001'
        standardized = standardizer.standardize_doi(doi)
        self.assertEqual(standardized, '10.1590/S0102-67202020000100001')

    def test_standardize_doi_is_valid_with_doi_prefix(self):
        doi = 'doi:10.1590/S0102-67202020000100001'
        standardized = standardizer.standardize_doi(doi)
        self.assertEqual(standardized, '10.1590/S0102-67202020000100001')

    def test_standardize_doi_is_valid_with_http_prefix(self):
        doi = 'http://doi.org/10.1590/S0102-67202020000100001'
        standardized = standardizer.standardize_doi(doi)
        self.assertEqual(standardized, '10.1590/S0102-67202020000100001')

    def test_standardize_doi_is_valid_with_https_prefix(self):
        doi = 'https://doi.org/10.1590/S0102-67202020000100001'
        standardized = standardizer.standardize_doi(doi)
        self.assertEqual(standardized, '10.1590/S0102-67202020000100001')

    def test_standardize_doi_is_valid_with_doi_prefix_and_http_prefix(self):
        doi = 'doi:http://doi.org/10.1590/S0102-67202020000100001'
        standardized = standardizer.standardize_doi(doi)
        self.assertEqual(standardized, '10.1590/S0102-67202020000100001')

    def test_standardize_doi_is_valid_with_doi_prefix_and_https_prefix(self):
        doi = 'doi:https://doi.org/10.1590/S0102-67202020000100001'
        standardized = standardizer.standardize_doi(doi)
        self.assertEqual(standardized, '10.1590/S0102-67202020000100001')


class TestStandardizeYearOfPublication(TestCase):
    def test_standardize_year_of_publication_four_digit_year(self):
        """Test that a four-digit year is returned as-is"""
        year = "2023"
        result = standardizer.standardize_year_of_publication(year)
        self.assertEqual(result, "2023")
    
    def test_standardize_year_of_publication_integer_year(self):
        """Test that an integer year is converted to string"""
        year = 2023
        result = standardizer.standardize_year_of_publication(year)
        self.assertEqual(result, "2023")
    
    def test_standardize_year_of_publication_year_range(self):
        """Test that a year range returns the first year"""
        year = "2020-2023"
        result = standardizer.standardize_year_of_publication(year)
        self.assertEqual(result, "2020")
    
    def test_standardize_year_of_publication_year_with_slash(self):
        """Test that a year with slash returns the first year"""
        year = "2020/2023"
        result = standardizer.standardize_year_of_publication(year)
        self.assertEqual(result, "2020")
    
    def test_standardize_year_of_publication_year_with_extra_text(self):
        """Test that year with extra text extracts the year"""
        year = "Published in 2023"
        result = standardizer.standardize_year_of_publication(year)
        self.assertEqual(result, "")
    
    def test_standardize_year_of_publication_invalid_year(self):
        """Test that invalid year returns None or empty string"""
        year = "invalid"
        result = standardizer.standardize_year_of_publication(year)
        self.assertEqual(result, '')
    
    def test_standardize_year_of_publication_empty_string(self):
        """Test that empty string returns None or empty string"""
        year = ""
        result = standardizer.standardize_year_of_publication(year)
        self.assertEqual(result, '')
    
    def test_standardize_year_of_publication_none_input(self):
        """Test that None input returns None"""
        year = None
        result = standardizer.standardize_year_of_publication(year)
        self.assertEqual(result, '')
    
    def test_standardize_year_of_publication_two_digit_year(self):
        """Test that two-digit year is converted to four-digit year"""
        year = "23"
        result = standardizer.standardize_year_of_publication(year)
        self.assertEqual(result, '')
    
    def test_standardize_year_of_publication_year_with_parentheses(self):
        """Test that year in parentheses is extracted"""
        year = "(2023)"
        result = standardizer.standardize_year_of_publication(year)
        self.assertEqual(result, '')
