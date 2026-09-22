from datetime import date
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from counter_api.exceptions import CounterAPIError
from counter_api.extensions.distribution import DistributionQuery


class DistributionQueryTests(TestCase):
    def setUp(self):
        period = patch(
            "counter_api.extensions.query.split_period", return_value=([], [], [])
        )
        self.period = period.start()
        self.addCleanup(period.stop)

    def test_incomplete_month_does_not_query_metrics(self):
        client = Mock()
        query = DistributionQuery(Mock(client=client))
        platform = SimpleNamespace(acron3="scl", collection_type="journals")
        self.period.return_value = ([], [date(2025, 2, 1)], [])

        with self.assertRaises(CounterAPIError) as error:
            query.run(
                platform,
                date(2025, 2, 1),
                date(2025, 2, 28),
                {"entity_type": "collection", "entity_id": "scl", "dimension": "yop"},
            )

        self.assertEqual(error.exception.status_code, 503)
        client.search.assert_not_called()

    def test_subject_areas_overlap_without_inflating_total(self):
        client = Mock()
        client.search.return_value = {
            "aggregations": {
                "rows": {
                    "buckets": [
                        {
                            "key": {"subject_area": "source-1"},
                            "count": {"value": 5},
                        },
                        {
                            "key": {"subject_area": "source-2"},
                            "count": {"value": 2},
                        },
                    ]
                }
            }
        }
        client.mget.return_value = {
            "docs": [
                {
                    "_id": "source-1",
                    "found": True,
                    "_source": {"subject_areas": ["Health", "Science"]},
                }
            ]
        }
        query = DistributionQuery(Mock(client=client))
        platform = SimpleNamespace(acron3="scl", collection_type="journals")

        result = query.run(
            platform,
            date(2024, 1, 1),
            date(2024, 1, 31),
            {
                "entity_type": "collection",
                "entity_id": "scl",
                "dimension": "subject_area",
            },
        )

        self.assertEqual(result["total"], 7)
        self.assertEqual(
            result["buckets"],
            [
                {
                    "value": "Health",
                    "dimensions": {"subject_area": "Health"},
                    "count": 5,
                },
                {
                    "value": "Science",
                    "dimensions": {"subject_area": "Science"},
                    "count": 5,
                },
                {
                    "value": "Unknown",
                    "dimensions": {"subject_area": "Unknown"},
                    "count": 2,
                },
            ],
        )

    def test_yop_distribution_combines_missing_and_unknown_year(self):
        client = Mock()
        client.search.side_effect = [
            {
                "aggregations": {
                    "rows": {
                        "buckets": [
                            {
                                "key": {"yop": None},
                                "count": {"value": 3},
                            }
                        ],
                        "after_key": {"yop": None},
                    }
                }
            },
            {
                "aggregations": {
                    "rows": {
                        "buckets": [
                            {
                                "key": {"yop": 1},
                                "count": {"value": 2},
                            },
                            {
                                "key": {"yop": 2020},
                                "count": {"value": 7},
                            },
                        ]
                    }
                }
            },
        ]
        query = DistributionQuery(Mock(client=client))
        platform = SimpleNamespace(acron3="scl", collection_type="journals")

        result = query.run(
            platform,
            date(2024, 1, 1),
            date(2024, 2, 29),
            {
                "entity_type": "collection",
                "entity_id": "scl",
                "dimension": "yop",
            },
        )

        self.assertEqual(result["total"], 12)
        self.assertEqual(
            result["buckets"],
            [
                {
                    "value": "2020",
                    "dimensions": {"yop": "2020"},
                    "count": 7,
                },
                {
                    "value": "0001",
                    "dimensions": {"yop": "0001"},
                    "count": 5,
                },
            ],
        )
        body = client.search.call_args_list[0].kwargs["body"]
        self.assertIn(
            {"terms": {"month": ["2024-01", "2024-02"]}},
            body["query"]["bool"]["filter"],
        )

    def test_country_language_cross_uses_annual_index(self):
        client = Mock()
        client.search.return_value = {
            "aggregations": {
                "rows": {
                    "buckets": [
                        {
                            "key": {"country": "BR", "language": "pt"},
                            "count": {"value": 9},
                        }
                    ]
                }
            }
        }
        query = DistributionQuery(Mock(client=client))
        platform = SimpleNamespace(acron3="scl", collection_type="journals")

        result = query.run(
            platform,
            date(2024, 1, 1),
            date(2024, 12, 31),
            {
                "entity_type": "collection",
                "entity_id": "scl",
                "dimension": "country,language",
            },
        )

        self.assertEqual(result["dimensions"], ["country", "language"])
        self.assertEqual(
            result["buckets"],
            [
                {
                    "value": "BR | pt",
                    "dimensions": {"country": "BR", "language": "pt"},
                    "count": 9,
                }
            ],
        )
        body = client.search.call_args.kwargs["body"]
        sources = body["aggs"]["rows"]["composite"]["sources"]
        self.assertEqual(
            sources,
            [
                {
                    "country": {
                        "terms": {"field": "country_code", "missing_bucket": True}
                    }
                },
                {
                    "language": {
                        "terms": {
                            "field": "content_language",
                            "missing_bucket": True,
                        }
                    }
                },
            ],
        )

    def test_country_yop_reads_year_from_document_metadata(self):
        client = Mock()
        client.search.return_value = {
            "aggregations": {
                "rows": {
                    "buckets": [
                        {
                            "key": {"country": "BR", "document_key": "article-1"},
                            "count": {"value": 9},
                        }
                    ]
                }
            }
        }
        client.mget.return_value = {
            "docs": [
                {
                    "_id": "article-1",
                    "found": True,
                    "_source": {"publication_year": 2020},
                }
            ]
        }
        query = DistributionQuery(Mock(client=client))
        platform = SimpleNamespace(acron3="scl", collection_type="journals")

        result = query.run(
            platform,
            date(2024, 1, 1),
            date(2024, 12, 31),
            {
                "entity_type": "collection",
                "entity_id": "scl",
                "dimension": "country,yop",
            },
        )

        self.assertEqual(
            result["buckets"],
            [
                {
                    "value": "BR | 2020",
                    "dimensions": {"country": "BR", "yop": "2020"},
                    "count": 9,
                }
            ],
        )
        sources = client.search.call_args.kwargs["body"]["aggs"]["rows"]["composite"][
            "sources"
        ]
        self.assertEqual(
            sources[-1],
            {
                "document_key": {
                    "terms": {"field": "document_key", "missing_bucket": True}
                }
            },
        )
