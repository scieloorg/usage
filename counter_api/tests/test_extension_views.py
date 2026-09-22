from datetime import date
from unittest.mock import patch

from django.test import TestCase

from collection.models import Collection
from counter_api.models import APIKey


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
            {"api_key": self.api_key, "platform": "scl"},
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

    @patch("counter_api.extensions.views.RankingQuery")
    def test_extension_ranking_download_uses_same_result(self, query_class):
        query_class.return_value.run.return_value = {
            "groups": [
                {
                    "dimensions": {},
                    "items": [{"id": "article-1", "title": "Artigo", "count": 12}],
                }
            ]
        }
        response = self.client.get(
            "/r51/extensions/ranking",
            {
                "api_key": self.api_key,
                "platform": "scl",
                "begin_date": "2025-08",
                "end_date": "2025-08",
                "parent_type": "journal",
                "parent_id": "Print_ISSN:1234-5678",
                "entity_type": "articles",
                "format": "csv",
            },
        )

        lines = b"".join(response.streaming_content).decode("utf-8").splitlines()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertEqual(lines[1], ",,1,article-1,Artigo,12")
