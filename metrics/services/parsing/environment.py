from scielo_usage_counter.translator.books import URLTranslatorBooksSite
from scielo_usage_counter.translator.classic import URLTranslatorClassicSite
from scielo_usage_counter.translator.dataverse import URLTranslatorDataverseSite
from scielo_usage_counter.translator.opac import URLTranslatorOPACSite
from scielo_usage_counter.translator.opac_alpha import URLTranslatorOPACAlphaSite
from scielo_usage_counter.translator.preprints import URLTranslatorPreprintsSite

from document.models import Document
from log_manager_config.models import CollectionLogDirectory
from scielo_usage_counter import log_handler, url_translator
from source.models import Source


def setup_parsing_environment(log_file, robots_list, mmdb):
    log_parser = log_handler.LogParser(
        mmdb_data=mmdb.data,
        robots_list=robots_list,
        output_mode="dict",
    )
    log_parser.logfile = log_file.path

    translator_class = _get_log_file_translator_class(log_file)
    if not translator_class:
        raise Exception(
            f"No URL translator class found for collection {log_file.collection}."
        )

    url_translator_manager = url_translator.URLTranslationManager(
        documents_metadata=Document.metadata(collection=log_file.collection),
        sources_metadata=Source.metadata(collection=log_file.collection),
        translator=translator_class,
    )
    return log_parser, url_translator_manager


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

    translator_classes = {
        "books": URLTranslatorBooksSite,
        "classic": URLTranslatorClassicSite,
        "dataverse": URLTranslatorDataverseSite,
        "opac": URLTranslatorOPACSite,
        "opac_alpha": URLTranslatorOPACAlphaSite,
        "preprints": URLTranslatorPreprintsSite,
    }
    return translator_classes.get(name.lower())
