from types import SimpleNamespace
from unittest.mock import patch

import pytest

from collection.models import Collection
from config.collections import COLLECTION_ACRON3_SIZE_MAP, LOG_MANAGER_SEED_DATA
from document.models import Document
from log_manager_config.models import (
    CollectionLogDirectory,
    LogManagerCollectionConfig,
)
from metrics.services.parsing import metadata, metadata_cache
from source.models import Source


@pytest.fixture(autouse=True)
def empty_metadata_cache():
    metadata_cache.clear()
    yield
    metadata_cache.clear()


@pytest.fixture
def parsing_collection(db, settings):
    settings.PARSING_METADATA_CACHE_COLLECTIONS = ["prt"]
    collection = Collection.objects.create(acron3="prt", acron2="pt")
    config = LogManagerCollectionConfig.objects.create(collection=collection)
    CollectionLogDirectory.objects.create(
        config=config,
        path="/app/logs/prt",
        translator_class="classic",
    )
    source = Source.objects.create(
        collection=collection,
        source_type=Source.SOURCE_TYPE_JOURNAL,
        source_id="1234-5678",
        scielo_issn="1234-5678",
        title="Journal",
    )
    document = Document.objects.create(
        collection=collection,
        source=source,
        document_type=Document.DOCUMENT_TYPE_ARTICLE,
        document_id="S123456782026000100001",
        pid_v2="S123456782026000100001",
        publication_year="2026",
    )
    log_file = SimpleNamespace(
        collection=collection,
        path="/app/logs/prt/2026-07-07_scielo.pt.log.gz",
    )
    return collection, source, document, log_file


def test_all_known_collections_are_enabled_by_default(settings):
    active_log_collections = {item["acronym"] for item in LOG_MANAGER_SEED_DATA}

    assert active_log_collections <= set(COLLECTION_ACRON3_SIZE_MAP)
    assert set(settings.PARSING_METADATA_CACHE_COLLECTIONS) == set(
        COLLECTION_ACRON3_SIZE_MAP
    )


@pytest.mark.django_db
def test_cache_hit_reuses_metadata_but_isolates_mutable_translator(
    parsing_collection,
    django_assert_num_queries,
):
    _, _, _, log_file = parsing_collection

    with (
        patch.object(Document, "metadata", wraps=Document.metadata) as documents,
        patch.object(Source, "metadata", wraps=Source.metadata) as sources,
    ):
        first = metadata.build_url_translation_manager(log_file)
        with django_assert_num_queries(3):
            second = metadata.build_url_translation_manager(log_file)

    assert documents.call_count == 1
    assert sources.call_count == 1
    assert first is not second
    assert first.translator is not second.translator
    assert first.documents_metadata is second.documents_metadata
    assert first.sources_metadata is second.sources_metadata

    first.translator.url_params = {"pid": "first"}

    assert not hasattr(second.translator, "url_params")


@pytest.mark.django_db
def test_cache_is_disabled_for_collection_outside_allowlist(
    parsing_collection,
    settings,
):
    _, _, _, log_file = parsing_collection
    settings.PARSING_METADATA_CACHE_COLLECTIONS = []

    with (
        patch.object(Document, "metadata", wraps=Document.metadata) as documents,
        patch.object(Source, "metadata", wraps=Source.metadata) as sources,
    ):
        metadata.build_url_translation_manager(log_file)
        metadata.build_url_translation_manager(log_file)

    assert documents.call_count == 2
    assert sources.call_count == 2


@pytest.mark.django_db
def test_document_update_invalidates_cache(parsing_collection):
    _, _, document, log_file = parsing_collection

    with patch.object(Document, "metadata", wraps=Document.metadata) as documents:
        first = metadata.build_url_translation_manager(log_file)
        document.title = "Updated title"
        document.save(update_fields=["title", "updated"])
        second = metadata.build_url_translation_manager(log_file)

    assert documents.call_count == 2
    assert first.documents_metadata is not second.documents_metadata


@pytest.mark.django_db
def test_document_creation_invalidates_cache(parsing_collection):
    collection, source, _, log_file = parsing_collection

    with patch.object(Document, "metadata", wraps=Document.metadata) as documents:
        first = metadata.build_url_translation_manager(log_file)
        Document.objects.create(
            collection=collection,
            source=source,
            document_type=Document.DOCUMENT_TYPE_ARTICLE,
            document_id="S123456782026000100002",
            pid_v2="S123456782026000100002",
        )
        second = metadata.build_url_translation_manager(log_file)

    assert documents.call_count == 2
    assert first.documents_metadata is not second.documents_metadata


@pytest.mark.django_db
def test_source_deletion_invalidates_cache(parsing_collection):
    _, source, document, log_file = parsing_collection
    document.source = None
    document.save(update_fields=["source", "updated"])

    with patch.object(Source, "metadata", wraps=Source.metadata) as sources:
        first = metadata.build_url_translation_manager(log_file)
        source.delete()
        second = metadata.build_url_translation_manager(log_file)

    assert sources.call_count == 2
    assert first.sources_metadata is not second.sources_metadata


@pytest.mark.django_db
def test_translator_change_rebuilds_cache(parsing_collection):
    _, _, _, log_file = parsing_collection
    directory = CollectionLogDirectory.objects.get()

    first = metadata.build_url_translation_manager(log_file)
    directory.translator_class = "opac"
    directory.save(update_fields=["translator_class", "updated"])
    second = metadata.build_url_translation_manager(log_file)

    assert first.translator.__class__.__name__ == "URLTranslatorClassicSite"
    assert second.translator.__class__.__name__ == "URLTranslatorOPACSite"
    assert first.documents_metadata is not second.documents_metadata


@pytest.mark.django_db
def test_new_collection_replaces_process_cache(parsing_collection, settings):
    _, _, _, first_log_file = parsing_collection
    settings.PARSING_METADATA_CACHE_COLLECTIONS = ["prt", "arg"]
    other_collection = Collection.objects.create(acron3="arg", acron2="ar")
    config = LogManagerCollectionConfig.objects.create(collection=other_collection)
    CollectionLogDirectory.objects.create(
        config=config,
        path="/app/logs/arg",
        translator_class="classic",
    )
    other_log_file = SimpleNamespace(
        collection=other_collection,
        path="/app/logs/arg/2026-07-07_scielo.ar.log.gz",
    )

    with patch.object(Document, "metadata", wraps=Document.metadata) as documents:
        metadata.build_url_translation_manager(first_log_file)
        metadata.build_url_translation_manager(other_log_file)
        metadata.build_url_translation_manager(first_log_file)

    assert documents.call_count == 3


@pytest.mark.django_db
def test_failed_rebuild_preserves_previous_entry(parsing_collection):
    _, _, document, log_file = parsing_collection
    metadata.build_url_translation_manager(log_file)
    previous_entry = metadata_cache._CACHE_ENTRY
    document.title = "Changed"
    document.save(update_fields=["title", "updated"])

    with patch.object(
        metadata_cache,
        "_build_cache_entry",
        side_effect=RuntimeError("metadata build failed"),
    ):
        with pytest.raises(RuntimeError, match="metadata build failed"):
            metadata.build_url_translation_manager(log_file)

    assert metadata_cache._CACHE_ENTRY is previous_entry


@pytest.mark.django_db
def test_explicit_clear_forces_rebuild(parsing_collection):
    _, _, _, log_file = parsing_collection

    with patch.object(Document, "metadata", wraps=Document.metadata) as documents:
        metadata.build_url_translation_manager(log_file)
        metadata_cache.clear()
        metadata.build_url_translation_manager(log_file)

    assert documents.call_count == 2
