import logging

from datetime import datetime, timedelta


def get_str_date(date_obj: datetime, format: str = "%Y-%m-%d") -> str:
    """
    Convert a date object to a string date.

    Args:
        date_obj: Date object.

    Returns:
        String date.
    """
    return date_obj.strftime(format)

def get_obj_date(date_str: str, format: str = "%Y-%m-%d") -> datetime.date:
    """
    Generate a date object from a string date.

    Args:
        date_str: String date.

    Returns:
        Date object.
    """
    try:
        return datetime.strptime(date_str, format).date()
    except (ValueError, TypeError):
        logging.error("Invalid date format. Use YYYY-MM-DD.")

def get_str_date_range(from_date_str: str = None, until_date_str: str = None, days_to_go_back: int = None) -> tuple[str, str]:
    """
    Get the date range to be used in the queries.

    Args:
        from_date_str: Date to start the query.
        until_date_str: Date to end the query.
        days_to_go_back: Number of days to go back from the current date.

    Returns:
        Tuple with the from_date and until_date.
    """
    today = datetime.now().date()

    if days_to_go_back:
        return get_str_date(today - timedelta(days=days_to_go_back)), get_str_date(today)

    from_date_obj = get_obj_date(from_date_str)
    until_date_obj = get_obj_date(until_date_str)

    if from_date_obj and until_date_obj:
        return from_date_str, until_date_str

    if from_date_obj:
        return from_date_str, get_str_date(from_date_obj + timedelta(days=7))

    if until_date_obj:
        return get_str_date(until_date_obj - timedelta(days=7)), until_date_str
    
    return get_str_date(today - timedelta(days=7)), get_str_date(today)
