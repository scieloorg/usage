import re

from stdnum import isbn

from counter_api.constants import PROPRIETARY_NAMESPACE

IDENTIFIER_NAMES = {
    "doi": "DOI",
    "isbn": "ISBN",
    "eisbn": "ISBN",
    "print_issn": "Print_ISSN",
    "electronic_issn": "Online_ISSN",
    "uri": "URI",
    "book_id": "Proprietary",
    "chapter_id": "Proprietary",
    "scielo_issn": "Proprietary",
    "pid_v2": "Proprietary",
    "pid_v3": "Proprietary",
    "pid_generic": "Proprietary",
}
ITEM_ID_FIELDS = {
    "doi": ("identifiers.doi",),
    "isbn": ("identifiers.isbn", "identifiers.eisbn"),
    "print_issn": ("identifiers.print_issn", "scielo_issn"),
    "online_issn": ("identifiers.electronic_issn",),
    "proprietary": (
        "source_id",
        "document_id",
        "identifiers.book_id",
        "identifiers.chapter_id",
        "identifiers.pid_v2",
        "identifiers.pid_v3",
        "identifiers.pid_generic",
    ),
}
DOI_URL_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
)
DOI_PATTERN = re.compile(r"10\.[1-9][0-9]{2}[0-9.]*/.+", re.IGNORECASE)
PROPRIETARY_IDENTIFIER_PRIORITY = {
    "pid_generic": 0,
    "pid_v3": 1,
    "pid_v2": 2,
    "chapter_id": 3,
    "book_id": 4,
    "scielo_issn": 5,
}


def counter_identifiers(metadata):
    identifiers = metadata.get("identifiers") or {}
    result = {}

    ordered = sorted(
        identifiers.items(),
        key=lambda item: PROPRIETARY_IDENTIFIER_PRIORITY.get(
            str(item[0]).lower(),
            len(PROPRIETARY_IDENTIFIER_PRIORITY),
        ),
    )

    for key, value in ordered:
        name = IDENTIFIER_NAMES.get(str(key).lower())
        if not name or not value or name in result:
            continue

        value = str(value)
        if name == "DOI":
            lower_value = value.lower()
            for prefix in DOI_URL_PREFIXES:
                if lower_value.startswith(prefix):
                    value = value[len(prefix) :]
                    break
            if not DOI_PATTERN.fullmatch(value):
                continue

        if name == "ISBN":
            try:
                value = isbn.format(isbn.to_isbn13(value))
            except isbn.ValidationError:
                continue

        if name == "Proprietary" and ":" not in value:
            value = f"{PROPRIETARY_NAMESPACE}:{value}"

        result[name] = value

    return tuple(sorted(result.items()))
