from datetime import date
from io import BytesIO
from unittest.mock import patch

from django.test import TestCase
from openpyxl import load_workbook

from collection.models import Collection
from counter_api.models import APIKey
from counter_api.openapi import EXCEL_CONTENT_TYPE
from counter_api.reports import build_report
from counter_api.tabular import build_tsv
from counter_api.tests.schema import validate_report


class ReportViewTests(TestCase):
    def setUp(self):
        self.platform = Collection.objects.create(
            acron3="scl",
            main_name="SciELO Brasil",
            collection_type="journals",
            is_active=True,
        )
        _key, self.api_key = APIKey.issue("tests")

    def test_title_report_omits_facts_without_source_metadata(self):
        records = [
            (
                {
                    "key": {
                        "source_key": "missing-source",
                        "month": "2025-08",
                        "metric_scope": "item",
                        "data_type": "Article",
                        "access_type": "Open",
                        "access_method": "Regular",
                    },
                    "total_requests": {"value": 1},
                    "total_investigations": {"value": 1},
                    "unique_requests": {"value": 1},
                    "unique_investigations": {"value": 1},
                },
                {},
                {},
            )
        ]
        report = build_report(
            "tr_j3",
            self.platform,
            date(2025, 8, 1),
            date(2025, 8, 31),
            records,
            {},
        )

        self.assertEqual(report["Report_Items"], [])
        self.assertEqual(
            report["Report_Header"]["Exceptions"],
            [
                {
                    "Code": 3040,
                    "Message": "Partial Data Returned",
                    "Data": "Metadata missing for 1 title(s)",
                }
            ],
        )

    def test_title_report_includes_required_data_type(self):
        bucket = {
            "key": {
                "source_key": "journal-1",
                "document_key": "article-1",
                "month": "2025-08",
                "metric_scope": "item",
                "data_type": "Article",
                "access_type": "Open",
                "access_method": "Regular",
                "publication_year": 2025,
            },
            "total_investigations": {"value": 1},
            "total_requests": {"value": 1},
        }
        source = {"title": "Journal"}

        report = build_report(
            "tr",
            self.platform,
            date(2025, 8, 1),
            date(2025, 8, 31),
            [(bucket, source, {})],
            {},
        )
        attributes = report["Report_Items"][0]["Attribute_Performance"][0]
        tsv = build_tsv(report)
        lines = tsv.read().decode("utf-8-sig").splitlines()
        tsv.close()

        self.assertEqual(attributes["Data_Type"], "Journal")
        self.assertIn("Data_Type", lines[14].split("\t"))
        validate_report(report, "tr")

    @patch("counter_api.generation.split_period")
    @patch("counter_api.generation.ReportQuery")
    def test_book_report_rejects_inconsistent_index_metrics(
        self, query_class, split_period
    ):
        Collection.objects.create(
            acron3="books",
            main_name="SciELO Livros",
            collection_type="books",
            is_active=True,
        )
        split_period.return_value = ([date(2025, 8, 1)], [], [])
        query_class.return_value.deadline = float("inf")
        query_class.return_value.fetch.return_value = [
            (
                {
                    "key": {
                        "month": "2025-08",
                        "metric_scope": "item",
                        "access_type": "Open",
                        "access_method": "Regular",
                    },
                    "total_investigations": {"value": 2},
                    "unique_investigations": {"value": 2},
                },
                {},
                {},
            )
        ]

        response = self.client.get(
            "/r51/reports/pr",
            {
                "api_key": self.api_key,
                "platform": "books",
                "begin_date": "2025-08",
                "end_date": "2025-08",
            },
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["Code"], 1000)
        self.assertIn("Unique_Title_Investigations is missing", response.json()["Data"])

    @patch("counter_api.generation.split_period")
    @patch("counter_api.generation.ReportQuery")
    def test_report_uses_r51_shape_and_downloads_xlsx(self, query_class, split_period):
        split_period.return_value = (
            [date(2024, 1, 1), date(2024, 2, 1)],
            [],
            [],
        )
        query_class.return_value.fetch.return_value = [
            (
                {
                    "key": {
                        "source_key": "source-1",
                        "document_key": "document-1",
                        "month": "2024-01",
                        "metric_scope": "item",
                        "data_type": "Article",
                        "access_type": "Open",
                        "access_method": "Regular",
                        "publication_year": 2023,
                    },
                    "total_requests": {"value": 4},
                    "total_investigations": {"value": 5},
                    "unique_requests": {"value": 2},
                    "unique_investigations": {"value": 3},
                },
                {
                    "title": "Journal",
                    "publisher_name": ["SciELO"],
                    "identifiers": {"print_issn": "1234-5678"},
                },
                {},
            )
        ]
        query_class.return_value.deadline = float("inf")
        params = {
            "api_key": self.api_key,
            "platform": "scl",
            "begin_date": "2024-01",
            "end_date": "2024-02",
        }

        response = self.client.get("/r51/reports/tr_j3", params)
        payload = response.json()
        item = payload["Report_Items"][0]

        self.assertEqual(response.status_code, 200)
        self.assertIn("Attribute_Performance", item)
        self.assertNotIn("Performance", item)
        self.assertEqual(
            query_class.return_value.fetch.call_args.args[1],
            [date(2024, 1, 1), date(2024, 2, 1)],
        )
        self.assertEqual(
            payload["Report_Header"]["Report_Filters"]["Data_Type"],
            ["Journal"],
        )
        self.assertEqual(
            set(item["Attribute_Performance"][0]),
            {"Access_Type", "Performance"},
        )
        self.assertEqual(
            item["Attribute_Performance"][0]["Performance"][
                "Total_Item_Investigations"
            ]["2024-01"],
            5,
        )
        self.assertNotIn(
            "2024-02",
            item["Attribute_Performance"][0]["Performance"][
                "Total_Item_Investigations"
            ],
        )
        validate_report(payload, "tr_j3")

        params["format"] = "invalid"
        response = self.client.get("/r51/reports/tr_j3", params)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["Report_Header"]["Exceptions"][0]["Code"], 3060
        )

        params["format"] = "xlsx"
        for accept in ("application/json", EXCEL_CONTENT_TYPE):
            response = self.client.get(
                "/r51/reports/tr_j3",
                params,
                HTTP_ACCEPT=accept,
            )
            workbook = load_workbook(
                BytesIO(b"".join(response.streaming_content)),
                read_only=True,
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], EXCEL_CONTENT_TYPE)
            self.assertEqual(
                response["Content-Disposition"],
                'attachment; filename="tr_j3_scl_202401_202402.xlsx"',
            )
            self.assertEqual(workbook.active["A1"].value, "Report_Name")
            self.assertEqual(workbook.active["A15"].value, "Title")
            self.assertEqual(workbook.active["G15"].value, "Print_ISSN")
            self.assertEqual(workbook.active["G16"].value, "1234-5678")
            self.assertNotIn("Begin_Date", workbook.active["B7"].value)

        params["format"] = "tsv"
        response = self.client.get("/r51/reports/tr_j3", params)
        lines = b"".join(response.streaming_content).decode("utf-8").splitlines()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/tab-separated-values")
        self.assertIn("Total_Item_Investigations", lines[5])
        self.assertNotIn("Metric_Type", lines[6])
        self.assertEqual(lines[14].split("\t")[-2:], ["Jan-2024", "Feb-2024"])
        self.assertEqual(lines[15].split("\t")[6], "1234-5678")
