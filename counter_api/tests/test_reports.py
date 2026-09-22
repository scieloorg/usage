from datetime import date
from unittest.mock import Mock

from django.test import TestCase
from openpyxl import load_workbook

from counter_api.reports import build_report
from counter_api.tabular import build_workbook
from counter_api.tests.schema import validate_report


class ReportSemanticsTests(TestCase):
    def test_empty_item_report_has_no_empty_group(self):
        platform = Mock(
            acron3="books",
            main_name="SciELO Livros",
            collection_type="books",
        )

        report = build_report(
            "ir",
            platform,
            date(2024, 1, 1),
            date(2024, 1, 31),
            [],
            {},
        )

        self.assertEqual(report["Report_Items"], [])
        validate_report(report, "ir")

    def test_item_report_groups_parent_and_adds_tabular_parent_columns(self):
        platform = Mock(
            acron3="scl",
            main_name="SciELO Brasil",
            collection_type="journals",
        )
        bucket = {
            "key": {
                "source_key": "journal-1",
                "document_key": "article-1",
                "month": "2024-01",
                "metric_scope": "item",
                "data_type": "Article",
                "parent_data_type": "Journal",
                "access_type": "Open",
                "access_method": "Regular",
                "publication_year": 2020,
            },
            "total_requests": {"value": 3},
        }
        source = {
            "title": "Journal",
            "identifiers": {"print_issn": "1234-5678"},
        }
        document = {"title": "Article", "identifiers": {"doi": "10.1234/article"}}

        report = build_report(
            "ir",
            platform,
            date(2024, 1, 1),
            date(2024, 1, 31),
            [(bucket, source, document)],
            {"Include_Parent_Details": True},
        )
        parent = report["Report_Items"][0]

        self.assertEqual(parent["Title"], "Journal")
        self.assertEqual(parent["Data_Type"], "Journal")
        self.assertEqual(parent["Item_ID"]["Print_ISSN"], "1234-5678")
        self.assertEqual(parent["Items"][0]["Item"], "Article")
        self.assertEqual(
            report["Report_Header"]["Report_Attributes"]["Include_Parent_Details"],
            "True",
        )
        validate_report(report, "ir")

        workbook = build_workbook(report)
        sheet = load_workbook(workbook, read_only=True).active
        headings = [cell.value for cell in sheet[15]]
        self.assertEqual(sheet["K16"].value, "Journal")
        self.assertIn("Parent_Print_ISSN", headings)
        self.assertEqual(sheet["S16"].value, "1234-5678")

    def test_global_item_report_for_journal_collection_uses_article_metadata(self):
        platform = Mock(
            acron3="scl",
            main_name="SciELO Brasil",
            collection_type="journals",
        )
        rows = [
            {
                "key": {
                    "source_key": "journal-1",
                    "document_key": "article-1",
                    "month": "2024-01",
                    "metric_scope": "item",
                    "data_type": "Article",
                    "access_type": "Open",
                    "access_method": "Regular",
                    "publication_year": 2020,
                },
                "total_requests": {"value": 3},
                "total_investigations": {"value": 4},
                "unique_requests": {"value": 2},
                "unique_investigations": {"value": 2},
            }
        ]

        report = build_report(
            "ir",
            platform,
            date(2024, 1, 1),
            date(2024, 1, 31),
            [
                (
                    rows[0],
                    {"title": "Journal"},
                    {
                        "title": "Article",
                        "identifiers": {"doi": "10.1234/article"},
                    },
                )
            ],
            {},
        )
        item = report["Report_Items"][0]["Items"][0]

        self.assertEqual(item["Item"], "Article")
        self.assertEqual(item["Item_ID"]["DOI"], "10.1234/article")
        self.assertEqual(item["Attribute_Performance"][0]["Data_Type"], "Article")
        validate_report(report, "ir")

    def test_book_item_report_excludes_title_scope_metrics(self):
        platform = Mock(
            acron3="books",
            main_name="SciELO Livros",
            collection_type="books",
        )
        common = {
            "source_key": "book-1",
            "document_key": "chapter-1",
            "month": "2024-01",
            "data_type": "Book_Segment",
            "access_type": "Open",
            "access_method": "Regular",
            "publication_year": 2020,
        }
        rows = [
            {
                "key": {**common, "metric_scope": scope},
                "total_requests": {"value": 3},
                "unique_requests": {"value": 2},
            }
            for scope in ("item", "title")
        ]

        report = build_report(
            "ir",
            platform,
            date(2024, 1, 1),
            date(2024, 1, 31),
            (
                (
                    row,
                    {"title": "Book"},
                    {
                        "title": "Chapter",
                        "identifiers": {
                            "book_id": "book-1",
                            "chapter_id": "chapter-1",
                            "pid_generic": "BOOK:BOOK-1/CHAPTER:CHAPTER-1",
                        },
                    },
                )
                for row in rows
            ),
            {},
        )
        item = report["Report_Items"][0]["Items"][0]
        performance = item["Attribute_Performance"][0]["Performance"]

        self.assertEqual(performance["Total_Item_Requests"]["2024-01"], 3)
        self.assertNotIn("Unique_Title_Requests", performance)
        self.assertEqual(
            item["Item_ID"]["Proprietary"],
            "BOOK:BOOK-1/CHAPTER:CHAPTER-1",
        )

    def test_platform_report_aggregates_sources(self):
        platform = Mock(
            acron3="scl",
            main_name="SciELO Brasil",
            collection_type="journals",
        )
        rows = []
        for source_key in ("source-1", "source-2"):
            rows.append(
                {
                    "key": {
                        "source_key": source_key,
                        "document_key": f"document-{source_key}",
                        "month": "2024-01",
                        "metric_scope": "item",
                        "data_type": "Article",
                        "access_type": "Open",
                        "access_method": "Regular",
                        "publication_year": 2020,
                    },
                    "total_requests": {"value": 1},
                    "total_investigations": {"value": 1},
                    "unique_requests": {"value": 1},
                    "unique_investigations": {"value": 1},
                }
            )

        report = build_report(
            "pr",
            platform,
            date(2024, 1, 1),
            date(2024, 1, 31),
            (
                (
                    row,
                    {
                        "publisher_name": [
                            "Publisher A" if index == 0 else "Publisher B"
                        ]
                    },
                    {},
                )
                for index, row in enumerate(rows)
            ),
            {},
        )
        performance = report["Report_Items"][0]["Attribute_Performance"][0][
            "Performance"
        ]

        self.assertEqual(len(report["Report_Items"]), 1)
        self.assertEqual(performance["Total_Item_Requests"]["2024-01"], 2)
        self.assertEqual(report["Report_Header"]["Exceptions"][0]["Code"], 3040)
        self.assertEqual(report["Report_Items"][0]["Platform"], "scl")
        self.assertRegex(
            report["Report_Header"]["Created"],
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
        )
        validate_report(report, "pr")

    def test_book_title_metrics_are_not_counted_as_item_metrics(self):
        platform = Mock(
            acron3="books",
            main_name="SciELO Livros",
            collection_type="books",
        )
        common = {
            "source_key": "source-1",
            "document_key": "document-1",
            "month": "2024-01",
            "data_type": "Book",
            "access_type": "Open",
            "access_method": "Regular",
            "publication_year": 2020,
        }
        rows = [
            {
                "key": {**common, "metric_scope": "item"},
                "total_requests": {"value": 3},
                "total_investigations": {"value": 4},
                "unique_requests": {"value": 2},
                "unique_investigations": {"value": 2},
            },
            {
                "key": {**common, "metric_scope": "title"},
                "total_requests": {"value": 3},
                "total_investigations": {"value": 4},
                "unique_requests": {"value": 0},
                "unique_investigations": {"value": 1},
            },
        ]

        report = build_report(
            "tr_b3",
            platform,
            date(2024, 1, 1),
            date(2024, 1, 31),
            (
                (
                    row,
                    {
                        "title": "Book",
                        "identifiers": {
                            "doi": "https://doi.org/10.1234/example",
                            "isbn": "8575410326",
                        },
                    },
                    {},
                )
                for row in rows
            ),
            {},
        )
        performance = report["Report_Items"][0]["Attribute_Performance"][0][
            "Performance"
        ]

        self.assertEqual(performance["Total_Item_Requests"]["2024-01"], 3)
        self.assertNotIn("Unique_Title_Requests", performance)
        self.assertEqual(report["Report_Items"][0]["Item_ID"]["DOI"], "10.1234/example")
        self.assertEqual(
            report["Report_Items"][0]["Item_ID"]["ISBN"],
            "978-85-7541-032-5",
        )
        self.assertNotIn("Exceptions", report["Report_Header"])
        validate_report(report, "tr_b3")

    def test_title_report_omits_zero_metric_types(self):
        platform = Mock(
            acron3="books",
            main_name="SciELO Livros",
            collection_type="books",
        )
        common = {
            "source_key": "source-1",
            "month": "2024-01",
            "data_type": "Book",
            "access_type": "Open",
            "access_method": "Regular",
            "publication_year": 2020,
        }
        title_bucket = {
            "key": {
                **common,
                "metric_scope": "title",
            },
            "unique_investigations": {"value": 1},
            "unique_requests": {"value": 0},
        }
        item_bucket = {
            "key": {
                **common,
                "metric_scope": "item",
            },
            "total_investigations": {"value": 1},
            "unique_investigations": {"value": 1},
        }

        report = build_report(
            "tr",
            platform,
            date(2024, 1, 1),
            date(2024, 1, 31),
            [
                (item_bucket, {"title": "Book"}, {}),
                (title_bucket, {"title": "Book"}, {}),
            ],
            {},
        )
        performance = report["Report_Items"][0]["Attribute_Performance"][0][
            "Performance"
        ]

        self.assertNotIn("Unique_Title_Requests", performance)
        validate_report(report, "tr")

    def test_book_report_preserves_inconsistent_title_metrics_for_diagnosis(self):
        platform = Mock(
            acron3="books",
            main_name="SciELO Livros",
            collection_type="books",
        )
        common = {
            "source_key": "source-1",
            "month": "2024-01",
            "data_type": "Book",
            "access_type": "Open",
            "access_method": "Regular",
            "publication_year": 2020,
        }
        rows = [
            {
                "key": {**common, "metric_scope": "item"},
                "total_investigations": {"value": 3},
                "unique_investigations": {"value": 2},
                "total_requests": {"value": 3},
                "unique_requests": {"value": 3},
            },
            {
                "key": {**common, "metric_scope": "title"},
                "unique_investigations": {"value": 4},
                "unique_requests": {"value": 3},
            },
        ]

        report = build_report(
            "tr_b3",
            platform,
            date(2024, 1, 1),
            date(2024, 1, 31),
            ((row, {"title": "Book"}, {}) for row in rows),
            {},
        )
        performance = report["Report_Items"][0]["Attribute_Performance"][0][
            "Performance"
        ]

        self.assertEqual(performance["Unique_Title_Investigations"]["2024-01"], 4)
        self.assertEqual(performance["Unique_Title_Requests"]["2024-01"], 3)
        validate_report(report, "tr_b3")
