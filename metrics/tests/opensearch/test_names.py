import unittest

from django.conf import settings
from django.test import override_settings

from metrics.opensearch.names import generate_month_index_name, generate_year_index_name


class TestIndexNames(unittest.TestCase):
    def test_year_partition_policy_is_explicit(self):
        self.assertEqual(
            set(settings.YEAR_PARTITIONED_COLLECTIONS),
            {"chl", "col", "mex", "scl"},
        )

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

    @override_settings(YEAR_PARTITIONED_COLLECTIONS=[" books ", "SCL"])
    def test_generate_index_names_uses_configured_collections(self):
        self.assertEqual(
            generate_year_index_name("usage", "books", "2024-01-15"),
            "usage_yearly_books_2024",
        )
        self.assertEqual(
            generate_month_index_name("usage", "scl", "2024-01-15"),
            "usage_monthly_scl_2024",
        )
        self.assertEqual(
            generate_year_index_name("usage", "chl", "2024-01-15"),
            "usage_yearly_chl",
        )
