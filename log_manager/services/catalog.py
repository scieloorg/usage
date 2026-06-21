import logging
import os

from django.conf import settings

from collection.models import Collection
from core.utils import date_utils
from log_manager import models, utils
from log_manager_config import models as lmc_models


def catalog_log_files_from_configured_directories(
    collections=None,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
):
    from_date_str, until_date_str = date_utils.get_date_range_str(
        from_date, until_date, days_to_go_back
    )
    visible_dates = date_utils.get_date_objs_from_date_range(
        from_date_str, until_date_str
    )
    supported_extensions = settings.SUPPORTED_LOGFILE_EXTENSIONS
    if not supported_extensions:
        logging.error("No supported log file extensions configured.")

    for collection_code in collections or Collection.acron3_list():
        collection = Collection.objects.get(acron3=collection_code)
        directories = lmc_models.CollectionLogDirectory.objects.filter(
            config__collection__acron3=collection_code,
            active=True,
        )
        if not directories:
            logging.error(
                "No CollectionLogDirectory found for collection %s.", collection_code
            )

        for directory in directories:
            _catalog_log_files_in_directory(
                collection=collection,
                directory_path=directory.path,
                visible_dates=visible_dates,
                supported_extensions=supported_extensions,
            )


def _catalog_log_files_in_directory(
    collection,
    directory_path,
    visible_dates,
    supported_extensions,
):
    for root, _sub_dirs, files in os.walk(directory_path):
        for name in files:
            _name, extension = os.path.splitext(name)
            if extension.lower() not in supported_extensions:
                continue

            file_path = os.path.join(root, name)
            file_stat = os.stat(file_path)
            file_ctime = date_utils.get_date_obj_from_timestamp(file_stat.st_ctime)

            logging.debug("Checking file %s with ctime %s.", file_path, file_ctime)
            if file_ctime not in visible_dates:
                continue

            try:
                models.LogFile.create_or_update(
                    collection=collection,
                    path=file_path,
                    stat_result=file_stat,
                    hash=utils.hash_file(file_path),
                )
            except Exception as exc:
                logging.error(
                    "Error cataloging file %s. Error: %s",
                    file_path,
                    exc,
                )
