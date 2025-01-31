import logging

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext as _

from config import celery_app
from core.utils.utils import _get_user

from . import constants, models, utils


User = get_user_model()

@celery_app.task(bind=True, name=_('Download robots data'))
def task_download_robots(self, url_robots=None, user_id=None, username=None):
    """
    Downloads robot data from the specified URL.

    If no URL is provided, the default URL from constants.DEFAULT_COUNTER_ROBOTS_URL is used.

    Args:
        url_robots (str, optional): The URL to download the robots data from. Defaults to None.
        user_id (int, optional): The ID of the user requesting the download. Defaults to None.
        username (str, optional): The username of the user requesting the download. Defaults to None.

    Returns:
        dict: The downloaded robot data in JSON format.

    Raises:
        Exception: If there is an error during the download process.

    Logs:
        Warning: If no URL is provided and the default URL is used.
        Error: If there is an error during the download process.
    """
    if not url_robots:
        url_robots = constants.DEFAULT_COUNTER_ROBOTS_URL
        logging.warning(f'No robots URL provided. Using default: {url_robots}')

    try:
        return utils.fetch_data(url_robots, data_type='json')
    except Exception as e:
        logging.error(f'Error downloading robots: {e}')


@celery_app.task(bind=True, name=_('Save robots data'))
def task_save_robots(self, robots, user_id=None, username=None):
    """
    Adds a list of robots to the database.
    This function processes a list of robots, cleans the list, and saves each robot to the database.
    If a robot with the same pattern and last_changed date already exists, it updates the existing
    robot. Otherwise, it creates a new robot entry.
    Args:
        robots (list): A list of dictionaries, where each dictionary represents a robot with keys
                       'pattern' and 'last_changed'.
        user_id (int, optional): The ID of the user performing the operation. Defaults to None.
        username (str, optional): The username of the user performing the operation. Defaults to None.
    Returns:
        bool: True if all robots were successfully saved, False otherwise.
    Raises:
        Exception: If there is an error while saving the robots.
    Logs:
        - Error if no robots are provided.
        - Debug information for each robot saved.
        - Error if there is an exception during the saving process.
    """
    user = _get_user(self.request, username=username, user_id=user_id)

    if not robots:
        logging.error('No robots to save.')
        return False
    
    robots = utils.clean_robots_list(robots)

    try:
        for r_str in robots:
            pattern = r_str.get('pattern')
            last_changed = r_str.get('last_changed')

            r_obj, created = models.RobotUserAgent.objects.get_or_create(pattern=pattern, last_changed=last_changed)

            if created:
                r_obj.creator = user

            r_obj.updated = timezone.now()
            r_obj.updated_by = user

            r_obj.save()
            logging.debug(f'Robot saved: {r_obj}')
        return True

    except Exception as e:
        logging.error(f'Error saving robots: {e}')


@celery_app.task(bind=True, name=_('Download GeoIP data'))
def task_download_geoip(self, url_geoip=None, user_id=None, username=None, validate=True):
    """
    Downloads and processes GeoIP data from a given URL.
    Args:
        url_geoip (str, optional): The URL to download the GeoIP data from. 
                                   If not provided, a default URL is used.
        user_id (int, optional): The ID of the user requesting the download.
        username (str, optional): The username of the user requesting the download.
        validate (bool, optional): Whether to validate the downloaded GeoIP data. 
                                   Defaults to True.
    Returns:
        bytes: The processed GeoIP data if successful, otherwise None.
    Raises:
        None: All exceptions are logged and None is returned in case of errors.
    """
    if not url_geoip:
        url_geoip = constants.DEFAULT_MMDB_URL
        logging.warning(f'No GeoIP URL provided. Using default: {url_geoip}')
                                                                  
    try:
        data = utils.fetch_data(url_geoip, data_type='content')
    except Exception as e:
        logging.error(f'Error downloading GeoIP: {e}')
        return None

    try:
        data = utils.decompress_gzip(data)
    except Exception as e:
        logging.error(f'Error decompressing GeoIP data: {e}')
        return None

    if validate:
        try:
            utils.validate_geoip_data(data)
        except Exception as e:
            logging.error(f'Error validating GeoIP data: {e}')
            return None

    return data


@celery_app.task(bind=True, name=_('Save GeoIP data'))
def task_save_geoip(self, mmdb_data, mmdb_url=None, user_id=None, username=None):
    """
    Save GeoIP data to the database.
    This function computes the hash of the provided GeoIP data and checks if it already exists in the database.
    If the data does not exist, it creates a new entry. It also updates the metadata such as the creator and the 
    last updated timestamp.
    Args:
        mmdb_data (file-like object): The GeoIP data file to be saved.
        user_id (int, optional): The ID of the user performing the operation. Defaults to None.
        username (str, optional): The username of the user performing the operation. Defaults to None.
    Returns:
        bool: True if the operation was successful.
    """
    user = _get_user(self.request, username=username, user_id=user_id)

    if not mmdb_data:
        logging.error('No valid GeoIP data to save.')
        return False
    
    mmdb_hash = models.MMDB.compute_hash(mmdb_data)
    
    try:    
        mmdb_obj = models.MMDB.objects.get(id=mmdb_hash)
        logging.debug(f'GeoIP data already exists: {mmdb_obj}')

    except models.MMDB.DoesNotExist:
        mmdb_obj = models.MMDB.objects.create(id=mmdb_hash, data=mmdb_data)
        mmdb_obj.url = mmdb_url or constants.DEFAULT_MMDB_URL
        mmdb_obj.creator = user

    mmdb_obj.updated = timezone.now()
    mmdb_obj.updated_by = user

    mmdb_obj.save()
    logging.debug(f'GeoIP data has been saved: {mmdb_obj}')
    
    return True
