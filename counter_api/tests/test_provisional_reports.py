from datetime import date
from io import BytesIO
from unittest.mock import Mock, patch

from django.test import TestCase
from openpyxl import load_workbook


class ProvisionalReportTests(TestCase):
    def setUp(self):
        platform = Mock(acron3="scl", collection_type="journals")

        self.params = {
            "platform": "scl",
            "begin_date": "2024-01",
            "end_date": "2024-02",
        }
        self.coverage = {
            "policy": "allow_partial",
            "status": "partial",
            "basis": "confirmed_days",
            "included_months": ["2024-01", "2024-02"],
            "ongoing": False,
            "months": [
                {
                    "month": month,
                    "status": "complete" if complete else "partial",
                    "complete_month": complete,
                    "ongoing": False,
                    "requested_days": list(range(1, days + 1)),
                    "confirmed_days": list(range(1, days + 1)) if complete else [1, 3],
                    "missing_days": []
                    if complete
                    else [day for day in range(1, days + 1) if day not in (1, 3)],
                    "future_days": [],
                }
                for month, days, complete in (
                    ("2024-01", 31, True),
                    ("2024-02", 29, False),
                )
            ],
        }

        for target, value in (
            ("counter_api.views.get_platform", platform),
            ("counter_api.generation.resolve_coverage", self.coverage),
            (
                "counter_api.generation.split_period",
                ([date(2024, 1, 1)], [date(2024, 2, 1)], []),
            ),
        ):
            mocked = patch(target, return_value=value)
            mocked.start()
            self.addCleanup(mocked.stop)

        query_patch = patch("counter_api.generation.ReportQuery")
        self.query = query_patch.start().return_value
        self.addCleanup(query_patch.stop)
        self.query.deadline = float("inf")
        self.query.fetch.return_value = []

    def test_partial_selection_preserves_standard_report_behavior(self):
        response = self.client.get("/r51/extensions/reports/tr", self.params)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["provisional"])
        self.assertEqual(response.json()["coverage"]["policy"], "allow_partial")
        self.assertEqual(
            self.query.fetch.call_args.args[1], [date(2024, 1, 1), date(2024, 2, 1)]
        )
        self.assertIn("coverage", self.query.fetch.call_args.args[3])

        response = self.client.get(
            "/r51/extensions/reports/tr",
            {**self.params, "coverage_policy": "allow_partial"},
        )
        self.assertEqual(response.status_code, 200)

        for policy in ("strict", "invalid"):
            with self.subTest(policy=policy):
                response = self.client.get(
                    "/r51/extensions/reports/tr",
                    {**self.params, "coverage_policy": policy},
                )
                self.assertEqual(response.status_code, 400)

        response = self.client.get("/r51/reports/tr", self.params)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("provisional", response.json())
        self.assertEqual(self.query.fetch.call_args.args[1], [date(2024, 1, 1)])
        self.assertNotIn("coverage", self.query.fetch.call_args.args[3])

    def test_empty_downloads_preserve_partial_coverage_and_warnings(self):
        for output_format in ("xlsx", "tsv"):
            with self.subTest(output_format=output_format):
                response = self.client.get(
                    "/r51/extensions/reports/tr",
                    {**self.params, "format": output_format},
                )
                self.assertEqual(response.status_code, 200)

                content = b"".join(response.streaming_content)
                if output_format == "xlsx":
                    workbook = load_workbook(BytesIO(content), read_only=True)
                    text = str(list(workbook["Coverage"].values))
                    workbook.close()
                else:
                    text = content.decode("utf-8-sig")

                self.assertIn("not a COUNTER-compliant report", text)
                self.assertIn("2024-02", text)
                self.assertIn("partial", text)
                self.assertIn("Confirmed_Days", text)
