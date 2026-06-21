import logging

from django.conf import settings

from resources import models, utils


def load_robots(url_robots=None):
    if not url_robots:
        url_robots = settings.COUNTER_ROBOTS_URL
        logging.warning("No robots URL provided. Using default: %s", url_robots)

    try:
        robots_data = utils.fetch_data(url_robots, data_type="json")
    except Exception as e:
        logging.error("Error downloading robots: %s", e)
        return False

    cleaned_robots_data = utils.clean_robots_list(robots_data)
    fetched_patterns = set()

    try:
        for r_str in cleaned_robots_data:
            pattern = r_str.get("pattern")
            last_changed = r_str.get("last_changed")
            fetched_patterns.add(pattern)

            r_obj = models.RobotUserAgent.objects.filter(pattern=pattern).first()
            created = r_obj is None

            if created:
                r_obj = models.RobotUserAgent(
                    pattern=pattern,
                    source_counter=True,
                    source_scielo=False,
                )
            r_obj.source_counter = True
            r_obj.is_active = True
            r_obj.source_url = url_robots
            r_obj.last_changed = last_changed

            r_obj.save()
            logging.debug("Robot saved: %s", r_obj)

        stale_counter_patterns = models.RobotUserAgent.objects.filter(
            source_counter=True
        ).exclude(pattern__in=fetched_patterns)

        for r_obj in stale_counter_patterns:
            r_obj.source_counter = False
            r_obj.source_url = None
            r_obj.last_changed = None
            if not r_obj.source_scielo:
                r_obj.is_active = False
            r_obj.save()
            logging.debug(
                "Robot deactivated or detached from COUNTER source: %s", r_obj
            )

        return True

    except Exception as e:
        logging.error("Error saving robots: %s", e)
        return False


def load_geoip(url_geoip=None, validate=True):
    if url_geoip:
        candidates = [url_geoip]
    else:
        candidates = utils.resolve_mmdb_url()
        logging.info("No GeoIP URL provided. Will try candidates: %s", candidates)

    data = None
    resolved_url = None
    for url in candidates:
        try:
            data = utils.fetch_data(url, data_type="content")
            resolved_url = url
            logging.info("GeoIP data downloaded from: %s", url)
            break
        except Exception as e:
            logging.warning(
                "Failed to download GeoIP from %s: %s. Trying next candidate.", url, e
            )

    if data is None:
        logging.error(
            "Could not download GeoIP data from any candidate URL: %s", candidates
        )
        return False

    try:
        mmdb_data = utils.decompress_gzip(data)
    except Exception as e:
        logging.error("Error decompressing GeoIP data: %s", e)
        return False

    if validate:
        try:
            utils.validate_geoip_data(mmdb_data)
        except Exception as e:
            logging.error("Error validating GeoIP data: %s", e)
            return False

    mmdb_hash = models.MMDB.compute_hash(mmdb_data)

    try:
        mmdb_obj = models.MMDB.objects.get(id=mmdb_hash)
        logging.debug("GeoIP data already exists: %s", mmdb_obj)

    except models.MMDB.DoesNotExist:
        mmdb_obj = models.MMDB.objects.create(id=mmdb_hash, data=mmdb_data)
        mmdb_obj.url = resolved_url

    mmdb_obj.save()
    logging.info("GeoIP data saved (url=%s, hash=%s)", resolved_url, mmdb_hash)

    return True
