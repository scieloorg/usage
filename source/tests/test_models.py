from django.test import TestCase

from collection.models import Collection
from source.models import Source


class SourceLookupTests(TestCase):
    def test_find_journal_by_issns_searches_source_and_identifier_fields(self):
        collection = Collection.objects.create(acron3="scl", acron2="sc")
        source = Source.objects.create(
            collection=collection,
            source_type=Source.SOURCE_TYPE_JOURNAL,
            source_id="1234-5678",
            scielo_issn="1234-5678",
            acronym="testjou",
            title="Test Journal",
            identifiers={
                "electronic_issn": "2345-6789",
                "print_issn": "8765-4321",
                "scielo_issn": "3456-7890",
            },
        )

        for issn in ("1234-5678", "2345-6789", "8765-4321", "3456-7890"):
            self.assertEqual(
                Source.find_journal_by_issns(collection, [issn]),
                source,
            )

        self.assertIsNone(Source.find_journal_by_issns(collection, ["0000-0000"]))

    def test_find_journal_by_acronym(self):
        collection = Collection.objects.create(acron3="scl", acron2="sc")
        source = Source.objects.create(
            collection=collection,
            source_type=Source.SOURCE_TYPE_JOURNAL,
            source_id="1234-5678",
            acronym="testjou",
            title="Test Journal",
        )

        self.assertEqual(Source.find_journal_by_acronym(collection, "testjou"), source)
        self.assertIsNone(Source.find_journal_by_acronym(collection, "missing"))
        self.assertIsNone(Source.find_journal_by_acronym(collection, ""))

    def test_delete_book_source_by_id(self):
        collection = Collection.objects.create(acron3="books", acron2="bk")
        other_collection = Collection.objects.create(acron3="other", acron2="ot")
        Source.objects.create(
            collection=collection,
            source_type=Source.SOURCE_TYPE_BOOK,
            source_id="abcd1",
            title="Book",
        )
        Source.objects.create(
            collection=other_collection,
            source_type=Source.SOURCE_TYPE_BOOK,
            source_id="abcd1",
            title="Book",
        )

        deleted_count, _ = Source.delete_book_source_by_id(collection, "abcd1")

        self.assertEqual(deleted_count, 1)
        self.assertFalse(Source.objects.filter(collection=collection).exists())
        self.assertTrue(Source.objects.filter(collection=other_collection).exists())
