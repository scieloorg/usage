import logging
import os

from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from core.utils.utils import _get_user
from config import celery_app

from . import (
    models,
    utils,
)


User = get_user_model()


@celery_app.task(bind=True, name=_('Load Top100 Article Metrics from directory'))
def task_load_top100_from_dir(self, dir=None, user_id=None, username=None):
    """
    Task to load most accessed articles by journal.

    Parameters:
        dir (path): Directory path containing the top100 metrics files
        user_id
        username
    
    Returns:
        None.
    """
    user = _get_user(self.request, username=username, user_id=user_id)

    for root, sub_dirs, files in os.walk(dir):
        for name in files:
            if not name.lower().endswith('.csv'):
                continue

            file_path = os.path.join(root, name)
            for row in utils.load_csv(file_path):
                try:
                    models.Top100ArticlesByJournal.create(
                        user=user,
                        key_issn=row['pid_issn'],
                        online_issn=row['online_issn'],
                        print_issn=row['print_issn'],
                        year_month_day=row['year_month_day'],
                        collection=row['collection'],
                        pid=row['pid'],
                        yop=row['yop'],
                        total_item_requests=row['total_item_requests'],
                        total_item_investigations=row['total_item_investigations'],
                        unique_item_requests=row['unique_item_requests'],
                        unique_item_investigations=row['unique_item_investigations'],
                    )
                except KeyError as e:
                    logging.info(_(f'File {file_path} does not contain all of the necessary data. Message: {e}'))


@celery_app.task(bind=True, name=_('Load Top100 Article Metrics from file'))
def task_load_top100_from_file(self, file_path, user_id=None, username=None):
    """
    Task to load most accessed articles by journal.

    Args:
        path (str): File path of the top100 metrics data.
        user_id
        username

    Returns:
        None.
    """
    user = _get_user(self.request, username=username, user_id=user_id)
    
    logging.info(f'Processing file {file_path}')
    for row in utils.load_csv(file_path):
        try:
            models.Top100ArticlesByJournal.create(
                user=user,
                key_issn=row['pid_issn'],
                online_issn=row['online_issn'],
                print_issn=row['print_issn'],
                year_month_day=row['year_month_day'],
                collection=row['collection'],
                pid=row['pid'],
                yop=row['yop'],
                total_item_requests=row['total_item_requests'],
                total_item_investigations=row['total_item_investigations'],
                unique_item_requests=row['unique_item_requests'],
                unique_item_investigations=row['unique_item_investigations'],
            )
        except KeyError as e:
            logging.info(_(f'File {file_path} does not contain all of the necessary data. Message: {e}'))
