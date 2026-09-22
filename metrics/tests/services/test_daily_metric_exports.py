import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from metrics.services import daily_payloads
from metrics.services.daily_metric_exports import _ensure_payload, _export_payload
from metrics.services.export import export_daily_metric_payload


class DailyMetricExportTests(SimpleTestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.temporary_directory.name,
            OPENSEARCH_INDEX_NAME="usage",
        )
        self.settings_override.enable()
        self.storage_path = Path("scl/2026/08/2026-08-25.json")
        self.job = SimpleNamespace(
            pk=1,
            collection=SimpleNamespace(
                acron3="scl",
                log_manager_config=SimpleNamespace(
                    opensearch_primary_shards=1,
                    opensearch_partition_strategy="yearly",
                ),
            ),
            access_date=date(2026, 8, 25),
            storage_path=self.storage_path.as_posix(),
            payload_hash="payload-hash",
            job_id="scl|2026-08-25|payload-hash",
        )

    def tearDown(self):
        self.settings_override.disable()
        self.temporary_directory.cleanup()

    def _write_payload(self):
        with daily_payloads.DailyPayloadWriter(
            self.storage_path,
            "scl",
            "2026-08-25",
        ) as writer:
            writer.write_document_items(
                "counter",
                [("month-doc", {"month": "2026-08"})],
            )
            writer.write_document_items(
                "analytics",
                [
                    (
                        "analytics-doc",
                        {"year": "2026", "country_code": "BR"},
                    )
                ],
            )
            writer.finalize(["abc"], {"valid_lines": 1})

    def test_export_streams_each_dataset_as_document_items(self):
        self._write_payload()
        search_client = Mock()
        search_client.prepare_usage_index.side_effect = [
            "usage_monthly_scl_2026",
            "usage_yearly_analytics_scl_2026",
        ]
        exported_groups = []

        def consume_items(
            index_name,
            document_items,
            access_day,
            annual=False,
            resolve_existing_indexes=False,
        ):
            exported_groups.append(
                (
                    index_name,
                    list(document_items),
                    access_day,
                    annual,
                    resolve_existing_indexes,
                )
            )
            return 1

        search_client.increment_document_items_for_day.side_effect = consume_items

        export_daily_metric_payload(search_client, self.job)

        self.assertEqual(
            exported_groups,
            [
                (
                    "usage_monthly_scl_2026",
                    [("month-doc", {"month": "2026-08"})],
                    "2026-08-25",
                    False,
                    True,
                ),
                (
                    "usage_yearly_analytics_scl_2026",
                    [
                        (
                            "analytics-doc",
                            {"year": "2026", "country_code": "BR"},
                        )
                    ],
                    "2026-08-25",
                    True,
                    True,
                ),
            ],
        )
        self.assertEqual(
            [
                call.kwargs["primary_shards"]
                for call in search_client.prepare_usage_index.call_args_list
            ],
            [1, 1],
        )
        self.assertEqual(
            [
                (
                    call.kwargs["alias_name"],
                    call.kwargs["read_alias"],
                )
                for call in search_client.rollover_usage_index.call_args_list
            ],
            [
                ("usage_monthly_scl_2026", "usage_monthly_scl"),
                (
                    "usage_yearly_analytics_scl_2026",
                    "usage_yearly_analytics_scl",
                ),
            ],
        )

    def test_retry_after_partial_export_reuses_same_payload_and_access_day(self):
        self._write_payload()
        first_client = Mock()
        first_client.increment_document_items_for_day.side_effect = [
            1,
            RuntimeError("analytics export failed"),
        ]

        with self.assertRaisesMessage(RuntimeError, "analytics export failed"):
            export_daily_metric_payload(first_client, self.job)

        second_client = Mock()

        def count_items(**kwargs):
            return len(list(kwargs["document_items"]))

        second_client.increment_document_items_for_day.side_effect = count_items
        export_daily_metric_payload(second_client, self.job)

        self.assertEqual(
            [
                call.kwargs["access_day"]
                for call in second_client.increment_document_items_for_day.call_args_list
            ],
            ["2026-08-25", "2026-08-25"],
        )

    def test_continuous_collection_routes_existing_documents_before_rollover(self):
        self._write_payload()
        self.job.collection.log_manager_config.opensearch_partition_strategy = (
            "rollover"
        )
        search_client = Mock()
        search_client.prepare_usage_index.side_effect = [
            "usage_monthly_scl",
            "usage_yearly_analytics_scl",
        ]
        search_client.increment_document_items_for_day.side_effect = (
            lambda **kwargs: len(list(kwargs["document_items"]))
        )

        export_daily_metric_payload(search_client, self.job)

        self.assertEqual(
            [
                call.kwargs["resolve_existing_indexes"]
                for call in search_client.increment_document_items_for_day.call_args_list
            ],
            [True, True],
        )
        self.assertEqual(
            [
                call.kwargs["alias_name"]
                for call in search_client.rollover_usage_index.call_args_list
            ],
            ["usage_monthly_scl", "usage_yearly_analytics_scl"],
        )

    @patch("metrics.services.daily_metric_exports.mark_days_exported")
    @patch("metrics.services.daily_metric_exports.export_daily_metric_payload")
    @patch("metrics.services.daily_metric_exports.OpenSearchUsageClient")
    def test_marks_day_after_facts_are_visible(
        self,
        client_class,
        export_payload,
        mark_exported,
    ):
        search_client = client_class.return_value
        search_client.ping.return_value = True

        _export_payload(self.job)

        export_payload.assert_called_once_with(
            search_client=search_client,
            job=self.job,
        )
        search_client.client.indices.refresh.assert_called_once_with(
            index="usage_monthly_scl,usage_yearly_analytics_scl",
            ignore_unavailable=True,
        )
        mark_exported.assert_called_once_with(
            search_client,
            "scl",
            date(2026, 8, 25),
            1 << 24,
        )

    @patch("metrics.services.daily_metric_exports.fetch_required_resources")
    @patch("metrics.services.daily_metric_exports.build_daily_metric_job_payload")
    def test_resume_uses_persisted_payload_without_parsing(
        self,
        mock_build_payload,
        mock_fetch_resources,
    ):
        self._write_payload()

        _ensure_payload(self.job, track_errors=False, robots_source="counter")

        mock_build_payload.assert_not_called()
        mock_fetch_resources.assert_not_called()
