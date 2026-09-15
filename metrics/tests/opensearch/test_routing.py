from django.test import SimpleTestCase

from metrics.legacy_matomo.routing import build_usage_index_target
from metrics.opensearch.mappings import MONTH_INDEX_MAPPINGS


class UsageIndexRoutingTests(SimpleTestCase):
    def test_yearly_strategy_partitions_both_datasets_by_access_year(self):
        counter = build_usage_index_target(
            "usage", "scl", "counter", "yearly", "2025-08-01"
        )
        analytics = build_usage_index_target(
            "usage", "scl", "analytics", "yearly", "2025-08-01"
        )

        self.assertEqual(counter["read_alias"], "usage_monthly_scl")
        self.assertEqual(counter["write_alias"], "usage_monthly_scl_2025")
        self.assertIn("applied_migrations", counter["mappings"]["properties"])
        self.assertNotIn("applied_migrations", MONTH_INDEX_MAPPINGS["properties"])
        self.assertEqual(analytics["read_alias"], "usage_yearly_analytics_scl")
        self.assertEqual(
            analytics["write_alias"],
            "usage_yearly_analytics_scl_2025",
        )

    def test_rollover_strategy_uses_continuous_aliases(self):
        counter = build_usage_index_target(
            "usage", "books", "counter", "rollover", "2025-08-01"
        )
        analytics = build_usage_index_target(
            "usage", "books", "analytics", "rollover", "2025-08-01"
        )

        self.assertEqual(counter["write_alias"], counter["read_alias"])
        self.assertEqual(analytics["write_alias"], analytics["read_alias"])

    def test_rejects_unknown_dataset(self):
        with self.assertRaisesMessage(ValueError, "Unsupported usage dataset"):
            build_usage_index_target("usage", "scl", "unknown", "yearly", "2025-08-01")
