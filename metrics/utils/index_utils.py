from scielo_usage_counter.counter import compute_r5_metrics
from scielo_usage_counter.values import CONTENT_TYPE_UNDEFINED, MEDIA_FORMAT_UNDEFINED

from core.utils import standardizer
from core.utils.date_utils import extract_minute_second_key, truncate_datetime_to_hour


def generate_user_session_id(client_name, client_version, ip_address, datetime, sep='|'):
    """
    Generates a user session ID based on the provided parameters.
    
    Parameters:
        client_name (str): The name of the client.
        client_version (str): The version of the client.
        ip_address (str): The IP address of the user.
        datetime (datetime): The datetime object representing the session time.
        sep (str): The separator to use in the ID. Default is '|'.
    
    Returns:
        str: A user session ID formatted as a string.
    """
    dt_year_month_day = datetime.strftime('%Y-%m-%d')
    dt_hour = datetime.strftime('%H')
    
    return sep.join([
        str(client_name),
        str(client_version),
        str(ip_address),
        str(dt_year_month_day),
        str(dt_hour),
    ])


def generate_item_access_id(col_acron3, scielo_issn, pid_v2, pid_v3, pid_generic, user_session_id, country_code, media_language, media_format, content_type, sep='|'):
    """
    Generates an item access ID based on the provided parameters.

    Parameters:
        col_acron3 (str): The acronym of the collection.
        scielo_issn (str): The ISSN of the SciELO journal.
        pid_v2 (str): The PID version 2.
        pid_v3 (str): The PID version 3.
        pid_generic (str): The generic PID.
        user_session_id (str): The user session ID.
        country_code (str): The country code of the user.
        media_language (str): The language of the media.
        media_format (str): The format of the media.
        content_type (str): The type of content.
        sep (str): The separator to use in the ID. Default is '|'.
    """
    return sep.join([
        col_acron3,
        scielo_issn,
        pid_v2 or '',
        pid_v3 or '',
        pid_generic or '',
        user_session_id,
        country_code,
        media_language,
        media_format,
        content_type,
    ])


def generate_index_name(index_prefix: str, collection: str, date: str):
    """ Generates an index name based on the provided parameters.
    Parameters:
        index_prefix (str): The prefix for the index name.
        collection (str): The collection acronym.
        date (str): The date string in 'YYYY-MM-DD' format.
    Returns:
        str: The formatted index name.
    """
    if not date or not isinstance(date, str):
        raise ValueError("Date must be a non-empty string in 'YYYY-MM-DD' format.")
    
    if not collection or not isinstance(collection, str):
        raise ValueError("Collection must be a non-empty string.")
    
    if not index_prefix or not isinstance(index_prefix, str):
        raise ValueError("Index prefix must be a non-empty string.")

    index_year, _, _ = date.split('-')
    return f'{index_prefix}_{collection}_{index_year}'


def generate_index_id(collection, journal, pid_v2, pid_v3, pid_generic, media_language, country_code, date_str):
    """
    Generates a unique index key based on the provided parameters. 
    This is different from the item access ID as it does not include user session, media_format, and content_type information.
    It is used for indexing purposes.

    Parameters:
        collection (str): The collection acronym.
        journal (str): The journal name.
        pid_v2 (str): The PID version 2.
        pid_v3 (str): The PID version 3.
        pid_generic (str): The generic PID.
        media_language (str): The media language code.
        country_code (str): The country code.
        date_str (str): The date string in 'YYYY-MM-DD' format.
    
    Returns:
        str: A unique index key formatted as a string.
    """
    return '|'.join([
        collection,
        journal,
        pid_v2 or '',
        pid_v3 or '',
        pid_generic or '',
        media_language,
        country_code,
        date_str
    ])


def extract_item_access_data(collection_acron3:str, translated_url: dict):
    """
    Extracts item access data from the translated URL and standardizes it.

    Args:
        collection_acron3 (str): The acronym of the collection.
        translated_url (dict): The translated URL containing metadata.
    
    Returns:
        dict: A dictionary containing standardized item access data, or None if the data is invalid.
    """
    if not translated_url or not isinstance(translated_url, dict):
        return {}
    
    item_access_data = {
        'collection': collection_acron3,
        'scielo_issn': translated_url.get('scielo_issn'),
        'pid_v2': standardizer.standardize_pid_v2(translated_url.get('pid_v2')),
        'pid_v3': standardizer.standardize_pid_v3(translated_url.get('pid_v3')),
        'pid_generic': standardizer.standardize_pid_generic(translated_url.get('pid_generic')),
        'media_language': standardizer.standardize_language_code(translated_url.get('media_language')),
        'media_format': translated_url.get('media_format'),
        'content_type': translated_url.get('content_type'),
        'year_of_publication': standardizer.standardize_year_of_publication(translated_url.get('year_of_publication')),
        'journal_main_title': translated_url.get('journal_main_title'),
        'journal_subject_area_capes': translated_url.get('journal_subject_area_capes'),
        'journal_subject_area_wos': translated_url.get('journal_subject_area_wos'),
        'journal_acronym': translated_url.get('journal_acronym'),
    }
        
    return item_access_data


def is_valid_item_access_data(data: dict, utm=None, ignore_utm_validation=False):
    """
    Validates the item access data based on the provided parameters.

    Parameters:
        data (dict): A dictionary containing the following keys:
            - scielo_issn (str): The ISSN of the SciELO journal.
            - pid_v2 (str): The PID version 2 of the document.
            - pid_v3 (str): The PID version 3 of the document.
            - media_format (str): The media format of the document.
            - content_type (str): The content type of the document.
        utm: URL translation manager for converting URLs
        ignore_utm_validation (bool): If True, skips validation against the URL translation manager.

    Returns:
        tuple: A tuple containing a boolean indicating whether the data is valid and a message.
        If the data is valid, the first element is True and the second element is a success message.
        If the data is invalid, the first element is False and the second element is an error message.
    """
    if not isinstance(data, dict):
        return False, {'message': 'Invalid data format. Expected a dictionary.', 'code': 'invalid_format'}

    scielo_issn = data.get('scielo_issn')
    media_format = data.get('media_format')
    content_type = data.get('content_type')
    pid_v2 = data.get('pid_v2')
    pid_v3 = data.get('pid_v3')
    pid_generic = data.get('pid_generic')

    if not all([
        scielo_issn,
        media_format and media_format != MEDIA_FORMAT_UNDEFINED,
        content_type and content_type != CONTENT_TYPE_UNDEFINED,
        pid_v2 or pid_v3 or pid_generic,
    ]):
        return False, {'message': 'Missing required fields in item access data.', 'code': 'missing_fields'}
    
    # Check ISSN and PIDs validity using the URL translation manager
    if utm and not ignore_utm_validation:
        if not utm.is_valid_code(scielo_issn, utm.journals_metadata['issn_set']):
            return False, {'message': f'Invalid scielo_issn: {scielo_issn}', 'code': 'invalid_scielo_issn'}
        
        if pid_v2 and not utm.is_valid_code(pid_v2, utm.articles_metadata['pid_set']):
            return False, {'message': f'Invalid pid_v2: {pid_v2}', 'code': 'invalid_pid_v2'}
        
        if pid_v3 and not utm.is_valid_code(pid_v3, utm.articles_metadata['pid_set']):
            return False, {'message': f'Invalid pid_v3: {pid_v3}', 'code': 'invalid_pid_v3'}
        
        if pid_generic and not utm.is_valid_code(pid_generic, utm.articles_metadata['pid_set']):
            return False, {'message': f'Invalid pid_generic: {pid_generic}', 'code': 'invalid_pid_generic'}

    return True, {'message': 'Item access data is valid.', 'code': 'valid'}


def update_results_with_item_access_data(results: dict, item_access_data: dict, line: dict):
    """
    Updates the item access data with the information from the log line.

    Args:
        data (dict): The dictionary to store item access data.
        item_access_data (dict): The item access data extracted from the translated URL.
        line (dict): The log line containing additional information.
    
    Returns:
        None.
    """
    col_acron3 = item_access_data.get('collection')
    scielo_issn = item_access_data.get('scielo_issn')
    pid_v2 = item_access_data.get('pid_v2')
    pid_v3 = item_access_data.get('pid_v3')
    pid_generic = item_access_data.get('pid_generic')

    media_format = item_access_data.get('media_format')
    media_language = item_access_data.get('media_language')
    content_type = item_access_data.get('content_type')

    client_name = line.get('client_name')
    client_version = line.get('client_version')
    local_datetime = line.get('local_datetime')
    country_code = line.get('country_code')
    ip_address = line.get('ip_address')

    truncated_datetime = truncate_datetime_to_hour(local_datetime)
    ms_key = extract_minute_second_key(local_datetime)

    user_session_id = generate_user_session_id(
        client_name, 
        client_version, 
        ip_address, 
        truncated_datetime,
    )

    item_access_id = generate_item_access_id(
        user_session_id=user_session_id, 
        col_acron3=col_acron3, 
        scielo_issn=scielo_issn, 
        pid_v2=pid_v2, 
        pid_v3=pid_v3, 
        pid_generic=pid_generic, 
        media_language=media_language, 
        country_code=country_code, 
        media_format=media_format, 
        content_type=content_type, 
    )

    if item_access_id not in results:
        results[item_access_id] = {
            'click_timestamps': {ms_key: 0},
            'media_format': media_format,
            'media_language': media_language,
            'content_type': content_type,
            'country_code': country_code,
            'date_str': truncated_datetime.strftime('%Y-%m-%d'),
            'date': truncated_datetime,
            'year_of_publication': item_access_data.get('year_of_publication'),
            'journal': {
                'scielo_issn': item_access_data.get('scielo_issn'),
                'main_title': item_access_data.get('journal_main_title'),
                'subject_area_capes': item_access_data.get('journal_subject_area_capes'),
                'subject_area_wos': item_access_data.get('journal_subject_area_wos'),
                'acronym': item_access_data.get('journal_acronym'),
            },
        }

    # Check if the click timestamp for this minute-second key exists, if not, initialize it
    if ms_key not in results[item_access_id]['click_timestamps']:
        results[item_access_id]['click_timestamps'][ms_key] = 0

    # Increment the click timestamp count
    results[item_access_id]['click_timestamps'][ms_key] += 1


def convert_to_index_documents(data: dict, key_sep='|'):
    """
    Converts the provided data into a format suitable for indexing metrics.
    This function processes the data dictionary, extracting relevant fields and computing metrics.
    
    Args:
        data (dict): A dictionary containing the metrics data to be processed.

    Returns:
        dict: A dictionary containing the processed metrics data, ready for indexing.
    """
    if not isinstance(data, dict):
        return {}
    
    metrics_data = {}

    for key, value in data.items():
        collection, scielo_issn, pid_v2, pid_v3, pid_generic, _, _, _, _, _, country_code, media_language, _, content_type = key.split(key_sep)

        document_id = generate_index_id(
            collection, 
            scielo_issn, 
            pid_v2, 
            pid_v3, 
            pid_generic, 
            media_language, 
            country_code, 
            value.get('date_str')
        )

        compute_r5_metrics(
            document_id,
            metrics_data,
            collection,
            value.get('journal'),
            pid_v2,
            pid_v3,
            pid_generic,
            value.get('year_of_publication'),
            media_language,
            value.get('country_code'),
            value.get('date_str'),
            value.get('click_timestamps'),
            content_type,
        )
    
    return metrics_data
