import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from metrics.services import daily_payloads
from metrics.services.daily_metric_exports import _ensure_payload
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
            collection=SimpleNamespace(acron3="scl"),
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
            writer.write_documents(
                "month",
                {"month-doc": {"access": {"month": "2026-08"}}},
            )
            writer.write_documents(
                "year",
                {"year-doc": {"access": {"year": "2026"}}},
            )
            writer.finalize(["abc"], {"valid_lines": 1})

    def test_export_streams_each_granularity_as_document_items(self):
        self._write_payload()
        search_client = Mock()
        exported_groups = []

        def consume_items(index_name, document_items, job_id):
            exported_groups.append((index_name, list(document_items), job_id))
            return 1

        search_client.increment_document_items_for_daily_job.side_effect = consume_items

        export_daily_metric_payload(search_client, self.job)

        self.assertEqual(
            exported_groups,
            [
                (
                    "usage_monthly_scl_2026",
                    [("month-doc", {"access": {"month": "2026-08"}})],
                    self.job.job_id,
                ),
                (
                    "usage_yearly_scl_2026",
                    [("year-doc", {"access": {"year": "2026"}})],
                    self.job.job_id,
                ),
            ],
        )

    def test_retry_after_partial_export_reuses_same_payload_and_job_id(self):
        self._write_payload()
        first_client = Mock()
        first_client.increment_document_items_for_daily_job.side_effect = [
            1,
            RuntimeError("year export failed"),
        ]

        with self.assertRaisesMessage(RuntimeError, "year export failed"):
            export_daily_metric_payload(first_client, self.job)

        second_client = Mock()
        second_client.increment_document_items_for_daily_job.side_effect = (
            lambda index_name, document_items, job_id: len(list(document_items))
        )
        export_daily_metric_payload(second_client, self.job)

        self.assertEqual(
            [
                call.kwargs["job_id"]
                for call in second_client.increment_document_items_for_daily_job.call_args_list
            ],
            [self.job.job_id, self.job.job_id],
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
