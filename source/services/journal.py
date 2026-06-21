from core.utils.metadata import as_list, compact_dict, get_value
from source.models import Source


def upsert_journal_source(
    journal,
    collection,
    user=None,
    force_update=True,
    load_mode=None,
):
    scielo_issn = get_value(journal, "scielo_issn")
    if not scielo_issn:
        return None

    source, created = Source.objects.get_or_create(
        collection=collection,
        source_type=Source.SOURCE_TYPE_JOURNAL,
        source_id=scielo_issn,
    )

    if created and user:
        source.creator = user

    if created or force_update:
        source.scielo_issn = scielo_issn
        source.acronym = get_value(journal, "acronym") or ""
        source.title = get_value(journal, "title") or scielo_issn
        source.identifiers = _build_source_identifiers(journal)
        source.publisher_name = as_list(get_value(journal, "publisher_name"))
        source.subject_areas = as_list(get_value(journal, "subject_areas"))
        source.wos_subject_areas = as_list(get_value(journal, "wos_subject_areas"))
        source.default_lang = None
        source.publication_date = None
        source.publication_year = None
        source.extra_data = compact_dict(
            {
                "collection_acronym": get_value(journal, "collection_acronym"),
                "load_mode": load_mode,
            }
        )

    if user:
        source.updated_by = user

    source.save()
    return source


def _build_source_identifiers(journal):
    identifiers = {
        "electronic_issn": get_value(journal, "electronic_issn"),
        "print_issn": get_value(journal, "print_issn"),
        "scielo_issn": get_value(journal, "scielo_issn"),
    }
    return compact_dict(identifiers)
