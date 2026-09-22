from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import override_settings

from metrics.legacy_matomo import importer
from metrics.legacy_matomo.opensearch_actions import (
    build_analytics_increment_action,
    build_counter_increment_action,
)
from metrics.tests.services.legacy_matomo import METRICS, LegacyManifestTestCase


class LegacyMatomoImporterTests(LegacyManifestTestCase):
    def test_counter_action_tracks_only_document_days(self):
        document = {
            "month": "2025-08",
            "daily_metrics": {"01": METRICS},
            **METRICS,
        }

        action = build_counter_increment_action(
            "usage_monthly_scl_2025",
            "key",
            document,
            "migration-with-hash",
            ["2025-08-01", "2025-08-02"],
        )

        params = action["script"]["params"]
        self.assertEqual(params["migration_id"], "migration-with-hash")
        self.assertEqual(params["source_days"], ["2025-08-01"])

    def test_analytics_action_builds_all_day_masks(self):
        action = build_analytics_increment_action(
            "usage_yearly_analytics_scl_2025",
            "key",
            METRICS,
            "migration-with-hash",
            ["2025-08-01", "2025-08-31"],
        )

        day_masks = action["script"]["params"]["day_masks"]
        august_first_offset = 212
        august_last_offset = 242
        self.assertTrue(
            day_masks[august_first_offset // 63] & (1 << (august_first_offset % 63))
        )
        self.assertTrue(
            day_masks[august_last_offset // 63] & (1 << (august_last_offset % 63))
        )

    def test_analytics_action_preserves_masks_larger_than_32_bits(self):
        action = build_analytics_increment_action(
            "usage_yearly_analytics_scl_2025",
            "key",
            METRICS,
            "migration-with-hash",
            ["2025-09-01", "2025-09-30"],
        )

        day_masks = action["script"]["params"]["day_masks"]
        script = action["script"]["source"]

        self.assertGreater(max(day_masks), (1 << 31) - 1)
        self.assertIn("((Number) params.day_masks[index]).longValue()", script)
        self.assertNotIn("applied_day_masks[index] |=", script)

    @override_settings(OPENSEARCH_INDEX_NAME="usage")
    def test_preflight_builds_yearly_targets_without_writes(self):
        collection = SimpleNamespace(
            acron3="scl",
            log_manager_config=SimpleNamespace(
                opensearch_partition_strategy="yearly",
                opensearch_primary_shards=3,
            ),
        )
        search_client = Mock()
        search_client.client.indices.exists_alias.return_value = False

        plan = importer.build_import_plan(search_client, collection, self.manifest)

        self.assertEqual(plan["primary_shards"], 3)
        self.assertEqual(
            [item["write_alias"]["alias"] for item in plan["datasets"]],
            ["usage_monthly_scl_2025", "usage_yearly_analytics_scl_2025"],
        )
        self.assertFalse(search_client.prepare_usage_index.called)

    @override_settings(OPENSEARCH_INDEX_NAME="usage")
    def test_preflight_rejects_rollover_with_existing_yearly_alias(self):
        collection = SimpleNamespace(
            acron3="scl",
            log_manager_config=SimpleNamespace(
                opensearch_partition_strategy="rollover",
                opensearch_primary_shards=1,
            ),
        )
        search_client = Mock()
        search_client.client.indices.exists_alias.side_effect = (
            lambda name: name.endswith("_2025")
        )
        search_client.client.indices.get_alias.side_effect = lambda name: {
            name
            + "-000001": {
                "aliases": {name: {"is_write_index": True}},
            }
        }

        with self.assertRaisesMessage(ValueError, "conflicts with yearly alias"):
            importer.build_import_plan(search_client, collection, self.manifest)

    @patch("metrics.legacy_matomo.importer.helpers.bulk")
    def test_historical_updates_follow_existing_backing_index(self, bulk):
        search_client = Mock()
        search_client.bulk_chunk_size = 500
        search_client.client.indices.exists_alias.return_value = True
        search_client.client.indices.get_alias.return_value = {
            "usage_monthly_scl_2025-000001": {
                "aliases": {
                    "usage_monthly_scl_2025": {"is_write_index": False},
                }
            },
            "usage_monthly_scl_2025-000002": {
                "aliases": {
                    "usage_monthly_scl_2025": {"is_write_index": True},
                }
            },
        }
        search_client.client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "existing",
                        "_index": "usage_monthly_scl_2025-000001",
                    }
                ]
            }
        }
        actions = []
        progress = []

        def consume(_client, action_items, chunk_size):
            actions.extend(action_items)
            return len(actions), 0

        bulk.side_effect = consume

        imported = importer._update_document_items(
            search_client,
            "usage_monthly_scl_2025",
            iter([("existing", {}), ("new", {})]),
            lambda index_name, doc_id, document: {
                "_index": index_name,
                "_id": doc_id,
                "_source": document,
            },
            dataset="counter",
            progress_callback=lambda dataset, stage, documents: progress.append(
                (dataset, stage, documents)
            ),
            progress_interval=1,
        )

        self.assertEqual(imported, 2)
        self.assertEqual(
            [action["_index"] for action in actions],
            [
                "usage_monthly_scl_2025-000001",
                "usage_monthly_scl_2025-000002",
            ],
        )
        self.assertEqual(progress, [("counter", "import", 2)])

    @override_settings(OPENSEARCH_INDEX_NAME="usage")
    @patch("metrics.legacy_matomo.importer.mark_days_exported")
    @patch("metrics.legacy_matomo.importer.import_dataset")
    def test_import_marks_source_and_empty_days_after_refresh(
        self,
        import_dataset,
        mark_days,
    ):
        self.manifest["source_days"] = ["2025-08-01", "2025-08-31"]
        self.manifest["empty_days"] = ["2025-08-02"]
        collection = SimpleNamespace(
            acron3="scl",
            log_manager_config=SimpleNamespace(
                opensearch_partition_strategy="yearly",
                opensearch_primary_shards=1,
            ),
        )
        search_client = Mock()
        import_dataset.side_effect = [10, 20]

        result = importer.import_manifest(search_client, collection, self.manifest)

        self.assertEqual(result, {"counter": 10, "analytics": 20})
        search_client.client.indices.refresh.assert_called_once_with(
            index="usage_monthly_scl,usage_yearly_analytics_scl",
            ignore_unavailable=True,
        )
        mark_days.assert_called_once_with(
            search_client,
            "scl",
            date(2025, 8, 1),
            (1 << 0) | (1 << 1) | (1 << 30),
        )
