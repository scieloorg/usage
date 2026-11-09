import csv
from datetime import date
from io import BytesIO, StringIO
from unittest.mock import patch

from django.test import TestCase
from openpyxl import load_workbook

from collection.models import Collection
from counter_api.exceptions import service_unavailable
from counter_api.models import APIKey
from counter_api.openapi import EXCEL_CONTENT_TYPE


class ExtensionViewTests(TestCase):
    def setUp(self):
        self.platform = Collection.objects.create(
            acron3="scl",
            main_name="SciELO Brasil",
            collection_type="journals",
            is_active=True,
        )
        _key, self.api_key = APIKey.issue("tests")

    @patch("counter_api.extensions.views.available_months")
    def test_extension_capabilities_show_journal_relations(self, available_months):
        available_months.return_value = [date(2024, 1, 1), date(2024, 8, 1)]

        response = self.client.get(
            "/r51/extensions/capabilities",
            {"platform": "scl"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["ranking_relations"],
            [
                {"entity_type": "journals", "parent_type": "collection"},
                {"entity_type": "articles", "parent_type": "journal"},
            ],
        )
        self.assertNotIn("coverage", response.json())
        self.assertEqual(response.json()["other_granularity"], "day")
        available_months.assert_called_once_with(self.platform, complete_only=False)

    @patch("counter_api.extensions.distribution.ReportQuery")
    def test_default_http_request_includes_partial_coverage(self, report_query):
        search = report_query.return_value.client.search
        search.side_effect = [
            {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "collection": "scl",
                                "month": "2023-03",
                                "day_mask": (1 << 31) - 1 - (1 << 15),
                                "complete": False,
                            }
                        }
                    ]
                }
            },
            {"aggregations": {"rows": {"buckets": []}}},
        ]

        response = self.client.get(
            "/r51/extensions/distribution",
            {
                "platform": "scl",
                "begin_date": "2023-03",
                "end_date": "2023-03",
                "entity_type": "collection",
                "entity_id": "scl",
                "dimension": "yop",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["coverage"]["status"], "partial")
        self.assertEqual(payload["coverage"]["months"][0]["missing_days"], [16])
        self.assertTrue(payload["warnings"])
        self.assertEqual(search.call_count, 2)
        script = search.call_args.kwargs["body"]["aggs"]["rows"]["aggs"]["count"][
            "sum"
        ]["script"]
        self.assertNotIn("16", script["params"]["days"]["2023-03"])
        self.assertEqual(len(script["params"]["days"]["2023-03"]), 30)

    @patch("counter_api.extensions.views.DistributionQuery")
    @patch("counter_api.extensions.views.RankingQuery")
    def test_public_extensions_preserve_values_in_all_formats(
        self, ranking_class, distribution_class
    ):
        cases = (
            (
                "ranking",
                ranking_class,
                {
                    "parent_type": "journal",
                    "parent_id": "Print_ISSN:1234-5678",
                    "entity_type": "articles",
                },
                {
                    "groups": [
                        {
                            "dimensions": {},
                            "items": [
                                {"id": "article-1", "title": "Artigo", "count": 12}
                            ],
                        }
                    ]
                },
                ["Country", "Language", "Rank", "ID", "Title", "Count"],
                [None, None, 1, "article-1", "Artigo", 12],
            ),
            (
                "distribution",
                distribution_class,
                {"entity_type": "collection", "entity_id": "scl", "dimension": "yop"},
                {
                    "dimension": "yop",
                    "total": 12,
                    "buckets": [{"dimensions": {"yop": 2024}, "count": 12}],
                },
                ["Yop", "Count"],
                [2024, 12],
            ),
        )
        for kind, query_class, filters, payload, headings, row in cases:
            query_class.return_value.run.return_value = payload
            for key_state, key in (
                ("absent", None),
                ("valid", self.api_key),
            ):
                for output_format in ("json", "csv", "xlsx"):
                    with self.subTest(kind=kind, key=key_state, format=output_format):
                        params = {
                            "platform": "scl",
                            "begin_date": "2024-01",
                            "end_date": "2024-01",
                            "format": output_format,
                            **filters,
                        }
                        if key is not None:
                            params["api_key"] = key
                        response = self.client.get(f"/r51/extensions/{kind}", params)
                        self.assertEqual(response.status_code, 200)
                        if output_format == "json":
                            self.assertEqual(response.json(), payload)
                            continue
                        content = b"".join(response.streaming_content)
                        if output_format == "csv":
                            self.assertEqual(response["Content-Type"], "text/csv")
                            rows = list(csv.reader(StringIO(content.decode("utf-8"))))
                            self.assertEqual(
                                rows,
                                [headings, ["" if v is None else str(v) for v in row]],
                            )
                        else:
                            self.assertEqual(
                                response["Content-Type"], EXCEL_CONTENT_TYPE
                            )
                            workbook = load_workbook(BytesIO(content), read_only=True)
                            self.assertEqual(
                                list(workbook.active.values),
                                [tuple(headings), tuple(row)],
                            )
                            workbook.close()

    @patch("counter_api.extensions.views.DistributionQuery")
    @patch("counter_api.extensions.views.RankingQuery")
    def test_public_extensions_do_not_turn_failures_into_empty_success(
        self, ranking_class, distribution_class
    ):
        for kind, query_class in (
            ("ranking", ranking_class),
            ("distribution", distribution_class),
        ):
            query_class.return_value.run.side_effect = service_unavailable()
            for output_format in ("json", "csv", "xlsx"):
                with self.subTest(kind=kind, format=output_format):
                    response = self.client.get(
                        f"/r51/extensions/{kind}",
                        {
                            "platform": "scl",
                            "begin_date": "2024-01",
                            "end_date": "2024-01",
                            "format": output_format,
                        },
                    )
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.json()["Code"], 1000)

    @patch("counter_api.extensions.views.DistributionQuery")
    @patch("counter_api.extensions.views.RankingQuery")
    def test_public_extensions_still_reject_current_and_future_months(
        self, ranking_class, distribution_class
    ):
        for month in (date.today().strftime("%Y-%m"), "9999-12"):
            for kind in ("ranking", "distribution"):
                with self.subTest(kind=kind, month=month):
                    response = self.client.get(
                        f"/r51/extensions/{kind}",
                        {"platform": "scl", "begin_date": month, "end_date": month},
                    )
                    self.assertEqual(response.status_code, 400)
        ranking_class.return_value.run.assert_not_called()
        distribution_class.return_value.run.assert_not_called()
