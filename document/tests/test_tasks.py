from unittest.mock import patch

from django.test import TestCase

from collection.models import Collection
from document.models import Document
from document.tasks import common as document_tasks_common
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
