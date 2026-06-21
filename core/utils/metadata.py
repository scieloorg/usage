def as_list(value):
    if not value:
        return []

    if isinstance(value, list):
        return value

    return [value]


def compact_dict(data):
    return {
        key: value for key, value in data.items() if value not in (None, "", [], {}, ())
    }


def get_value(data, key, default=None):
    if isinstance(data, dict):
        return data.get(key, default)
    return getattr(data, key, default)


def normalize_langs(value):
    if not value:
        return []

    if isinstance(value, list):
        return [item for item in value if item not in (None, "")]

    if isinstance(value, dict):
        return [key for key, enabled in value.items() if enabled]

    return [value]


def normalize_year(value, fallback_date=None):
    if value not in (None, ""):
        return str(value)[:4]

    if fallback_date not in (None, ""):
        return str(fallback_date)[:4]

    return None
