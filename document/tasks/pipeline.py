import logging

from celery import group
from django.utils.translation import gettext as _

from config import celery_app

from document.tasks.articlemeta import task_load_documents_from_article_meta
from document.tasks.dataverse import task_load_dataset_metadata_into_documents
from document.tasks.opac import task_load_documents_from_opac
from document.tasks.preprints import task_load_preprints_into_documents
from document.tasks.scielo_books import task_sync_documents_from_scielo_books


@celery_app.task(
    bind=True, name=_("[Metadata] Daily Sync Routine (Auto)"), queue="load"
)
def task_daily_metadata_sync_pipeline(self):
    logging.info("Starting Daily Metadata Sync Pipeline")
    group(
        [
            task_load_documents_from_article_meta.s(),
            task_load_documents_from_opac.s(),
            task_load_preprints_into_documents.s(),
            task_load_dataset_metadata_into_documents.s(),
            task_sync_documents_from_scielo_books.s(),
        ]
    ).apply_async()
