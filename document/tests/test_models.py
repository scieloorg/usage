from django.test import TestCase

from collection.models import Collection
from document.models import Document
from source.models import Source


class DocumentIdentifierTests(TestCase):
    def test_find_by_identifiers_searches_legacy_identifier_fields(self):
        collection = Collection.objects.create(acron3="scl", acron2="sc")
        document = Document.objects.create(
            collection=collection,
            document_type=Document.DOCUMENT_TYPE_ARTICLE,
            document_id="doc-id",
            pid_v2="pid-v2",
            pid_v3="pid-v3",
            pid_generic="pid-generic",
        )

        for identifier in ("doc-id", "pid-v2", "pid-v3", "pid-generic"):
            self.assertEqual(
                Document.find_by_identifiers(
                    collection,
                    Document.DOCUMENT_TYPE_ARTICLE,
                    identifier,
                ),
                document,
            )

        self.assertIsNone(
            Document.find_by_identifiers(
                collection,
                Document.DOCUMENT_TYPE_ARTICLE,
                "missing",
            )
        )

    def test_builds_book_pid_generic_values(self):
        self.assertEqual(Document.build_book_pid_generic("abcd1"), "book:abcd1")
        self.assertEqual(
            Document.build_chapter_pid_generic("abcd1", "18"),
            "book:abcd1/chapter:18",
        )
        self.assertIsNone(Document.build_book_pid_generic(""))
        self.assertIsNone(Document.build_chapter_pid_generic("abcd1", ""))

    def test_delete_documents_by_raw_id_deletes_collection_documents(self):
        collection = Collection.objects.create(acron3="books", acron2="bk")
        other_collection = Collection.objects.create(acron3="other", acron2="ot")
        Document.objects.create(
            collection=collection,
            document_type=Document.DOCUMENT_TYPE_BOOK,
            document_id="book:abcd1",
            extra_data={"raw_id": "abcd1"},
        )
        Document.objects.create(
            collection=other_collection,
            document_type=Document.DOCUMENT_TYPE_BOOK,
            document_id="book:abcd1",
            extra_data={"raw_id": "abcd1"},
        )

        deleted_count, _ = Document.delete_documents_by_raw_id(collection, "abcd1")

        self.assertEqual(deleted_count, 1)
        self.assertFalse(
            Document.objects.filter(collection=collection, extra_data__raw_id="abcd1")
            .exists()
        )
        self.assertTrue(
            Document.objects.filter(
                collection=other_collection,
                extra_data__raw_id="abcd1",
            ).exists()
        )


class DocumentMetadataTests(TestCase):
    def test_metadata_includes_source_context_and_legacy_identifiers(self):
        collection = Collection.objects.create(acron3="scl", acron2="sc")
        source = Source.objects.create(
            collection=collection,
            source_type=Source.SOURCE_TYPE_JOURNAL,
            source_id="1234-5678",
            scielo_issn="1234-5678",
            title="Test Journal",
            identifiers={"scielo_issn": "1234-5678"},
        )
        Document.objects.create(
            collection=collection,
            source=source,
            document_type=Document.DOCUMENT_TYPE_ARTICLE,
            document_id="S123456782024000100001",
            scielo_issn="1234-5678",
            pid_v2="S123456782024000100001",
            pid_v3="abc123",
            title="Test Article",
            identifiers={"doi": "10.1590/example"},
            files={"pt": {"path": "/pdf/test.pdf"}},
            default_lang="en",
            text_langs=["en", "pt"],
            publication_date="2024-01-15",
            publication_year="2024",
        )

        metadata = list(Document.metadata(collection=collection))

        self.assertEqual(
            metadata,
            [
                {
                    "collection": "scl",
                    "default_lang": "en",
                    "default_media_format": None,
                    "document_id": "S123456782024000100001",
                    "document_type": Document.DOCUMENT_TYPE_ARTICLE,
                    "extra_data": {},
                    "files": {"pt": {"path": "/pdf/test.pdf"}},
                    "identifiers": {"doi": "10.1590/example"},
                    "parent_document_id": None,
                    "pid_generic": None,
                    "pid_v2": "S123456782024000100001",
                    "pid_v3": "abc123",
                    "processing_date": None,
                    "publication_date": "2024-01-15",
                    "publication_year": "2024",
                    "scielo_issn": "1234-5678",
                    "source_id": "1234-5678",
                    "source_type": Source.SOURCE_TYPE_JOURNAL,
                    "text_langs": ["en", "pt"],
                    "title": "Test Article",
                }
            ],
        )

    def test_metadata_loads_parent_documents_in_the_initial_query(self):
        collection = Collection.objects.create(acron3="books", acron2="bk")
        source = Source.objects.create(
            collection=collection,
            source_type=Source.SOURCE_TYPE_BOOK,
            source_id="book-1",
            title="Test Book",
        )
        book = Document.objects.create(
            collection=collection,
            source=source,
            document_type=Document.DOCUMENT_TYPE_BOOK,
            document_id="book:book-1",
        )
        Document.objects.create(
            collection=collection,
            source=source,
            parent_document=book,
            document_type=Document.DOCUMENT_TYPE_CHAPTER,
            document_id="book:book-1/chapter:1",
        )
        Document.objects.create(
            collection=collection,
            document_type=Document.DOCUMENT_TYPE_OTHER,
            document_id="document-without-source",
        )

        with self.assertNumQueries(1):
            metadata = list(Document.metadata(collection=collection))

        metadata_by_id = {item["document_id"]: item for item in metadata}
        self.assertIsNone(metadata_by_id["book:book-1"]["parent_document_id"])
        self.assertEqual(
            metadata_by_id["book:book-1/chapter:1"]["parent_document_id"],
            "book:book-1",
        )
        self.assertIsNone(
            metadata_by_id["document-without-source"]["parent_document_id"]
        )
        self.assertIsNone(metadata_by_id["document-without-source"]["source_id"])
        self.assertIsNone(metadata_by_id["document-without-source"]["source_type"])
