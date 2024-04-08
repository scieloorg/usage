from datetime import datetime, timedelta

import hashlib
import logging
import os

from scielo_log_validator import validator
from app.lib import (
    logparser,
    file
)
from app.proc import (
    download_geomap,
    download_robots,
)

from .choices import (
    TEMPORAL_REFERENCE_YESTERDAY,
    TEMPORAL_REFERENCE_LAST_WEEK,
)


def temporal_reference_to_datetime(text):
    text = text.lower()

    if text:
        if text == TEMPORAL_REFERENCE_YESTERDAY:
            return datetime.now() - timedelta(days=1)
                
        if text == TEMPORAL_REFERENCE_LAST_WEEK:
            return datetime.now() - timedelta(weeks=1)
        
    raise ValueError()


def formatted_text_to_datetime(text, format="%Y-%m-%d"):
    try:
        return datetime.strptime(text, format)
    except ValueError:
        raise


def timestamp_to_datetime(timestamp):
    return datetime.fromtimestamp(timestamp)


def hash_file(path, num_lines=25):
    """
    Calculates the MD5 hash of a file using a combination of its first and last `num_lines` lines, 
    as well as its size.
    
    Args:
        path (str): The path to the file.
        num_lines (int): The number of lines to consider from the beginning and end of the file. Default is 25.

    Returns:
        The MD5 hash digest as a hexadecimal string.
    """
    md5_hash = hashlib.md5()

    with open(path, 'rb') as file:
        # Read the first `num_lines` lines of the file
        first_lines = b''.join([file.readline() for _ in range(num_lines)])
        md5_hash.update(first_lines)

        # Move the file pointer to the end of the file
        file.seek(0, 2)

        # Get the size of the file
        size = file.tell()
        md5_hash.update(str(size).encode())

        # Move the file pointer to the start of the file
        file.seek(-size, 2)

        # Read the last `num_lines` lines of the file
        last_lines = file.readlines()[-num_lines:]
        md5_hash.update(b''.join(last_lines))

    return md5_hash.hexdigest()


def validate_file(path, sample_size=0.05):
    # FIXME: It does not seem right to call a method starting with the '_' char. 
    #   It depends on the scielo_log_validator to become more flexible.
    validations = [
        validator._validate_path,
        validator._validate_content,
    ]

    return validator.validate(path, validations=validations, sample_size=sample_size)


def download_supplies(output_dir, url_robots, url_geomap):
    robots = download_robots.get_robots(url_robots)
    robots_path = os.path.join(output_dir, 'robots.txt')
    download_robots.save(robots, robots_path)

    mmdb_path = os.path.join(output_dir, 'geomap.mmdb.gz')
    download_geomap.download_mmdb(url_geomap, mmdb_path)

    geo_path_extracted = mmdb_path.replace('.gz', '')
    file.extract_gzip(mmdb_path, geo_path_extracted)

    return robots_path, geo_path_extracted


def parse_file(path_geomap, path_robots, path_log):
    lp = logparser.LogParser(path_geomap, path_robots)
    lp.logfile = path_log

    # FIXME: It depends on the counter-access library to become more flexible.
    lp.output = f'{path_log}.processed'
    lp.stats.output = f'{path_log}.summary'

    logging.info(f'INFO. LogParser has been started processing {lp.logfile}')
    for row in lp.parse():
        '''
        hit.local_datetime
        hit.client_name
        hit.client_version
        hit.ip
        hit.geolocation
        hit.action
        '''
        yield row
