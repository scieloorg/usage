import unittest

from metrics.opensearch.names import generate_month_index_name, generate_year_index_name


class TestIndexNames(unittest.TestCase):
    def test_generate_index_names_for_year_and_month(self):
        self.assertEqual(
            generate_year_index_name("usage", "scl", "2024-01-15"),
            "usage_yearly_scl_2024",
        )
        self.assertEqual(
            generate_month_index_name("usage", "scl", "2024-01-15"),
            "usage_monthly_scl_2024",
        )
        self.assertEqual(
            generate_year_index_name("usage", "books", "2024-01-15"),
            "usage_yearly_books",
        )
        self.assertEqual(
            generate_month_index_name("usage", "books", "2024-01-15"),
            "usage_monthly_books",
        )
