from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils.translation import gettext as _

from core.utils.utils import _get_user
from config import celery_app
from tracker.models import Top100ArticlesFileEvent

from .exceptions import Top100ArticlesFileNotFoundError, Top100ArticlesFileAttachmentNotFoundError
from .models import Top100Articles, Top100ArticlesFile
from .utils import get_load_data_function


User = get_user_model()


@celery_app.task(bind=True, name=_('Process File for Top100 Article Metrics'), timelimit=-1)
def task_process_top100_file(self, file_id=None, bulk_size=50000, user_id=None, username=None):
    """
    Process a file to create or update `Top100Articles`.

    Parameters:
        file_id (int, optional): Specific file ID to process.
        bulk_size (int): Number of records to process per batch.
        user_id (int, optional): User ID for context.
        username (str, optional): Username for context.
    """    
    top100_files = Top100ArticlesFile.objects.filter(
        pk=file_id) if file_id else Top100ArticlesFile.objects.filter(status=Top100ArticlesFile.Status.QUEUED).order_by('-created')

    for obj_file in top100_files:
        obj_file.status = Top100ArticlesFile.Status.PARSING
        obj_file.save()
        task_process_top100_file_item.apply_async(args=(obj_file.pk, bulk_size, user_id, username))


@celery_app.task(bind=True, name=_('Process File Item for Top100 Article Metrics'), timelimit=-1)
def task_process_top100_file_item(self, file_id, bulk_size=50000, user_id=None, username=None):
    """
    Process items in a file to create or update `Top100Articles`.

    Parameters:
        file_id (int): ID of the file to process.
        bulk_size (int): Number of records per batch.
        user_id (int, optional): ID of the user performing the action.
        username (str, optional): Username of the user performing the action.
    """
    user = _get_user(self.request, username=username, user_id=user_id)

    objs_create, objs_update = [], []
    lines = 0

    try:
        obj_file = Top100ArticlesFile.objects.get(pk=file_id)
    except Top100ArticlesFile.DoesNotExist:
        raise Top100ArticlesFileNotFoundError(f'Top100ArticlesFile with id {file_id} does not exist.')

    try:
        load_data_function = get_load_data_function(obj_file.attachment.file.path)
    except AttributeError:
        obj_file.status = Top100ArticlesFile.Status.ERROR
        obj_file.save()
        Top100ArticleFileEvent.create(
            user=user,
            file=obj_file,
            status=obj_file.status,
            lines=lines,
            message=f'Attachment related to {file_id} does not exist.',
        )
        raise Top100ArticlesFileAttachmentNotFoundError(f'Attachment related to {file_id} does not exist.')
    
    try:
        for row in load_data_function(obj_file.attachment.file.path):
            obj_top100, created = Top100Articles.create_or_update(user=user, save=False, **row)
            if created:
                objs_create.append(obj_top100)
            else:
                objs_update.append(obj_top100)

            if len(objs_create) >= bulk_size:
                Top100Articles.bulk_create(objs_create)
                objs_create = []
                lines += len(objs_create)

            if len(objs_update) >= bulk_size:
                Top100Articles.bulk_update(objs_update)
                objs_update = []
                lines += len(objs_update)

        if objs_create:
            Top100Articles.bulk_create(objs_create)
            lines += len(objs_create)
    
        if objs_update:
            Top100Articles.bulk_update(objs_update)
            lines += len(objs_update)
    
    except OSError as e:
        obj_file.status = Top100ArticlesFile.Status.ERROR
        Top100ArticlesFileEvent.create(
            user=user,
            file=obj_file,
            status=obj_file.status,
            lines=lines,
            message=str(e),
        )
    except Exception as e:
        obj_file.status = Top100ArticlesFile.Status.ERROR
        Top100ArticlesFileEvent.create(
            user=user,
            file=obj_file,
            status=obj_file.status,
            lines=lines,
            message=str(e),
        )        
    else:
        obj_file.status = Top100ArticlesFile.Status.PROCESSED
        Top100ArticlesFileEvent.create(
            user=user,
            file=obj_file,
            status=obj_file.status,
            lines=lines,
            message='File processed successfully.',
        )
    finally:
        obj_file.save()


@celery_app.task(bind=True, name=_('Rebuild Metrics Index'), timelimit=-1)
def rebuild_metrics_index(self, user_id=None, username=None):
    """Celery task to rebuild the index for metrics."""
    
    user = _get_user(self.request, username=username, user_id=user_id)
    call_command('rebuild_index', '--using=metrics', 'metrics.Top100Articles')


@celery_app.task(bind=True, name=_('Update Metrics Index'), timelimit=-1)
def update_metrics_index(self, user_id=None, username=None):
    """Celery task to update the index for metrics."""
    
    user = _get_user(self.request, username=username, user_id=user_id)
    call_command('update_index', '--using=metrics', 'metrics.Top100Articles')
