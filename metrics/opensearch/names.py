def _validate_index_inputs(index_prefix, collection, date):
    if not date or not isinstance(date, str):
        raise ValueError("Date must be a non-empty string in 'YYYY-MM-DD' format.")
    if not collection or not isinstance(collection, str):
        raise ValueError("Collection must be a non-empty string.")
    if not index_prefix or not isinstance(index_prefix, str):
        raise ValueError("Index prefix must be a non-empty string.")


def extract_access_year(date):
    _validate_index_inputs("usage", "tmp", date)
    return date.split("-")[0]


def generate_month_index_name(index_prefix, collection, date):
    _validate_index_inputs(index_prefix, collection, date)
    return f"{index_prefix}_monthly_{collection}_{extract_access_year(date)}"


def generate_analytics_index_name(index_prefix, collection, date):
    _validate_index_inputs(index_prefix, collection, date)
    return f"{index_prefix}_yearly_analytics_{collection}_{extract_access_year(date)}"


def generate_physical_index_name(alias_name):
    return f"{alias_name}_000001"


def generate_metadata_alias(entity):
    if entity not in {"documents", "sources"}:
        raise ValueError("Metadata entity must be 'documents' or 'sources'.")
    return f"usage_{entity}"
