from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from collection.models import Collection
from log_manager_config.models import CollectionLogDirectory, LogManagerCollectionConfig
from metrics.services.parsing.metadata import (
    _get_translator_class,
    build_url_translation_manager,
)


class TranslatorClassTests(TestCase):
    def test_books_maps_to_books_translator(self):
        cls = _get_translator_class("books")
        self.assertEqual(cls.__name__, "URLTranslatorBooksSite")

    def test_classic_maps_to_classic_translator(self):
        cls = _get_translator_class("classic")
        self.assertEqual(cls.__name__, "URLTranslatorClassicSite")

    def test_opac_maps_to_opac_translator(self):
        cls = _get_translator_class("opac")
        self.assertEqual(cls.__name__, "URLTranslatorOPACSite")

    def test_opac_alpha_maps_to_opac_alpha_translator(self):
        cls = _get_translator_class("opac_alpha")
        self.assertEqual(cls.__name__, "URLTranslatorOPACAlphaSite")

    def test_preprints_maps_to_preprints_translator(self):
        cls = _get_translator_class("preprints")
        self.assertEqual(cls.__name__, "URLTranslatorPreprintsSite")

    def test_dataverse_maps_to_dataverse_translator(self):
        cls = _get_translator_class("dataverse")
        self.assertEqual(cls.__name__, "URLTranslatorDataverseSite")

    def test_unknown_name_returns_none(self):
        self.assertIsNone(_get_translator_class("unknown"))

    def test_none_returns_none(self):
        self.assertIsNone(_get_translator_class(None))

    def test_case_insensitive(self):
        cls = _get_translator_class("Books")
        self.assertEqual(cls.__name__, "URLTranslatorBooksSite")


class ParsingMetadataTests(TestCase):
    def setUp(self):
        self.collection = Collection.objects.create(acron3="books", acron2="bk")
        config = LogManagerCollectionConfig.objects.create(collection=self.collection)
        CollectionLogDirectory.objects.create(
            config=config,
            path="/app/logs/books",
            translator_class="books",
        )

    @override_settings(PARSING_METADATA_CACHE_COLLECTIONS=[])
    @patch("metrics.services.parsing.metadata.url_translator.URLTranslationManager")
    @patch("metrics.services.parsing.metadata.Source.metadata")
    @patch("metrics.services.parsing.metadata.Document.metadata")
    def test_builds_manager_with_collection_metadata_and_configured_translator(
        self,
        document_metadata,
        source_metadata,
        manager_class,
    ):
        log_file = SimpleNamespace(
            collection=self.collection,
            path="/app/logs/books/2026-08-01.log.gz",
        )
        documents = iter([{"document_id": "book:1"}])
        sources = iter([{"source_id": "1"}])
        document_metadata.return_value = documents
        source_metadata.return_value = sources

        manager = build_url_translation_manager(log_file)

        document_metadata.assert_called_once_with(collection=self.collection)
        source_metadata.assert_called_once_with(collection=self.collection)
        manager_class.assert_called_once()
        call_kwargs = manager_class.call_args.kwargs
        self.assertIs(call_kwargs["documents_metadata"], documents)
        self.assertIs(call_kwargs["sources_metadata"], sources)
        self.assertEqual(call_kwargs["translator"].__name__, "URLTranslatorBooksSite")
        self.assertIs(manager, manager_class.return_value)

    def test_rejects_log_outside_configured_directories(self):
        log_file = SimpleNamespace(
            collection=self.collection,
            path="/other/logs/2026-08-01.log.gz",
        )

        with self.assertRaisesRegex(
            Exception,
            "No URL translator class found for collection",
        ):
            build_url_translation_manager(log_file)
