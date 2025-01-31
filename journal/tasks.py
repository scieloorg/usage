import logging

from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from collection.models import Collection
from config import celery_app
from core.utils.utils import _get_user

from . import models, utils


User = get_user_model()


@celery_app.task(bind=True, name=_('Populate Journal data'))
def task_load_journal_data_from_article_meta(self, collection_list=['scl',], force_update=True, user_id=None, username=None):
    user = _get_user(user_id, username)

    for col in collection_list:
        for j in utils.fetch_article_meta_journals(collection=col):
            collection = Collection.objects.get(acron3=j.collection_acronym)
            if not collection:
                continue

            journal, created = models.Journal.objects.get_or_create(collection=collection, scielo_issn=j.scielo_issn)
            
            if created or force_update:
                journal.issns = {
                    'electronic_issn': j.electronic_issn or '', 
                    'print_issn': j.print_issn or '',
                    'scielo_issn': j.scielo_issn
                }
                journal.acronym = j.acronym
                journal.title = j.title
            journal.save()

            logging.info(f'Journal {"created" if created else "updated"}: {journal}')

    return True
