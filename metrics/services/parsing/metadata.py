import logging
from time import monotonic

from scielo_usage_counter import url_translator
from scielo_usage_counter.translator.books import URLTranslatorBooksSite
from scielo_usage_counter.translator.classic import URLTranslatorClassicSite
from scielo_usage_counter.translator.dataverse import URLTranslatorDataverseSite
from scielo_usage_counter.translator.opac import URLTranslatorOPACSite
from scielo_usage_counter.translator.opac_alpha import URLTranslatorOPACAlphaSite
from scielo_usage_counter.translator.preprints import URLTranslatorPreprintsSite

from document.models import Document
from log_manager_config.models import CollectionLogDirectory
from metrics.services.parsing import metadata_cache
from source.models import Source

TRANSLATOR_CLASSES = {
    "books": URLTranslatorBooksSite,
    "classic": URLTranslatorClassicSite,
    "dataverse": URLTranslatorDataverseSite,
    "opac": URLTranslatorOPACSite,
    "opac_alpha": URLTranslatorOPACAlphaSite,
    "preprints": URLTranslatorPreprintsSite,
}


def build_url_translation_manager(log_file):
    translator_class = _get_log_file_translator_class(log_file)
    if not translator_class:
        raise Exception(
            f"No URL translator class found for collection {log_file.collection}."
        )

    if metadata_cache.is_enabled(log_file.collection):
        return metadata_cache.get_url_translation_manager(
            log_file.collection,
            translator_class,
            _build_manager,
        )

    manager, elapsed = _build_manager(log_file.collection, translator_class)
    logging.info(
        "Prepared parsing metadata for %s without cache in %.3f seconds.",
        log_file.collection.acron3,
        elapsed,
    )
    return manager


def _build_manager(collection, translator_class):
    started = monotonic()
    manager = url_translator.URLTranslationManager(
        documents_metadata=Document.metadata(collection=collection),
        sources_metadata=Source.metadata(collection=collection),
        translator=translator_class,
    )
    return manager, monotonic() - started


def _get_log_file_translator_class(log_file):
    for directory in CollectionLogDirectory.objects.filter(
        config__collection=log_file.collection,
    ):
        if directory.path in log_file.path and directory.translator_class:
            return _get_translator_class(directory.translator_class)

    return None


def _get_translator_class(name):
    if not name or not isinstance(name, str):
        return None

    return TRANSLATOR_CLASSES.get(name.lower())
