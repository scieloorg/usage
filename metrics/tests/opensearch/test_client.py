from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from opensearchpy import RequestError

from metrics.opensearch.client import OpenSearchUsageClient
from metrics.opensearch.mappings import (
    ANALYTICS_INDEX_MAPPINGS,
    DOCUMENT_INDEX_MAPPINGS,
    MONTH_INDEX_MAPPINGS,
    SOURCE_INDEX_MAPPINGS,
    get_index_settings,
)
from metrics.opensearch.painless import merge_metric_document


class OpenSearchUsageClientTests(SimpleTestCase):
    @patch("metrics.opensearch.client.OpenSearch")
    def test_basic_auth_string_is_split_into_credentials(self, opensearch):
        OpenSearchUsageClient(
            url="https://example.org:9200",
            basic_auth="reader:secret",
        )

        self.assertEqual(
            opensearch.call_args.kwargs["http_auth"],
            ("reader", "secret"),
        )

    def test_unknown_yop_does_not_replace_known_yop(self):
        existing = {"publication_year": 2024, "total_requests": 1}
        current = {"publication_year": 1, "total_requests": 2}

        merged = merge_metric_document(existing, current)

        assert merged["publication_year"] == 2024
        assert merged["total_requests"] == 3

    def test_rejects_non_positive_primary_shard_count(self):
        with self.assertRaisesMessage(
            ValueError,
            "OpenSearch primary shards must be greater than zero.",
        ):
            get_index_settings(0)

    @patch.object(OpenSearchUsageClient, "get_opensearch_client")
    def test_creates_physical_index_with_alias_and_compression(self, get_client):
        raw_client = Mock()
        raw_client.indices.exists_alias.return_value = False
        raw_client.indices.exists.return_value = False
        get_client.return_value = raw_client
        client = OpenSearchUsageClient(url="https://example.org:9200")

        client.create_alias_if_not_exists(
            "usage_monthly_scl_2026",
            MONTH_INDEX_MAPPINGS,
            primary_shards=3,
        )

        raw_client.indices.create.assert_called_once_with(
            index="usage_monthly_scl_2026_000001",
            body={
                "settings": get_index_settings(3),
                "mappings": MONTH_INDEX_MAPPINGS,
                "aliases": {"usage_monthly_scl_2026": {}},
            },
        )

    @patch.object(OpenSearchUsageClient, "get_opensearch_client")
    def test_yearly_partition_uses_validated_access_year(self, get_client):
        raw_client = Mock()
        raw_client.indices.exists_alias.return_value = False
        raw_client.indices.exists.return_value = False
        get_client.return_value = raw_client
        client = OpenSearchUsageClient(url="https://example.org:9200")

        write_index = client.prepare_usage_index(
            alias_name="usage_monthly_scl",
            mappings=MONTH_INDEX_MAPPINGS,
            partition_strategy="yearly",
            access_date="2025-12-31",
        )

        assert write_index == "usage_monthly_scl_2025"
        raw_client.indices.create.assert_called_once_with(
            index="usage_monthly_scl_2025-000001",
            body={
                "settings": get_index_settings(1),
                "mappings": MONTH_INDEX_MAPPINGS,
                "aliases": {
                    "usage_monthly_scl_2025": {"is_write_index": True},
                    "usage_monthly_scl": {},
                },
            },
        )

    @patch.object(OpenSearchUsageClient, "get_opensearch_client")
    def test_yearly_rollover_keeps_global_read_alias(self, get_client):
        raw_client = Mock()
        raw_client.indices.rollover.return_value = {
            "rolled_over": False,
        }
        get_client.return_value = raw_client
        client = OpenSearchUsageClient(url="https://example.org:9200")

        client.rollover_usage_index(
            "usage_monthly_scl_2026",
            MONTH_INDEX_MAPPINGS,
            read_alias="usage_monthly_scl",
        )

        raw_client.indices.rollover.assert_called_once_with(
            alias="usage_monthly_scl_2026",
            body={
                "conditions": {"max_size": "50gb"},
                "settings": get_index_settings(1),
                "mappings": MONTH_INDEX_MAPPINGS,
                "aliases": {"usage_monthly_scl": {}},
            },
        )

    @patch.object(OpenSearchUsageClient, "get_opensearch_client")
    def test_continuous_partition_creates_a_write_alias(self, get_client):
        raw_client = Mock()
        raw_client.indices.exists_alias.return_value = False
        raw_client.indices.exists.return_value = False
        get_client.return_value = raw_client
        client = OpenSearchUsageClient(url="https://example.org:9200")

        write_index = client.prepare_usage_index(
            alias_name="usage_monthly_books",
            mappings=MONTH_INDEX_MAPPINGS,
            partition_strategy="rollover",
            access_date="2026-01-01",
        )

        assert write_index == "usage_monthly_books"
        raw_client.indices.create.assert_called_once_with(
            index="usage_monthly_books-000001",
            body={
                "settings": get_index_settings(1),
                "mappings": MONTH_INDEX_MAPPINGS,
                "aliases": {
                    "usage_monthly_books": {"is_write_index": True},
                },
            },
        )

    @patch.object(OpenSearchUsageClient, "get_opensearch_client")
    def test_concurrent_initial_index_creation_is_idempotent(self, get_client):
        raw_client = Mock()
        raw_client.indices.exists_alias.return_value = False
        raw_client.indices.exists.side_effect = [False, True]
        raw_client.indices.create.side_effect = RequestError(
            400,
            "resource_already_exists_exception",
            {},
        )
        get_client.return_value = raw_client
        client = OpenSearchUsageClient(url="https://example.org:9200")

        write_index = client.prepare_usage_index(
            alias_name="usage_monthly_books",
            mappings=MONTH_INDEX_MAPPINGS,
            partition_strategy="rollover",
            access_date="2026-01-01",
        )

        assert write_index == "usage_monthly_books"

    @override_settings(OPENSEARCH_ROLLOVER_MAX_SIZE="50gb")
    @patch.object(OpenSearchUsageClient, "get_opensearch_client")
    def test_rollover_preserves_mappings_and_settings(self, get_client):
        raw_client = Mock()
        get_client.return_value = raw_client
        client = OpenSearchUsageClient(url="https://example.org:9200")

        client.rollover_usage_index(
            "usage_monthly_books",
            MONTH_INDEX_MAPPINGS,
        )

        raw_client.indices.rollover.assert_called_once_with(
            alias="usage_monthly_books",
            body={
                "conditions": {"max_size": "50gb"},
                "settings": get_index_settings(1),
                "mappings": MONTH_INDEX_MAPPINGS,
            },
        )

    @override_settings(OPENSEARCH_BULK_CHUNK_SIZE=2)
    @patch("metrics.opensearch.client.helpers.bulk")
    @patch.object(OpenSearchUsageClient, "get_opensearch_client")
    def test_continuous_updates_follow_existing_backing_index(
        self,
        get_client,
        bulk,
    ):
        raw_client = Mock()
        raw_client.indices.get_alias.return_value = {
            "usage_monthly_books-000001": {
                "aliases": {
                    "usage_monthly_books": {"is_write_index": False},
                }
            },
            "usage_monthly_books-000002": {
                "aliases": {
                    "usage_monthly_books": {"is_write_index": True},
                }
            },
        }
        raw_client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "existing",
                        "_index": "usage_monthly_books-000001",
                    }
                ]
            }
        }
        get_client.return_value = raw_client
        bulk.return_value = (2, 0)
        client = OpenSearchUsageClient(url="https://example.org:9200")

        succeeded = client.increment_document_items_for_day(
            index_name="usage_monthly_books",
            document_items=iter(
                [
                    ("existing", {"total_requests": 1}),
                    ("new", {"total_requests": 1}),
                ]
            ),
            access_day="2026-01-01",
            resolve_existing_indexes=True,
        )

        actions = list(bulk.call_args.args[1])
        assert succeeded == 2
        assert [action["_index"] for action in actions] == [
            "usage_monthly_books-000001",
            "usage_monthly_books-000002",
        ]

    def test_mappings_are_explicit_and_separate_metadata_from_facts(self):
        assert "source_key" in MONTH_INDEX_MAPPINGS["properties"]
        assert "document_key" in MONTH_INDEX_MAPPINGS["properties"]
        assert "year" in ANALYTICS_INDEX_MAPPINGS["properties"]
        assert "source_key" in ANALYTICS_INDEX_MAPPINGS["properties"]
        assert "document_key" in ANALYTICS_INDEX_MAPPINGS["properties"]
        assert set(ANALYTICS_INDEX_MAPPINGS["_source"]["excludes"]) == {
            "year",
            "source_key",
            "document_key",
            "metric_scope",
            "data_type",
            "parent_data_type",
            "article_version",
            "access_type",
            "access_method",
            "country_code",
            "content_language",
        }
        for mapping in (MONTH_INDEX_MAPPINGS, ANALYTICS_INDEX_MAPPINGS):
            assert mapping["dynamic"] is False
            assert "source" not in mapping["properties"]
            assert "document" not in mapping["properties"]
        assert "applied_days" in MONTH_INDEX_MAPPINGS["properties"]
        assert "applied_day_masks" in ANALYTICS_INDEX_MAPPINGS["properties"]
        assert DOCUMENT_INDEX_MAPPINGS["dynamic"] is False
        assert SOURCE_INDEX_MAPPINGS["dynamic"] is False

    @override_settings(OPENSEARCH_BULK_CHUNK_SIZE=2000)
    @patch("metrics.opensearch.client.helpers.bulk")
    @patch.object(OpenSearchUsageClient, "get_opensearch_client")
    def test_daily_increment_uses_short_access_day(self, get_client, bulk):
        get_client.return_value = Mock()
        bulk.return_value = (1, 0)
        client = OpenSearchUsageClient(url="https://example.org:9200")

        succeeded = client.increment_document_items_for_day(
            index_name="usage_monthly_scl_2026",
            document_items=iter([("key", {"total_requests": 1})]),
            access_day="2026-08-20",
        )

        action = list(bulk.call_args.args[1])[0]
        assert action["script"]["params"]["access_day"] == "2026-08-20"
        assert action["upsert"] == {"applied_days": []}
        assert bulk.call_args.kwargs["chunk_size"] == 2000
        assert succeeded == 1

    @patch("metrics.opensearch.client.helpers.bulk")
    @patch.object(OpenSearchUsageClient, "get_opensearch_client")
    def test_annual_increment_uses_compact_day_mask(self, get_client, bulk):
        get_client.return_value = Mock()
        bulk.return_value = (1, 0)
        client = OpenSearchUsageClient(url="https://example.org:9200")

        client.increment_document_items_for_day(
            index_name="usage_yearly_analytics_scl_2026",
            document_items=iter([("key", {"total_requests": 1})]),
            access_day="2026-08-20",
            annual=True,
        )

        action = list(bulk.call_args.args[1])[0]
        params = action["script"]["params"]
        assert params["mask_index"] == 3
        assert params["day_mask"] == 1 << 42
        assert action["upsert"] == {"applied_day_masks": [0] * 6}

    @patch("metrics.opensearch.client.helpers.bulk")
    @patch.object(OpenSearchUsageClient, "get_opensearch_client")
    def test_annual_day_mask_covers_last_day_of_leap_year(
        self,
        get_client,
        bulk,
    ):
        get_client.return_value = Mock()
        bulk.return_value = (1, 0)
        client = OpenSearchUsageClient(url="https://example.org:9200")

        client.increment_document_items_for_day(
            index_name="usage_yearly_analytics_scl_2024",
            document_items=iter([("key", {"total_requests": 1})]),
            access_day="2024-12-31",
            annual=True,
        )

        action = list(bulk.call_args.args[1])[0]
        params = action["script"]["params"]
        assert params["mask_index"] == 5
        assert params["day_mask"] == 1 << 50

    @override_settings(
        OPENSEARCH_BASIC_AUTH=None,
        OPENSEARCH_API_KEY=None,
        OPENSEARCH_HTTP_COMPRESS=True,
    )
    @patch("metrics.opensearch.client.OpenSearch")
    def test_http_compression_remains_configurable(self, opensearch):
        OpenSearchUsageClient(url="https://example.org:9200")
        opensearch.assert_called_once_with(
            "https://example.org:9200",
            verify_certs=False,
            http_compress=True,
        )
