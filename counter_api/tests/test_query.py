from datetime import date
from unittest.mock import Mock, patch

from django.test import TestCase

from counter_api.exceptions import CounterAPIError
from counter_api.query import ReportQuery


class ReportQueryTests(TestCase):
    def test_item_id_resolution_is_scoped_to_collection(self):
        client = Mock()
        client.search.return_value = {"hits": {"hits": [{"_id": "article-key"}]}}
        query = ReportQuery(Mock(client=client))

        key = query.resolve_item_id(Mock(acron3="scl"), "ir", "DOI:10.1234/example")
        body = client.search.call_args.kwargs["body"]
        report_body = query._query_body(
            [date(2024, 1, 1)],
            None,
            "ir",
            {"Item_Key": key},
        )

        self.assertEqual(key, "article-key")
        self.assertIn({"term": {"collection": "scl"}}, body["query"]["bool"]["filter"])
        self.assertIn(
            {"term": {"document_key": "article-key"}},
            report_body["query"]["bool"]["filter"],
        )

        client.search.return_value = {
            "hits": {"hits": [{"_id": "one"}, {"_id": "two"}]}
        }
        with self.assertRaises(CounterAPIError):
            query.resolve_item_id(Mock(acron3="scl"), "ir", "DOI:10.1234/example")

    def test_partial_shard_failure_does_not_return_report(self):
        client = Mock()
        client.search.return_value = {"_shards": {"failed": 1}}
        query = ReportQuery(Mock(client=client))

        with self.assertRaises(CounterAPIError):
            list(query.fetch(Mock(acron3="scl"), [date(2024, 1, 1)]))

    def test_platform_query_does_not_group_by_items(self):
        query = ReportQuery(Mock(client=Mock()))

        body = query._query_body([date(2024, 1, 1)], None, "pr")
        sources = body["aggs"]["rows"]["composite"]["sources"]
        fields = {next(iter(source)) for source in sources}

        self.assertNotIn("source_key", fields)
        self.assertNotIn("document_key", fields)
        self.assertIn("month", fields)

    def test_query_applies_access_filters_before_aggregation(self):
        query = ReportQuery(Mock(client=Mock()))

        body = query._query_body(
            [date(2024, 1, 1)],
            None,
            "tr_j3",
            {"Access_Type": ["Open"], "Access_Method": ["Regular"]},
        )
        filters = body["query"]["bool"]["filter"]

        self.assertIn({"terms": {"access_type": ["Open"]}}, filters)
        self.assertIn({"terms": {"access_method": ["Regular"]}}, filters)
        self.assertFalse(body["track_total_hits"])

    def test_query_applies_yop_list_and_range_in_opensearch(self):
        query = ReportQuery(Mock(client=Mock()))

        body = query._query_body(
            [date(2024, 1, 1)],
            None,
            "ir",
            {"YOP": ["2020", "2022-2023"], "Data_Type": ["Article"]},
        )
        filters = body["query"]["bool"]["filter"]

        self.assertIn({"terms": {"data_type": ["Article"]}}, filters)
        self.assertIn({"term": {"metric_scope": "item"}}, filters)
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

    @patch("counter_api.metadata.METADATA_BATCH_SIZE", 1)
    def test_composite_query_reads_every_page_and_metadata_in_batches(self):
        client = Mock()
        client.search.side_effect = [
            {
                "aggregations": {
                    "rows": {
                        "buckets": [
                            {
                                "key": {
                                    "source_key": "source-1",
                                    "document_key": "document-1",
                                }
                            }
                        ],
                        "after_key": {"document_key": "document-1"},
                    }
                }
            },
            {
                "aggregations": {
                    "rows": {
                        "buckets": [
                            {
                                "key": {
                                    "source_key": "source-2",
                                    "document_key": "document-2",
                                }
                            }
                        ]
                    }
                }
            },
        ]
        client.mget.side_effect = [
            {
                "docs": [
                    {"_id": "source-1", "found": True, "_source": {"title": "A"}},
                ]
            },
            {
                "docs": [
                    {"_id": "document-1", "found": True, "_source": {"title": "C"}},
                ]
            },
            {
                "docs": [
                    {"_id": "source-2", "found": True, "_source": {"title": "B"}},
                ]
            },
            {
                "docs": [
                    {"_id": "document-2", "found": True, "_source": {"title": "D"}},
                ]
            },
        ]
        usage_client = Mock(client=client)
        platform = Mock(acron3="scl")

        records = list(ReportQuery(usage_client).fetch(platform, [date(2024, 1, 1)]))

        self.assertEqual(len(records), 2)
        self.assertEqual({source["title"] for _, source, _ in records}, {"A", "B"})
        self.assertEqual({document["title"] for _, _, document in records}, {"C", "D"})
        self.assertEqual(client.search.call_count, 2)
        self.assertEqual(client.mget.call_count, 4)
