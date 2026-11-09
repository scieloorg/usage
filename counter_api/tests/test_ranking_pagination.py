from datetime import date
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from counter_api.extensions.ranking import RankingQuery


def page(keys, after=None):
    rows = {"buckets": [{"key": key} for key in keys]}
    if after is not None:
        rows["after_key"] = after
    return {"aggregations": {"rows": rows}}


def items(rows, after=None):
    result = page([key for key, count in rows], after)
    for bucket, (_, count) in zip(result["aggregations"]["rows"]["buckets"], rows):
        bucket["count"] = {"value": count}
    return result


class RankingPaginationTests(TestCase):
    def setUp(self):
        for target in ("resolve_coverage", "require_complete_period"):
            patcher = patch(
                "counter_api.extensions.ranking." + target, return_value=None
            )
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = Mock()
        self.client.mget.return_value = {"docs": []}
        self.query = RankingQuery(Mock(client=self.client))
        self.query.report_query.resolve_item_id.return_value = "parent-key"
        self.platform = SimpleNamespace(acron3="scl", collection_type="journals")
        self.params = {
            "entity_type": "articles",
            "parent_type": "journal",
            "parent_id": "journal",
            "group_by": "country",
            "coverage_policy": "strict",
        }

    def run_query(self, **params):
        return self.query.run(
            self.platform,
            date(2024, 1, 1),
            date(2024, 12, 31),
            {**self.params, **params},
        )

    def body(self, call):
        return self.client.search.call_args_list[call].kwargs["body"]

    def test_exact_tuple_filter_includes_missing_values(self):
        keys = [
            {"country_code": "BR", "content_language": "pt"},
            {"country_code": None, "content_language": "en"},
        ]
        self.client.search.side_effect = [
            page(keys),
            items([({**keys[1], "document_key": "a"}, 3)]),
        ]

        result = self.run_query(group_by="country,language")

        selection = self.body(1)["query"]["bool"]["filter"][-1]["bool"]
        clauses = [clause["bool"]["filter"] for clause in selection["should"]]
        self.assertEqual(selection["minimum_should_match"], 1)
        self.assertEqual(
            clauses,
            [
                [
                    {"term": {"country_code": "BR"}},
                    {"term": {"content_language": "pt"}},
                ],
                [
                    {"bool": {"must_not": [{"exists": {"field": "country_code"}}]}},
                    {"term": {"content_language": "en"}},
                ],
            ],
        )
        self.assertEqual(
            result["groups"][0]["dimensions"], {"country": "Unknown", "language": "en"}
        )
        self.assertIsNone(result["pagination"]["next_cursor"])

    def test_zero_count_page_still_advances_and_short_page_finishes(self):
        self.client.search.side_effect = [
            page([{"country_code": "BR"}], {"country_code": "BR"}),
            items([({"country_code": "BR", "document_key": "a"}, 0)]),
        ]

        result = self.run_query(group_limit=1)

        self.assertEqual(result["groups"], [])
        self.assertIsNotNone(result["pagination"]["next_cursor"])

        self.client.search.side_effect = [
            page([{"country_code": "US"}], {"country_code": "US"}),
            items([]),
        ]

        result = self.run_query(
            cursor=result["pagination"]["next_cursor"], group_limit=2
        )

        self.assertIsNone(result["pagination"]["next_cursor"])
