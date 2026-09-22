from datetime import date
from unittest.mock import patch

from django.test import TestCase

from collection.models import Collection
from counter_api.models import APIKey


class CounterViewTests(TestCase):
    def setUp(self):
        self.platform = Collection.objects.create(
            acron3="scl",
            main_name="SciELO Brasil",
            collection_type="journals",
            is_active=True,
        )
        _key, self.api_key = APIKey.issue("tests")

    def test_status_is_public_and_private_routes_require_api_key(self):
        status = self.client.get("/r51/status")
        reports = self.client.get("/r51/reports", {"platform": "scl"})

        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.json()["Service_Active"])
        self.assertEqual(reports.status_code, 401)
        self.assertEqual(reports.json()["Code"], 2020)

    def test_counter_api_ignores_global_jwt_authentication(self):
        response = self.client.get(
            "/r51/platforms",
            {"api_key": self.api_key},
            HTTP_AUTHORIZATION="Bearer invalid",
        )

        self.assertEqual(response.status_code, 200)

    @patch("counter_api.views.available_months")
    def test_report_catalog_uses_completed_months(self, available_months):
        available_months.return_value = [date(2024, 1, 1), date(2024, 8, 1)]

        response = self.client.get(
            "/r51/reports",
            {"api_key": self.api_key, "platform": "scl"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [report["Report_ID"] for report in response.json()],
            ["PR", "TR", "TR_J3", "IR"],
        )
        self.assertEqual(response.json()[0]["First_Month_Available"], "2024-01")
        self.assertEqual(response.json()[0]["Last_Month_Available"], "2024-08")

    def test_swagger_and_schema_are_public_and_limited_to_counter(self):
        docs = self.client.get("/r51/")
        schema = self.client.get("/r51/schema/", HTTP_ACCEPT="application/json")
        payload = schema.json()

        self.assertEqual(docs.status_code, 200)
        self.assertContains(docs, "SwaggerUIBundle")
        self.assertEqual(schema.status_code, 200)
        self.assertEqual(
            set(payload["paths"]),
            {
                "/r51/members",
                "/r51/platforms",
                "/r51/reports",
                "/r51/reports/{report_id}",
                "/r51/status",
                "/r51/extensions/capabilities",
                "/r51/extensions/distribution",
                "/r51/extensions/ranking",
            },
        )
        self.assertEqual(
            payload["components"]["securitySchemes"]["CounterAPIKey"],
            {"type": "apiKey", "in": "query", "name": "api_key"},
        )
