from config.collections import get_collection_size


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
    size = get_collection_size(collection)
    if size in ("xlarge", "large"):
        return f"{index_prefix}_monthly_{collection}_{extract_access_year(date)}"
    return f"{index_prefix}_monthly_{collection}"


def generate_year_index_name(index_prefix, collection, date):
    _validate_index_inputs(index_prefix, collection, date)
    size = get_collection_size(collection)
    if size in ("xlarge", "large"):
        return f"{index_prefix}_yearly_{collection}_{extract_access_year(date)}"
    return f"{index_prefix}_yearly_{collection}"
