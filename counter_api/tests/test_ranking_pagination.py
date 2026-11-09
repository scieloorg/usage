from datetime import date
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from counter_api.exceptions import CounterAPIError, service_unavailable
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

    def test_subject_keys_are_one_filter_and_all_filters_apply_to_both_queries(self):
        keys = ["source-" + str(i) for i in range(2500)]
        with patch.object(self.query, "_source_keys", return_value=keys):
            self.client.search.side_effect = [
                page([{"country_code": "BR"}]),
                items([]),
            ]

            self.run_query(
                subject_area="Health", country="BR", language="pt", yop="2020"
            )

        self.assertEqual(self.client.search.call_count, 2)
        for call in (0, 1):
            filters = self.body(call)["query"]["bool"]["filter"]
            for clause in (
                {"terms": {"source_key": keys}},
                {"term": {"source_key": "parent-key"}},
                {"term": {"country_code": "BR"}},
                {"term": {"content_language": "pt"}},
                {"terms": {"year": ["2024"]}},
            ):
                self.assertIn(clause, filters)
            self.assertNotIn("publication_year", str(filters))

    def test_yop_filtered_page_keeps_cursor_and_metadata_filter(self):
        self.client.search.side_effect = [
            page([{"country_code": "BR"}], {"country_code": "BR"}),
            items([({"country_code": "BR", "document_key": "old"}, 8)]),
        ]
        self.client.mget.return_value = {
            "docs": [
                {"_id": "old", "found": True, "_source": {"publication_year": 2019}},
            ]
        }

        result = self.run_query(yop="2020", group_limit=1)

        self.assertEqual(result["groups"], [])
        self.assertIsNotNone(result["pagination"]["next_cursor"])

    def test_invalid_cursor_and_scope_changes_fail_before_search(self):
        self.client.search.side_effect = [
            page([{"country_code": "BR"}], {"country_code": "BR"}),
            items([]),
        ]

        cursor = self.run_query(group_limit=1)["pagination"]["next_cursor"]
        self.client.reset_mock()

        changes = [
            {"country": "US"},
            {"language": "en"},
            {"yop": "2020"},
            {"subject_area": "Health"},
            {"parent_id": "other"},
            {"group_by": "language"},
            {"metric_type": "Total_Item_Investigations"},
            {"coverage_policy": "allow_partial"},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaisesRegex(
                CounterAPIError, "does not match"
            ):
                self.run_query(cursor=cursor, **change)

        for invalid in ("", "garbage", cursor + "tampered"):
            with self.subTest(cursor=invalid), self.assertRaisesRegex(
                CounterAPIError, "Invalid ranking cursor"
            ):
                self.run_query(cursor=invalid)

        with self.assertRaisesRegex(CounterAPIError, "does not match"):
            self.query.run(
                self.platform,
                date(2023, 1, 1),
                date(2023, 12, 31),
                {**self.params, "cursor": cursor},
            )

        self.platform.acron3 = "other"
        with self.assertRaisesRegex(CounterAPIError, "does not match"):
            self.run_query(cursor=cursor)
        self.client.search.assert_not_called()

    def test_limits_and_ungrouped_contract(self):
        for params, message in (
            ({"group_limit": 0}, "between 1 and 20"),
            ({"group_limit": 21}, "between 1 and 20"),
            ({"group_limit": "x"}, "between 1 and 20"),
            ({"group_limit": 20, "limit": 501}, "must not exceed 10000"),
            ({"group_by": "", "group_limit": 1}, "require group_by"),
            ({"group_by": "", "cursor": "x"}, "require group_by"),
        ):
            with self.subTest(params=params), self.assertRaisesRegex(
                CounterAPIError, message
            ):
                self.run_query(**params)

        self.client.search.assert_not_called()
        self.client.search.return_value = items([])

        result = self.run_query(group_by="")

        self.assertNotIn("pagination", result)

        self.client.search.return_value = page([])

        result = self.run_query(group_limit=20, limit=500)

        self.assertEqual(result["pagination"], {"group_limit": 20, "next_cursor": None})

    def test_strict_daily_coverage_still_requires_complete_period(self):
        with (
            patch(
                "counter_api.extensions.ranking.resolve_coverage",
                return_value={},
            ),
            patch(
                "counter_api.extensions.ranking.require_complete_period",
                side_effect=service_unavailable(),
            ) as complete,
        ):
            with self.assertRaises(CounterAPIError):
                self.query.run(
                    self.platform,
                    date(2024, 1, 2),
                    date(2024, 1, 6),
                    {**self.params, "group_by": ""},
                )

        complete.assert_called_once_with(
            self.platform, date(2024, 1, 2), date(2024, 1, 6)
        )
        self.client.search.assert_not_called()
