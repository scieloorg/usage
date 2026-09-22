from datetime import date
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from counter_api.exceptions import CounterAPIError
from counter_api.extensions.ranking import RankingQuery


class RankingQueryTests(TestCase):
    def test_ranking_reads_all_pages_and_breaks_ties_by_item_key(self):
        client = Mock()
        client.search.side_effect = [
            {
                "aggregations": {
                    "rows": {
                        "buckets": [
                            {
                                "key": {
                                    "country_code": "BR",
                                    "content_language": "pt",
                                    "document_key": "item-b",
                                },
                                "count": {"value": 10},
                            }
                        ],
                        "after_key": {"document_key": "item-b"},
                    }
                }
            },
            {
                "aggregations": {
                    "rows": {
                        "buckets": [
                            {
                                "key": {
                                    "country_code": "BR",
                                    "content_language": "pt",
                                    "document_key": "item-a",
                                },
                                "count": {"value": 10},
                            }
                        ]
                    }
                }
            },
        ]
        client.mget.return_value = {
            "docs": [
                {"_id": "item-a", "found": True, "_source": {"title": "Article A"}}
            ]
        }
        query = RankingQuery(Mock(client=client))
        platform = SimpleNamespace(acron3="scl", collection_type="journals")

        query.report_query.resolve_item_id.return_value = "journal-key"
        result = query.run(
            platform,
            date(2025, 1, 1),
            date(2025, 12, 31),
            {
                "entity_type": "articles",
                "parent_type": "journal",
                "parent_id": "Print_ISSN:1234-5678",
                "group_by": "country,language",
                "limit": "1",
            },
        )

        self.assertEqual(
            result["groups"][0]["dimensions"], {"country": "BR", "language": "pt"}
        )
        self.assertEqual(
            result["groups"][0]["items"],
            [{"id": "item-a", "title": "Article A", "count": 10}],
        )
        self.assertEqual(client.search.call_count, 2)
        body = client.search.call_args_list[0].kwargs["body"]
        self.assertIn({"terms": {"year": ["2025"]}}, body["query"]["bool"]["filter"])
        self.assertIn(
            {"term": {"source_key": "journal-key"}}, body["query"]["bool"]["filter"]
        )

    def test_country_ranking_requires_complete_year(self):
        query = RankingQuery(Mock(client=Mock()))
        platform = SimpleNamespace(acron3="scl", collection_type="journals")

        with self.assertRaises(CounterAPIError):
            query.run(
                platform,
                date(2025, 1, 1),
                date(2025, 6, 30),
                {
                    "entity_type": "journals",
                    "parent_type": "collection",
                    "parent_id": "scl",
                    "group_by": "country",
                },
            )

    def test_subject_area_keys_and_yop_are_filtered_before_aggregation(self):
        client = Mock()
        client.search.side_effect = [
            {"hits": {"hits": [{"_id": "journal-1", "sort": ["journal-1"]}]}},
            {
                "aggregations": {
                    "rows": {
                        "buckets": [
                            {
                                "key": {"source_key": "journal-1"},
                                "count": {"value": 8},
                            }
                        ]
                    }
                }
            },
        ]
        client.mget.return_value = {
            "docs": [
                {
                    "_id": "journal-1",
                    "found": True,
                    "_source": {"title": "Journal"},
                }
            ]
        }
        query = RankingQuery(Mock(client=client))
        platform = SimpleNamespace(acron3="scl", collection_type="journals")

        result = query.run(
            platform,
            date(2024, 1, 1),
            date(2024, 12, 31),
            {
                "entity_type": "journals",
                "parent_type": "collection",
                "parent_id": "scl",
                "subject_area": "Health",
                "yop": "2020|2022-2023",
            },
        )

        self.assertEqual(result["groups"][0]["items"][0]["id"], "journal-1")
        metadata_body = client.search.call_args_list[0].kwargs["body"]
        self.assertIn(
            {"term": {"subject_areas": "Health"}},
            metadata_body["query"]["bool"]["filter"],
        )
        facts_body = client.search.call_args_list[1].kwargs["body"]
        filters = facts_body["query"]["bool"]["filter"]
        self.assertIn({"terms": {"source_key": ["journal-1"]}}, filters)
        self.assertIn(
            {
                "bool": {
                    "should": [
                        {"term": {"publication_year": 2020}},
                        {"range": {"publication_year": {"gte": 2022, "lte": 2023}}},
                    ],
                    "minimum_should_match": 1,
                }
            },
            filters,
        )

    def test_country_ranking_filters_yop_with_document_metadata(self):
        client = Mock()
        client.search.return_value = {
            "aggregations": {
                "rows": {
                    "buckets": [
                        {
                            "key": {"country_code": "BR", "document_key": "old"},
                            "count": {"value": 12},
                        },
                        {
                            "key": {"country_code": "BR", "document_key": "new"},
                            "count": {"value": 8},
                        },
                    ]
                }
            }
        }
        client.mget.return_value = {
            "docs": [
                {
                    "_id": "old",
                    "found": True,
                    "_source": {"title": "Old", "publication_year": 2019},
                },
                {
                    "_id": "new",
                    "found": True,
                    "_source": {"title": "New", "publication_year": 2022},
                },
            ]
        }
        query = RankingQuery(Mock(client=client))
        platform = SimpleNamespace(acron3="scl", collection_type="journals")

        result = query.run(
            platform,
            date(2024, 1, 1),
            date(2024, 12, 31),
            {
                "entity_type": "articles",
                "parent_type": "journal",
                "parent_id": "Print_ISSN:1234-5678",
                "group_by": "country",
                "yop": "2020-2023",
            },
        )

        self.assertEqual(
            result["groups"][0]["items"],
            [{"id": "new", "title": "New", "count": 8}],
        )
        filters = client.search.call_args.kwargs["body"]["query"]["bool"]["filter"]
        self.assertFalse(any("publication_year" in str(item) for item in filters))
