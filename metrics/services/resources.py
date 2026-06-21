import logging

from resources.models import MMDB, RobotUserAgent


def fetch_required_resources(robot_source=None):
    robots_list = RobotUserAgent.get_patterns(source=robot_source)
    if not robots_list:
        logging.error(
            "There are no robots available in the database for source %s.",
            RobotUserAgent.normalize_source(robot_source),
        )
        return None, None

    try:
        mmdb = MMDB.objects.latest("created")
    except MMDB.DoesNotExist:
        logging.error("There are no MMDB files available in the database.")
        return None, None

    return robots_list, mmdb
