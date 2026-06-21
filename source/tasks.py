from django.conf import settings

from config import celery_app
from core.utils.request_utils import _get_user
from source.services import loaders


@celery_app.task(bind=True, name="[Metadata] Sync Sources (Article Meta)", queue="load")
def task_load_sources_from_article_meta(
    self,
    collections=None,
    force_update=True,
    user_id=None,
    username=None,
    mode="thrift",
):
    user = _get_user(self.request, username=username, user_id=user_id)
    return loaders.load_sources_from_article_meta(
        collections=collections,
        force_update=force_update,
        user=user,
        mode=mode,
    )


@celery_app.task(bind=True, name="[Metadata] Sync Sources (SciELO Books)", queue="load")
def task_load_sources_from_scielo_books(
    self,
    collection="books",
    db_name=settings.SCIELO_BOOKS_DB_NAME,
    since=0,
    limit=settings.SCIELO_BOOKS_LIMIT,
    force_update=True,
    headers=None,
    base_url=None,
    user_id=None,
    username=None,
):
    user = _get_user(self.request, username=username, user_id=user_id)
    return loaders.load_sources_from_scielo_books(
        collection=collection,
        db_name=db_name,
        since=since,
        limit=limit,
        force_update=force_update,
        headers=headers,
        base_url=base_url,
        user=user,
    )
