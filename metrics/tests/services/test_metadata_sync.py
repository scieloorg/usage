from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from scielo_usage_counter.values import CONTENT_TYPE_FULL_TEXT

from collection.models import Collection
from document.models import Document
from metrics.counter.indexing import converter
from metrics.models import MetadataSyncOutbox, MetadataSyncState
from metrics.services.metadata_documents import (
    build_document_document,
    build_source_document,
)
from metrics.services.metadata_sync import sync_metadata
from source.models import Source


class MetadataDocumentsTests(TestCase):
    def setUp(self):
        self.collection = Collection.objects.create(acron3="prt", acron2="pt")
        self.source = Source.objects.create(
            collection=self.collection,
            source_type=Source.SOURCE_TYPE_JOURNAL,
            source_id="1234-5678",
            title="Journal title",
            subject_areas=["Medicine"],
        )
        self.document = Document.objects.create(
            collection=self.collection,
            source=self.source,
            document_type=Document.DOCUMENT_TYPE_ARTICLE,
            document_id="internal-id",
            pid_v3="S1234-56782026000100001",
            title="Article title",
            publication_year="2026",
        )

    def test_metadata_is_stored_once_under_the_same_keys_used_by_facts(self):
        source_key, source_payload = build_source_document(self.source)
        document_key, document_payload = build_document_document(self.document)

        self.assertTrue(source_key.startswith("k1_"))
        self.assertTrue(document_key.startswith("k1_"))
        self.assertEqual(document_payload["source_key"], source_key)
        self.assertEqual(source_payload["title"], "Journal title")
        self.assertEqual(document_payload["title"], "Article title")
        self.assertEqual(document_payload["publication_year"], 2026)
        self.assertTrue(source_payload["active"])
        self.assertTrue(document_payload["active"])

    def test_book_metadata_uses_the_same_canonical_key_as_facts(self):
        collection = Collection.objects.create(acron3="books", acron2="bk")
        source = Source.objects.create(
            collection=collection,
            source_type=Source.SOURCE_TYPE_BOOK,
            source_id="b5b72",
            title="Book title",
        )
        document = Document.objects.create(
            collection=collection,
            source=source,
            document_type=Document.DOCUMENT_TYPE_CHAPTER,
            document_id="book:b5b72/chapter:8jp9n",
            pid_generic="book:b5b72/chapter:8jp9n",
            title="Chapter title",
        )
        metadata_key, _payload = build_document_document(document)
        facts = dict(
            converter.iter_partitioned_values(
                [
                    {
                        "collection": "books",
                        "document_type": "chapter",
                        "pid_generic": "BOOK:B5B72/CHAPTER:8JP9N",
                        "title_pid_generic": "BOOK:B5B72",
                        "source": {
                            "source_type": "book",
                            "source_id": "b5b72",
                        },
                        "content_type": CONTENT_TYPE_FULL_TEXT,
                        "click_timestamps": {"00:01": 1},
                        "user_session_id": "session-1",
                        "access_date": "2025-02-01",
                    }
                ],
                "counter",
            )
        )
        item = next(
            value for value in facts.values() if value["metric_scope"] == "item"
        )

        self.assertEqual(item["document_key"], metadata_key)

    def test_save_and_delete_create_transactional_outbox_entries(self):
        source_key, _payload = build_source_document(self.source)
        document_key, _payload = build_document_document(self.document)

        self.assertTrue(
            MetadataSyncOutbox.objects.filter(
                entity=MetadataSyncState.ENTITY_SOURCE,
                object_key=source_key,
                payload__active=True,
            ).exists()
        )
        self.document.delete()
        entry = MetadataSyncOutbox.objects.get(
            entity=MetadataSyncState.ENTITY_DOCUMENT,
            object_key=document_key,
        )
        self.assertFalse(entry.payload["active"])

    @override_settings(OPENSEARCH_INDEX_NAME="custom_usage")
    @patch("metrics.services.metadata_sync.OpenSearchUsageClient")
    def test_full_sync_resets_cursor_and_clears_exported_outbox(self, client_class):
        client = Mock()
        client.ping.return_value = True
        client.index_document_items.side_effect = lambda index, items: len(list(items))
        client_class.return_value = client
        MetadataSyncState.objects.create(
            entity=MetadataSyncState.ENTITY_SOURCE,
            cursor_updated=self.source.updated,
            cursor_pk=self.source.pk + 1,
        )

        exported = sync_metadata(entity=MetadataSyncState.ENTITY_SOURCE, full=True)

        state = MetadataSyncState.objects.get(entity=MetadataSyncState.ENTITY_SOURCE)
        self.assertGreaterEqual(exported[MetadataSyncState.ENTITY_SOURCE], 1)
        self.assertEqual(state.cursor_pk, self.source.pk)
        self.assertIsNone(state.lease_until)
        self.assertFalse(
            MetadataSyncOutbox.objects.filter(
                entity=MetadataSyncState.ENTITY_SOURCE
            ).exists()
        )
        client.create_alias_if_not_exists.assert_called_once()
        self.assertEqual(
            client.create_alias_if_not_exists.call_args.args[0],
            "custom_usage_sources",
        )
