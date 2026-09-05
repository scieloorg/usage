from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import TestCase

from collection.models import Collection
from document.models import Document
from document.tasks import common as document_tasks_common
from document.tasks import opac as document_tasks_opac
from document.tasks import preprints as document_tasks_preprints
from document.tasks import scielo_books as document_tasks_scielo_books
from source.models import Source


class DocumentBooksSyncTests(TestCase):
    def test_get_latest_scielo_books_last_seq_uses_documents_and_sources(self):
        collection = Collection.objects.create(acron3="books", acron2="bk")
        source = Source.objects.create(
            collection=collection,
            source_type=Source.SOURCE_TYPE_BOOK,
            source_id="book-1",
            title="Book 1",
            extra_data={"last_seq": 120},
        )
        Document.objects.create(
            collection=collection,
            source=source,
            document_type=Document.DOCUMENT_TYPE_BOOK,
            document_id="book:book-1",
            extra_data={"last_seq": "135"},
        )

        self.assertEqual(
            document_tasks_common.get_latest_scielo_books_last_seq("books"),
            135,
        )

    def test_sync_documents_from_scielo_books_uses_computed_since(self):
        collection = Collection.objects.create(acron3="books", acron2="bk")
        source = Source.objects.create(
            collection=collection,
            source_type=Source.SOURCE_TYPE_BOOK,
            source_id="book-1",
            title="Book 1",
            extra_data={"last_seq": 120},
        )
        Document.objects.create(
            collection=collection,
            source=source,
            document_type=Document.DOCUMENT_TYPE_BOOK,
            document_id="book:book-1",
            extra_data={"last_seq": 135},
        )

        with patch(
            "document.tasks.scielo_books.load_documents_from_scielo_books",
            return_value=True,
        ) as mocked:
            result = document_tasks_scielo_books.sync_documents_from_scielo_books(
                collection="books",
                db_name="scielobooks_1a",
                limit=500,
            )

        self.assertTrue(result)
        mocked.assert_called_once_with(
            collection="books",
            db_name="scielobooks_1a",
            since=135,
            limit=500,
            force_update=True,
            headers=None,
            base_url=None,
            user=None,
        )


@pytest.mark.django_db
class TestDocumentOPACSync:
    def test_load_documents_from_dom_uses_collection_endpoint(self):
        collection = Collection.objects.create(
            acron3="dom",
            acron2="do",
            opac_url="https://scielo.do/api/v1/counter_dict",
        )
        source = Source.objects.create(
            collection=collection,
            source_type=Source.SOURCE_TYPE_JOURNAL,
            source_id="rscd",
            acronym="rscd",
            title="Revista Dominicana",
        )
        payload = {
            "journal_acronym": "rscd",
            "pid_v2": "S2636-23092024062038290",
            "pid_v3": "38WwNSBKBsYnMCjs7q9SNCK",
        }
        with patch(
            "document.tasks.opac.opac_collector.fetch_counter_dict"
        ) as mock_fetch_counter_dict, patch(
            "document.tasks.opac.article_service.upsert_article_document_from_opac"
        ) as mock_upsert:
            mock_fetch_counter_dict.return_value = {
                "collection": "",
                "documents": {payload["pid_v3"]: payload},
                "pages": 1,
            }

            result = document_tasks_opac.load_documents_from_opac(
                collection="dom",
                from_date="2026-08-01",
                until_date="2026-08-07",
            )

        assert result is True
        mock_fetch_counter_dict.assert_called_once_with(
            "2026-08-01",
            "2026-08-07",
            page=1,
            endpoint="https://scielo.do/api/v1/counter_dict",
        )
        mock_upsert.assert_called_once_with(
            payload,
            collection=collection,
            source=source,
            user=None,
            force_update=True,
        )

    def test_load_documents_refuses_collection_without_endpoint(self):
        Collection.objects.create(acron3="prt", acron2="pt")

        with patch(
            "document.tasks.opac.opac_collector.fetch_counter_dict"
        ) as mock_fetch_counter_dict:
            result = document_tasks_opac.load_documents_from_opac(
                collection="prt",
                from_date="2026-08-01",
                until_date="2026-08-07",
            )

        assert result is False
        mock_fetch_counter_dict.assert_not_called()


class DocumentPreprintsSyncTests(TestCase):
    @patch("document.tasks.preprints.preprint_service.upsert_preprint_document")
    @patch("document.tasks.preprints.preprints_collector.extract_record_data")
    @patch("document.tasks.preprints.preprints_collector.iter_records")
    @patch("document.tasks.preprints._get_collection")
    def test_load_skips_deleted_and_metadata_less_records(
        self,
        mock_get_collection,
        mock_iter_records,
        mock_extract_record_data,
        mock_upsert,
    ):
        collection = SimpleNamespace(acron3="preprints")
        deleted_record = SimpleNamespace(deleted=True)
        metadata_less_record = SimpleNamespace(deleted=False)
        valid_record = SimpleNamespace(deleted=False, metadata={"title": ["Title"]})
        mock_get_collection.return_value = collection
        mock_iter_records.return_value = [
            deleted_record,
            metadata_less_record,
            valid_record,
        ]
        mock_extract_record_data.return_value = {"pid_generic": "123"}

        result = document_tasks_preprints.load_preprints_from_preprints_api(
            from_date="2026-08-29",
            until_date="2026-09-05",
        )

        self.assertTrue(result)
        mock_extract_record_data.assert_called_once_with(valid_record)
        mock_upsert.assert_called_once_with(
            {"pid_generic": "123"},
            collection=collection,
            user=None,
            force_update=True,
        )
