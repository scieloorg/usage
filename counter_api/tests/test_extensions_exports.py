import csv
import json
from calendar import monthrange
from io import BytesIO, StringIO
from unittest import TestCase

from openpyxl import load_workbook

from counter_api.exceptions import CounterAPIError
from counter_api.extensions.exports import build_export


class ExtensionExportTests(TestCase):
    def test_ranking_csv_and_xlsx_preserve_cursor_with_items(self):
        payload = {
            "groups": [
                {
                    "dimensions": {"country": "BR", "language": "pt"},
                    "items": [{"id": "article-1", "title": "Artigo", "count": 12}],
                }
            ],
            "pagination": {"group_limit": 5, "next_cursor": "signed-next-page"},
        }

        with build_export(payload, "ranking", "csv") as output:
            rows = list(csv.DictReader(StringIO(output.read().decode())))
        with build_export(payload, "ranking", "xlsx") as output:
            workbook = load_workbook(BytesIO(output.read()), read_only=True)

        self.assertEqual(json.loads(rows[0]["Pagination"]), payload["pagination"])
        self.assertEqual(
            json.loads(workbook["Pagination"]["A2"].value), payload["pagination"]
        )
        workbook.close()

    def test_empty_page_preserves_coverage_and_cursor_in_downloads(self):
        payload = {
            "groups": [],
            "coverage": {"status": "partial"},
            "warnings": ["Missing days"],
            "pagination": {"group_limit": 5, "next_cursor": "signed-next-page"},
        }

        for output_format in ("csv", "xlsx"):
            with self.subTest(format=output_format):
                with build_export(payload, "ranking", output_format) as output:
                    if output_format == "csv":
                        metadata = next(
                            csv.DictReader(StringIO(output.read().decode()))
                        )
                        self.assertEqual(metadata["ID"], "")
                    else:
                        workbook = load_workbook(output, read_only=True)
                        headings, values = list(workbook["Coverage"].values)
                        metadata = dict(zip(headings, values))
                        workbook.close()

                self.assertEqual(json.loads(metadata["Coverage"]), payload["coverage"])
                self.assertEqual(json.loads(metadata["Warnings"]), payload["warnings"])
                self.assertEqual(
                    json.loads(metadata["Pagination"]), payload["pagination"]
                )

    def test_xlsx_long_coverage_round_trips_without_cell_truncation(self):
        months = [
            {
                "month": f"{year}-{month:02}",
                "status": "complete",
                "requested_days": list(range(1, monthrange(year, month)[1] + 1)),
                "confirmed_days": list(range(1, monthrange(year, month)[1] + 1)),
                "missing_days": [],
                "future_days": [],
                "ongoing": False,
                "complete_month": True,
            }
            for year in range(2014, 2024)
            for month in range(1, 13)
        ]
        coverage = {
            "policy": "allow_partial",
            "status": "complete",
            "ongoing": False,
            "basis": "confirmed_days",
            "months": months,
            "included_months": [month["month"] for month in months],
        }
        payload = {"groups": [], "coverage": coverage, "warnings": []}
        self.assertGreater(len(json.dumps(coverage, separators=(",", ":"))), 32767)

        with build_export(payload, "ranking", "xlsx") as output:
            workbook = load_workbook(output, read_only=True)
            _, summary = list(workbook["Coverage"].values)
            monthly_rows = list(workbook["Coverage months"].values)[1:]
            restored = json.loads(summary[0])
            restored["months"] = [json.loads(row[1]) for row in monthly_rows]
            restored["included_months"] = [row[0] for row in monthly_rows if row[2]]
            workbook.close()

        self.assertEqual(restored, coverage)

    def test_xlsx_rejects_oversized_cursor_instead_of_truncating(self):
        payload = {
            "groups": [],
            "pagination": {"group_limit": 5, "next_cursor": "x" * 40000},
        }

        with self.assertRaises(CounterAPIError) as error:
            build_export(payload, "ranking", "xlsx")

        self.assertIn("Excel cell limit", error.exception.data)
