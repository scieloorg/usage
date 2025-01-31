import logging
import gzip
import io
import requests
import tempfile

from time import sleep

import geoip2.database


def fetch_data(url, data_type='json', max_retries=5, sleep_time=30):
    """
    Retrieves data from the given URL.

    Parameters
    ----------
    url : str
        The URL of the data.
    data_type : str, optional
        The type of data to retrieve ('json' or 'content', default is 'json').
    max_retries : int, optional
        The maximum number of retries in case of a failed request (default is 5).
    sleep_time : int, optional
        The time to wait between retries in seconds (default is 30).

    Raises
    ------
    requests.exceptions.HTTPError
        If the request fails after the maximum number of retries.

    Returns
    -------
    dict or bytes
        The retrieved data. If data_type is 'json', returns a JSON object.
        If data_type is 'content', returns the raw content.
    """
    for t in range(1, max_retries + 1):
        response = requests.get(url)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            logging.warning(
                'Failed to retrieve data from %s. Waiting %d seconds before retry %d of %d' % (
                    url, 
                    sleep_time, 
                    t, 
                    max_retries
                )
            )
            sleep(sleep_time)
        else:
            if data_type == 'json':
                return response.json()
            elif data_type == 'content':
                return response.content
            else:
                raise ValueError("Invalid data_type. Expected 'json' or 'content'.")


def clean_robots_list(robots):
    """
    Cleans a list of robots.

    Parameters
    ----------
    robots : list
        A list of robots.

    Returns
    -------
    list
        A cleaned list of robots.
    """
    cleaned_robots = []
    for r in robots:
        if r.get('pattern') and r.get('last_changed'):
            cleaned_robots.append(r)
    return cleaned_robots


def decompress_gzip(data):
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
            return f.read()
    except Exception as e:
        raise Exception(f'Error decompressing data: {e}')


def validate_geoip_data(data):
    try:
        with tempfile.NamedTemporaryFile(delete=True) as temp_file:
            temp_file.write(data)
            temp_file.flush()
            reader = geoip2.database.Reader(temp_file.name)
    except Exception as e:
        raise Exception(f'Error validating GeoIP data: {e}')
    else:
        reader.close()
        return True
