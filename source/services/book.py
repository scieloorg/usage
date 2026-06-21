from core.utils.metadata import as_list, compact_dict, normalize_year
from source.models import Source


def upsert_monograph_source(
    payload,
    collection,
    user=None,
    force_update=True,
    source_url=None,
    last_seq=None,
):
    if payload.get("TYPE") != "Monograph":
        return None

    source, created = Source.objects.get_or_create(
        collection=collection,
        source_type=Source.SOURCE_TYPE_BOOK,
        source_id=str(payload.get("id")),
    )

    if created and user:
        source.creator = user

    if created or force_update:
        source.scielo_issn = None
        source.acronym = ""
        source.title = payload.get("title") or str(payload.get("id"))
        source.identifiers = _build_source_identifiers(payload)
        source.publisher_name = as_list(payload.get("publisher"))
        source.subject_areas = []
        source.wos_subject_areas = []
        source.default_lang = payload.get("language") or None
        source.publication_date = payload.get("publication_date") or None
        source.publication_year = normalize_year(payload.get("year"))
        source.access_type = _normalize_access_type(payload.get("is_comercial"))
        source.extra_data = _build_source_extra_data(
            payload,
            source_url=source_url,
            last_seq=last_seq,
        )

    if user:
        source.updated_by = user

    source.save()
    return source


def _build_source_identifiers(payload):
    identifiers = {
        "book_id": str(payload.get("id")) if payload.get("id") is not None else None,
        "isbn": payload.get("isbn"),
        "eisbn": payload.get("eisbn"),
        "doi": payload.get("doi_number"),
    }
    return compact_dict(identifiers)


def _build_source_extra_data(payload, source_url=None, last_seq=None):
    extra_data = {
        "raw_type": payload.get("TYPE"),
        "source_url": source_url,
        "last_seq": last_seq,
        "visible": payload.get("visible"),
        "city": payload.get("city"),
        "country": payload.get("country"),
        "pages": payload.get("pages"),
        "collection_data": payload.get("collection"),
        "creators": payload.get("creators"),
        "is_comercial": payload.get("is_comercial"),
        "use_licence": payload.get("use_licence"),
        "price_reais": payload.get("price_reais"),
        "price_dollar": payload.get("price_dollar"),
        "shopping_info": payload.get("shopping_info"),
        "serie": payload.get("serie"),
        "format": payload.get("format"),
        "translated_titles": payload.get("translated_titles"),
        "translated_synopses": payload.get("translated_synopses"),
        "synopsis": payload.get("synopsis"),
        "primary_descriptor": payload.get("primary_descriptor"),
        "translated_primary_descriptors": payload.get("translated_primary_descriptors"),
    }
    return compact_dict(extra_data)


def _normalize_access_type(value):
    if value in (None, ""):
        return None

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "sim"}:
            return Source.ACCESS_TYPE_COMMERCIAL
        if normalized in {"false", "0", "no", "n", "nao", "não"}:
            return Source.ACCESS_TYPE_OPEN_ACCESS

    return (
        Source.ACCESS_TYPE_COMMERCIAL if bool(value) else Source.ACCESS_TYPE_OPEN_ACCESS
    )
