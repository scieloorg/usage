import logging

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone
from django.utils.translation import gettext as _

from collection.models import Collection
from config import celery_app
from core.utils.utils import _get_user

from . import models, utils


User = get_user_model()


@celery_app.task(bind=True, name=_('Load journal data from Article Meta'))
def task_load_journal_data_from_article_meta(self, collection_list=['scl',], force_update=True, user_id=None, username=None, mode='thrift'):
    user = _get_user(user_id, username)

    for col in collection_list:
        for j in utils.fetch_article_meta_journals(collection=col, mode=mode):
            collection = Collection.objects.get(acron3=j.collection_acronym)
            if not collection:
                logging.error(f'Collection {j.collection_acronym} does not exist')
                continue

            try:
                journal, created = models.Journal.objects.get_or_create(collection=collection, scielo_issn=j.scielo_issn)
            except IntegrityError as e:
                logging.error(f'Journal {j} has not been created due to error: {e}')
                continue

            if created:
                journal.creator = user
                journal.created = timezone.now()
            
            if created or force_update:
                journal.updated_by = user
                journal.updated = timezone.now()
                journal.issns = {
                    'electronic_issn': j.electronic_issn or '', 
                    'print_issn': j.print_issn or '',
                    'scielo_issn': j.scielo_issn
                }
                journal.acronym = j.acronym
                journal.title = j.title
                journal.publisher_name = j.publisher_name or ''
                journal.subject_areas = j.subject_areas or []
                journal.wos_subject_areas = j.wos_subject_areas or []
                logging.info(f'Journal {"created" if created else "updated"}: {journal}')

            journal.save()

    return True
