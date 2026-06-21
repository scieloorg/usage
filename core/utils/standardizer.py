import re

import langcodes


def standardize_language_code(language_code: str, threshold=0.75):
    language_code = str(language_code).strip().strip("'\"")
    lang = langcodes.get(language_code)
    try:
        parts = str(lang).split("-")
    except Exception:
        return "un"
    return parts[0]


def standardize_pid_v2(pid_v2):
    if not pid_v2 or not pid_v2.lower().startswith("s") or len(pid_v2) < 23:
        return ""

    if len(pid_v2) == 23:
        return pid_v2[0].upper() + pid_v2[1:]

    if len(pid_v2) > 23:
        return pid_v2[0].upper() + pid_v2[1:23]

    return ""


def standardize_pid_v3(pid_v3):
    return str(pid_v3 or "")


def standardize_doi(text):
    text = (text or "").strip()
    if not text:
        return ""

    doi_prefixes = [
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi.org/",
        "dx.doi.org/",
        "doi:",
    ]
    for prefix in doi_prefixes:
        if text.lower().startswith(prefix):
            text = text[len(prefix) :]
            break

    if text.lower().startswith("10."):
        return text

    return ""


def standardize_pid_generic(pid_generic):
    value = str(pid_generic or "").strip().upper()
    value = re.sub(r"\s+", "", value)
    value = value.rstrip(".,;:")
    return value or ""


def standardize_year_of_publication(year_of_publication):
    value = str(year_of_publication or "").strip()
    if not value:
        return ""
    match = re.match(r"(\d{4})", value)
    return match.group(1) if match else ""


def language_iso(code):
    code = re.split(r"-|_", code)[0] if code else ""
    if langcodes.tag_is_valid(code):
        return langcodes.standardize_tag(code)
    return ""


def standardize_or_default(func, value, default=""):
    try:
        return func(value)
    except Exception:
        return default


def standardize_pid_generic_values(values):
    if not isinstance(values, (list, tuple, set)):
        return []

    items = []

    for value in values:
        item = standardize_or_default(standardize_pid_generic, value)

        if item and item not in items:
            items.append(item)

    return items
