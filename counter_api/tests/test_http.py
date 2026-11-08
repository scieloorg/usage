from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings

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
        self.key, self.api_key = APIKey.issue("tests")

    @override_settings(
        REST_FRAMEWORK={
            "DEFAULT_AUTHENTICATION_CLASSES": [
                "rest_framework_simplejwt.authentication.JWTAuthentication"
            ],
            "DEFAULT_PERMISSION_CLASSES": [
                "rest_framework.permissions.IsAuthenticated"
            ],
            "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        }
    )
    @patch("counter_api.extensions.views.available_months")
    @patch("counter_api.views.available_months")
    def test_discovery_is_public_with_optional_valid_keys(
        self, available_months, extension_months
    ):
        available_months.return_value = [date(2024, 1, 1)]
        extension_months.return_value = [date(2024, 1, 1)]
        paths = (
            "/r51/members",
            "/r51/platforms",
            "/r51/reports",
            "/r51/extensions/capabilities",
        )
        for path in paths:
            expected = self.client.get(path, {"platform": "scl"})
            self.assertEqual(expected.status_code, 200)
            for key in (None, self.api_key):
                with self.subTest(path=path, key_state=(key is None, key == "")):
                    params = {"platform": "scl"}
                    if key is not None:
                        params["api_key"] = key
                    response = self.client.get(
                        path, params, HTTP_AUTHORIZATION="Bearer invalid"
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), expected.json())
        self.key.refresh_from_db()
        self.assertIsNotNone(self.key.last_used_at)

    @patch("counter_api.views.available_months")
    def test_report_catalog_uses_completed_months(self, available_months):
        available_months.return_value = [date(2024, 1, 1), date(2024, 8, 1)]
        response = self.client.get("/r51/reports", {"platform": "scl"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [report["Report_ID"] for report in response.json()],
            ["PR", "TR", "TR_J3", "IR"],
        )
        self.assertEqual(response.json()[0]["First_Month_Available"], "2024-01")
        self.assertEqual(response.json()[0]["Last_Month_Available"], "2024-08")

    def test_customer_validation_is_preserved_without_a_key(self):
        for path in ("/r51/members", "/r51/reports", "/r51/reports/tr"):
            with self.subTest(path=path):
                response = self.client.get(
                    path, {"customer_id": "other-institution", "platform": "scl"}
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["Code"], 2010)

    def test_public_api_does_not_accept_writes(self):
        for path in (
            "/r51/status",
            "/r51/members",
            "/r51/platforms",
            "/r51/reports",
            "/r51/reports/tr",
            "/r51/extensions/capabilities",
            "/r51/extensions/ranking",
            "/r51/extensions/distribution",
        ):
            for method in ("post", "put", "patch", "delete"):
                with self.subTest(path=path, method=method):
                    response = getattr(self.client, method)(path)
                    self.assertEqual(response.status_code, 405)

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
