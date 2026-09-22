import json
import tempfile
from datetime import date
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from collection.models import Collection
from metrics.models import DailyMetricJob


class BackfillMonthStatusCommandTests(TestCase):
    @patch(
        "metrics.management.commands.backfill_counter_month_status."
        "replace_month_status"
    )
    @patch(
        "metrics.management.commands.backfill_counter_month_status."
        "OpenSearchUsageClient"
    )
    def test_uses_only_exported_days(self, client_class, replace_status):
        collection = Collection.objects.create(acron3="scl", acron2="sc")
        for access_date, status in (
            (date(2025, 1, 1), DailyMetricJob.STATUS_EXPORTED),
            (date(2025, 1, 2), DailyMetricJob.STATUS_PENDING),
            (date(2025, 1, 31), DailyMetricJob.STATUS_EXPORTED),
        ):
            DailyMetricJob.objects.create(
                collection=collection,
                access_date=access_date,
                status=status,
            )

        output = StringIO()
        call_command(
            "backfill_counter_month_status",
            collection="scl",
            start_month="2025-01",
            end_month="2025-01",
            apply=True,
            stdout=output,
        )

        replace_status.assert_called_once_with(
            client_class.return_value,
            "scl",
            date(2025, 1, 1),
            (1 << 0) | (1 << 30),
        )
        self.assertIn("days=2", output.getvalue())

    @patch(
        "metrics.management.commands.backfill_counter_month_status."
        "replace_month_status"
    )
    @patch(
        "metrics.management.commands.backfill_counter_month_status."
        "OpenSearchUsageClient"
    )
    def test_uses_completed_migration_reports(self, client_class, replace_status):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            report_path = root / "report.json"
            manifest = {
                "month": "2025-02",
                "source_days": ["2025-02-01", "2025-02-28"],
                "empty_days": ["2025-02-02"],
                "target": {"collection": "scl"},
            }
            report = {
                "status": "completed",
                "manifest": str(manifest_path),
                "collection": "scl",
                "month": "2025-02",
                "validation": {
                    "status": "valid",
                    "counter": {"documents": 10},
                    "analytics": {"documents": 20},
                },
                "imported": {"counter": 10, "analytics": 20},
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            report_path.write_text(json.dumps(report), encoding="utf-8")

            call_command(
                "backfill_counter_month_status",
                report=[str(report_path)],
                apply=True,
                stdout=StringIO(),
            )

        replace_status.assert_called_once_with(
            client_class.return_value,
            "scl",
            date(2025, 2, 1),
            (1 << 0) | (1 << 1) | (1 << 27),
        )
