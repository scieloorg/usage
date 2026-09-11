from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from metrics.opensearch.client import OpenSearchUsageClient
from metrics.opensearch.mappings import (
    ANALYTICS_INDEX_MAPPINGS,
    DOCUMENT_INDEX_MAPPINGS,
    MONTH_INDEX_MAPPINGS,
    SOURCE_INDEX_MAPPINGS,
    get_index_settings,
)


class OpenSearchUsageClientTests(SimpleTestCase):
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
