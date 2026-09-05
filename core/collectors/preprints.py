import logging

from django.conf import settings
from requests.exceptions import HTTPError
from sickle import Sickle

from core.utils import standardizer

FILTER_FALLBACK_STATUS_CODE = 500


def iter_records(from_date, until_date):
    oai_client = Sickle(
        endpoint=settings.OAI_PMH_PREPRINT_ENDPOINT,
        max_retries=settings.OAI_PMH_MAX_RETRIES,
        verify=False,
    )
    yielded_identifiers = set()

    try:
        for record in _list_records(oai_client, from_date, until_date):
            yielded_identifiers.add(record.header.identifier)
            yield record
        return
    except HTTPError as exc:
        response = exc.response
        has_date_filter = from_date or until_date
        if (
            response is None
            or response.status_code != FILTER_FALLBACK_STATUS_CODE
            or not has_date_filter
        ):
            raise

    logging.warning(
        "Preprints OAI rejected date filters with HTTP 500. "
        "Falling back to the full feed and filtering locally. "
        "From: %s, Until: %s",
        from_date,
        until_date,
    )

    for record in _list_records(oai_client):
        if record.header.identifier in yielded_identifiers:
            continue

        if _is_record_in_date_range(record, from_date, until_date):
            yield record


def _list_records(oai_client, from_date=None, until_date=None):
    params = {"metadataPrefix": settings.OAI_METADATA_PREFIX}

    if from_date:
        params["from"] = from_date

    if until_date:
        params["until"] = until_date

    return oai_client.ListRecords(ignore_deleted=True, **params)


def _is_record_in_date_range(record, from_date=None, until_date=None):
    datestamp = str(getattr(record.header, "datestamp", ""))[:10]
    if not datestamp:
        return False

    if from_date and datestamp < from_date:
        return False

    if until_date and datestamp > until_date:
        return False

    return True


def extract_record_data(record):
    pid_generic = _extract_compatible_identifier(record.header.identifier)
    text_langs = [
        standardizer.standardize_language_code(language)
        for language in record.metadata.get("language", [])
    ]
    publication_date = record.metadata.get("date", [""])[0]
    default_language = text_langs[0] if text_langs else ""
    publication_year = _extract_publication_year_from_date(publication_date)

    return {
        "pid_generic": pid_generic,
        "text_langs": text_langs,
        "publication_date": publication_date,
        "default_language": default_language,
        "publication_year": publication_year,
    }


def _extract_compatible_identifier(identifier):
    try:
        return identifier.split(":")[-1].split("/")[1]
    except IndexError:
        return ""


def _extract_publication_year_from_date(date_str):
    try:
        return date_str[:4]
    except IndexError:
        return ""
