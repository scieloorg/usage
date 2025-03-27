import logging

from datetime import datetime, timedelta


def get_date_str(date_obj: datetime, format: str = "%Y-%m-%d") -> str:
    """
    Convert a date object to a string date.

    Args:
        date_obj: Date object.

    Returns:
        String date.
    """
    return date_obj.strftime(format)


def get_date_obj(date_str: str, format: str = "%Y-%m-%d") -> datetime.date:
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


def get_date_range_str(from_date_str: str = None, until_date_str: str = None, days_to_go_back: int = None) -> tuple[str, str]:
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
        return get_date_str(today - timedelta(days=days_to_go_back)), get_date_str(today)

    from_date_obj = get_date_obj(from_date_str)
    until_date_obj = get_date_obj(until_date_str)

    if from_date_obj and until_date_obj:
        return from_date_str, until_date_str

    if from_date_obj:
        return from_date_str, get_date_str(from_date_obj + timedelta(days=7))

    if until_date_obj:
        return get_date_str(until_date_obj - timedelta(days=7)), until_date_str
    
    return get_date_str(today - timedelta(days=7)), get_date_str(today)


def get_date_obj_from_timestamp(timestamp):
    return datetime.fromtimestamp(timestamp).date()


def get_date_objs_from_date_range(from_date, until_date, format='%Y-%m-%d'):
    visible_dates = []

    if not isinstance(from_date, datetime):
        from_date = datetime.strptime(from_date, format).date()
        
    if not isinstance(until_date, datetime):
        until_date = datetime.strptime(until_date, format).date()

    current = from_date
    while current <= until_date:
        visible_dates.append(current)
        current += timedelta(days=1)

    return visible_dates


def truncate_datetime_to_hour(dt):
    """
    Truncates a datetime object to the hour.
    Parameters:
    dt (datetime or str): The datetime object or string to be truncated.

    Returns:
    datetime: The truncated datetime object.
    """
    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            logging.error("Invalid datetime string format. Expected '%Y-%m-%d %H:%M:%S'.")
            return None

    return dt.replace(minute=0, second=0, microsecond=0)


def extract_minute_second_key(dt):
    """
    Extracts a tuple based on the minute and second of a datetime object.

    Parameters:
    dt (datetime or str): The datetime object or string.

    Returns:
    str: A string in the format "MM:SS" representing the minute and second.
    """
    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            logging.error("Invalid datetime string format. Expected '%Y-%m-%d %H:%M:%S'.")
            return None

    return f"{dt.minute:02}:{dt.second:02}"
