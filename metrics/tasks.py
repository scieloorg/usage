import logging

from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from haystack.management.commands import update_index, rebuild_index

from core.utils.utils import _get_user
from config import celery_app
from tracker.models import UnexpectedEvent

from .exceptions import Top100ArticlesFileNotFoundError
from .models import Top100Articles, Top100ArticlesFile
from .utils import get_load_data_function


User = get_user_model()


@celery_app.task(bind=True, name=_('Load Top100 Article Metrics'), timelimit=-1)
def task_load_top100_articles(self, update=False, file_id=None, bulk_size=50000, user_id=None, username=None):
    """
    Load Top 100 article metrics from CSV files.

    Parameters:
        update (bool): Whether to update existing data.
        file_id (int, optional): Specific file ID to process.
        bulk_size (int): Number of records to process per batch.
        user_id (int, optional): User ID for context.
        username (str, optional): Username for context.
    """
    if isinstance(update, str):
        update = update.lower() == 'true'
    
    top100_files = Top100ArticlesFile.objects.filter(
        pk=file_id) if file_id else Top100ArticlesFile.objects.filter(status=Top100ArticlesFile.Status.QUEUED).order_by('-created')

    for obj_file in top100_files:
        logging.info(f'Processing file {obj_file.attachment.file.path}')
        obj_file.status = Top100ArticlesFile.Status.PARSING
        obj_file.save()
        task_process_file.apply_async(args=(obj_file.pk, update, bulk_size, user_id, username))


@celery_app.task(bind=True, name=_('Process CSV File'), timelimit=-1)
def task_process_file(self, file_id, update, bulk_size, user_id=None, username=None):
    """
    Process a CSV file to create or update `Top100Articles`.

    Parameters:
        file_id (int): ID of the file to process.
        update (bool): Whether to update existing records.
        bulk_size (int): Number of records per batch.
        user_id (int, optional): ID of the user performing the action.
        username (str, optional): Username of the user performing the action.
    """
    user = _get_user(self.request, username=username, user_id=user_id)

    try:
        obj_file = Top100ArticlesFile.objects.get(pk=file_id)
    except Top100ArticlesFile.DoesNotExist:
        raise Top100ArticlesFileNotFoundError(f'Top100ArticlesFile with id {file_id} does not exist.')

    load_data_function = get_load_data_function(obj_file.attachment.file.path)
    
    objs_create, objs_update = [], []

    try:
        for row in load_data_function(obj_file.attachment.file.path):
            obj_top100, created = Top100Articles.create_or_update(user=user, save=False, **row)
            if created:
                objs_create.append(obj_top100)
            elif update:
                objs_update.append(obj_top100)

            if len(objs_create) >= bulk_size:
                Top100Articles.bulk_create(objs_create)
                objs_create = []

            if update and len(objs_update) >= bulk_size:
                Top100Articles.bulk_update(objs_update)
                objs_update = []

        if objs_create:
            Top100Articles.bulk_create(objs_create)
    
        if update and objs_update:
            Top100Articles.bulk_update(objs_update)
    
    except OSError as e:
        UnexpectedEvent.create(
            OSError(f'It was not possible to process file {obj_file.attachment.file.path}.'),
            detail={'File': obj_file.attachment.file.path, 'Message': e}
        )
        obj_file.status = Top100ArticlesFile.Status.INVALIDATED
    else:
        obj_file.status = Top100ArticlesFile.Status.PROCESSED
    obj_file.save()


@celery_app.task(bind=True, name=_('Rebuild Metrics Index'), timelimit=-1)
def rebuild_metrics_index(self, user_id=None, username=None):
    """Celery task to rebuild the index for metrics."""
    
    user = _get_user(self.request, username=username, user_id=user_id)
    rebuild_index.Command().handle(interactive=False, using='metrics')


@celery_app.task(bind=True, name=_('Update Metrics Index'), timelimit=-1)
def update_metrics_index(self, user_id=None, username=None):
    """Celery task to update the index for metrics."""
    
    user = _get_user(self.request, username=username, user_id=user_id)
    update_index.Command().handle(interactive=False, using='metrics')
