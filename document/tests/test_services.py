from django.test import TestCase

from collection.models import Collection
from document.models import Document
from document.services import article as article_service
from document.services import book as books_service
from document.services import dataset as dataset_service
from document.services import preprint as preprint_service
from source.models import Source
from source.services import book as source_books_service


class ArticleServiceTests(TestCase):
    def test_articlemeta_and_opac_upsert_same_document(self):
        collection = Collection.objects.create(acron3="scl", acron2="sc")
        source = Source.objects.create(
            collection=collection,
            source_type=Source.SOURCE_TYPE_JOURNAL,
            source_id="1234-5678",
            scielo_issn="1234-5678",
            acronym="testjou",
            title="Test Journal",
            identifiers={"scielo_issn": "1234-5678"},
        )

        first = article_service.upsert_article_document_from_articlemeta(
            {
                "code": "S123456782024000100001",
                "title": "Article Title",
                "pdfs": {"en": {"url": "/pdf/en.pdf"}},
                "processing_date": "2024-02-10",
                "publication_date": "2024-01-15",
                "publication_year": "2024",
                "default_language": "en",
                "text_langs": ["en", "pt"],
                "code_title": ["1234-5678"],
            },
            collection=collection,
            source=source,
        )
        second = article_service.upsert_article_document_from_opac(
            {
                "pid_v2": "S123456782024000100001",
                "pid_v3": "S1234-56782024000100001",
                "title": "Article Title",
                "journal_acronym": "testjou",
                "publication_date": "2024-01-15",
                "default_language": "en",
                "text_langs": ["en", "pt"],
            },
            collection=collection,
            source=source,
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Document.objects.count(), 1)
        second.refresh_from_db()
        self.assertEqual(second.pid_v3, "S1234-56782024000100001")
        self.assertEqual(second.identifiers["journal_acronym"], "testjou")


class BookServiceTests(TestCase):
    def test_upsert_monograph_and_part_documents(self):
        collection = Collection.objects.create(acron3="books", acron2="bk")
        monograph_payload = {
            "TYPE": "Monograph",
            "id": "abcd1",
            "title": "Sample Book",
            "isbn": "9788578791889",
            "eisbn": "9788578791880",
            "doi_number": "10.1234/book",
            "language": "pt",
            "publication_date": "2024-05-20",
            "year": "2024",
            "publisher": "SciELO Books",
        }
        part_payload = {
            "TYPE": "Part",
            "id": "18",
            "monograph": "abcd1",
            "title": "Chapter 18",
            "text_language": "es",
            "order": "18",
        }

        source = source_books_service.upsert_monograph_source(
            monograph_payload, collection=collection
        )
        parent_document = books_service.upsert_monograph_document(
            monograph_payload, collection=collection, source=source
        )
        chapter = books_service.upsert_part_document(
            books_service.enrich_part_payload(part_payload, monograph_payload),
            collection=collection,
            source=source,
            parent_document=parent_document,
        )

        self.assertEqual(parent_document.document_type, Document.DOCUMENT_TYPE_BOOK)
        self.assertEqual(parent_document.document_id, "book:abcd1")
        self.assertEqual(parent_document.pid_generic, "book:abcd1")
        self.assertEqual(chapter.document_type, Document.DOCUMENT_TYPE_CHAPTER)
        self.assertEqual(chapter.document_id, "book:abcd1/chapter:18")
        self.assertEqual(chapter.parent_document, parent_document)
        self.assertEqual(chapter.identifiers["book_id"], "abcd1")
        self.assertEqual(chapter.default_lang, "es")


class PreprintServiceTests(TestCase):
    def test_upsert_preprint_document_maps_metadata(self):
        collection = Collection.objects.create(acron3="preprints", acron2="pp")

        document = preprint_service.upsert_preprint_document(
            {
                "pid_generic": "preprint/123",
                "title": "Preprint Title",
                "text_langs": ["en", "pt"],
                "default_language": "en",
                "publication_date": "2024-01-20",
                "publication_year": "2024",
            },
            collection=collection,
        )

        self.assertEqual(document.document_type, Document.DOCUMENT_TYPE_PREPRINT)
        self.assertEqual(document.document_id, "preprint/123")
        self.assertEqual(document.pid_generic, "preprint/123")
        self.assertEqual(document.default_lang, "en")


class DatasetServiceTests(TestCase):
    def test_upsert_dataset_document_accumulates_files(self):
        collection = Collection.objects.create(acron3="data", acron2="dt")

        dataset_service.upsert_dataset_document(
            {
                "title": "Dataset Title",
                "dataset_doi": "10.1234/dataset",
                "dataset_published": "2024-03-15",
                "file_id": "1",
                "file_name": "first.csv",
                "file_url": "https://example.org/first.csv",
                "file_persistent_id": "pid:first",
            },
            collection=collection,
        )
        document = dataset_service.upsert_dataset_document(
            {
                "title": "Dataset Title",
                "dataset_doi": "10.1234/dataset",
                "dataset_published": "2024-03-15",
                "file_id": "2",
                "file_name": "second.csv",
                "file_url": "https://example.org/second.csv",
                "file_persistent_id": "pid:second",
            },
            collection=collection,
        )

        self.assertEqual(document.document_type, Document.DOCUMENT_TYPE_DATASET)
        self.assertEqual(document.document_id, "10.1234/dataset")
        self.assertEqual(set(document.files.keys()), {"1", "2"})
