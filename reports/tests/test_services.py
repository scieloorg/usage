from datetime import date

from django.test import TestCase

from collection.models import Collection
from log_manager import choices
from log_manager.models import LogFile
from reports.services import dates, log_report


class DateServiceTests(TestCase):
    def test_get_report_date_from_log_file_uses_validation_probably_date(self):
        collection = Collection.objects.create(acron3="books", acron2="bk")
        log_file = LogFile(
            collection=collection,
            path="/tmp/access.log",
            stat_result={},
            hash="1" * 32,
            status=choices.LOG_FILE_STATUS_CREATED,
            validation={"probably_date": "2026-05-10"},
        )

        self.assertEqual(
            dates.get_report_date_from_log_file(log_file),
            date(2026, 5, 10),
        )


class LogReportServiceTests(TestCase):
    def test_populate_log_report_tables_aggregates_log_files(self):
        from reports.models import MonthlyLogReport, WeeklyLogReport, YearlyLogReport

        collection = Collection.objects.create(acron3="books", acron2="bk")
        LogFile.objects.create(
            collection=collection,
            path="/tmp/access-1.log",
            stat_result={},
            hash="1" * 32,
            status=choices.LOG_FILE_STATUS_QUEUED,
            date=date(2026, 5, 10),
            summary={"lines_parsed": 10, "valid_lines": 7},
            validation={
                "content": {
                    "summary": {
                        "ips": {"local": 1, "remote": 2, "unknown": 3},
                    }
                }
            },
        )

        result = log_report.populate_log_report_tables(
            year=2026,
            collection_acron="books",
        )

        self.assertEqual(result, "Weekly: 1, Monthly: 1, Yearly: 1")

        weekly = WeeklyLogReport.objects.get(collection=collection)
        monthly = MonthlyLogReport.objects.get(collection=collection)
        yearly = YearlyLogReport.objects.get(collection=collection)

        for report in [weekly, monthly, yearly]:
            self.assertEqual(report.total_files, 1)
            self.assertEqual(report.validated_files, 1)
            self.assertEqual(report.lines_parsed, 10)
            self.assertEqual(report.valid_lines, 7)
            self.assertEqual(report.discarded_lines, 3)
            self.assertEqual(report.ip_local_count, 1)
            self.assertEqual(report.ip_remote_count, 2)
            self.assertEqual(report.ip_unknown_count, 3)
