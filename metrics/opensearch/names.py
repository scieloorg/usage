from datetime import date as date_type

INITIAL_INDEX_GENERATION = 1


def _validate_access_date(access_date):
    if not access_date or not isinstance(access_date, str):
        raise ValueError("Date must be a non-empty string in 'YYYY-MM-DD' format.")
    try:
        return date_type.fromisoformat(access_date)
    except ValueError as exc:
        raise ValueError("Date must be in 'YYYY-MM-DD' format.") from exc


def extract_access_year(date):
    return str(_validate_access_date(date).year)


def _validate_index_inputs(index_prefix, collection):
    if not collection or not isinstance(collection, str):
        raise ValueError("Collection must be a non-empty string.")
    if not index_prefix or not isinstance(index_prefix, str):
        raise ValueError("Index prefix must be a non-empty string.")


def generate_month_index_name(index_prefix, collection):
    _validate_index_inputs(index_prefix, collection)
    return f"{index_prefix}_monthly_{collection}"


def generate_analytics_index_name(index_prefix, collection):
    _validate_index_inputs(index_prefix, collection)
    return f"{index_prefix}_yearly_analytics_{collection}"


def generate_initial_index_name(alias_name):
    return f"{alias_name}_{INITIAL_INDEX_GENERATION:06d}"


def generate_rollover_index_name(alias_name):
    return f"{alias_name}-{INITIAL_INDEX_GENERATION:06d}"


def generate_yearly_write_alias(alias_name, access_date):
    return f"{alias_name}_{extract_access_year(access_date)}"


def generate_metadata_alias(index_prefix, entity):
    if not index_prefix or not isinstance(index_prefix, str):
        raise ValueError("Index prefix must be a non-empty string.")
    if entity not in {"documents", "sources"}:
        raise ValueError("Metadata entity must be 'documents' or 'sources'.")
    return f"{index_prefix}_{entity}"
