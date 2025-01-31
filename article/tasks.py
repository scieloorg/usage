import logging

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.translation import gettext as _

from collection.models import Collection
from config import celery_app
from core.utils.utils import _get_user

from journal.models import Journal
from . import models, utils


User = get_user_model()

@celery_app.task(bind=True, name=_('Load article data from Article Meta'))
def task_load_article_from_article_meta(self, from_date, until_date, force_update=True, user_id=None, username=None):
    user = _get_user(self.request, username=username, user_id=user_id)

    offset = 0
    limit = 1000
    while True:
        response = utils.fetch_article_meta_dict(from_date, until_date, offset=offset, limit=limit)
        objects = response.get('objects')
        if not objects:
            break

        for obj in objects:
            codes = obj.get('code_title')

            for issn in codes:
                jou = Journal.objects.filter(
                    Q(issns__electronic_issn=issn) | 
                    Q(issns__scielo_issn=issn) | 
                    Q(issns__print_issn=issn)
                ).first()
                if not jou:
                    continue

            if not jou:
                logging.info(f'Journal not found for ISSNs: {codes}')
                continue

            collection = Collection.objects.get(acron3=obj.get('collection'))
            if not collection:
                logging.info(f'Collection not found: {obj.get("collection")}')
                continue

            article, created = models.Article.objects.get_or_create(collection=collection, scielo_issn=jou.scielo_issn, pid_v2=obj.get('code'))
            if created or force_update:
                article.pdfs = obj.get('pdfs') or {}
                article.processing_date = obj.get('processing_date') or ''
                article.publication_date = obj.get('publication_date') or ''
                article.publication_year = obj.get('publication_year') or ''
                article.default_lang = obj.get('default_language') or ''
                article.text_langs = obj.get('text_langs') or ''

            article.save()
            logging.debug(f'Article {"created" if created else "updated"}: {article}')

        offset += limit

    return True


@celery_app.task(bind=True, name=_('Load article data from OPAC'))
def task_load_article_from_opac(self, begin_date, end_date, page=1, force_update=True, collection_acron3='scl', user_id=None, username=None):
    user = _get_user(self.request, username=username, user_id=user_id)

    while True:
        response = utils.fetch_opac_dict(begin_date, end_date, page=page)

        documents = response.get('documents')

        for doc_id, doc in documents.items():
            collection = Collection.objects.get(acron3=collection_acron3)
            if not collection:
                logging.error(f'Collection not found: {collection_acron3}')
                continue

            journal = Journal.objects.get(collection=collection, acronym=doc.get('journal_acronym'))
            if not journal:
                logging.error(f'Journal not found: {doc.get("journal_acronym")}')
                continue

            try:
                article, created = models.Article.objects.get_or_create(collection=collection, scielo_issn=journal.scielo_issn, pid_v2=doc.get('pid_v2'))
            except Exception as e:
                logging.error(f'Error creating Article: {e}. Collection: {collection}, Journal: {journal.scielo_issn}, PIDv2: {doc.get("pid_v2")}')
                continue

            if created or force_update:
                article.pid_v3 = doc.get('pid_v3') or ''
                if not created:
                    article.pid_v2 = doc.get('pid_v2') or ''
                    article.publication_date = doc.get('publication_date') or ''
                    article.default_lang = doc.get('default_language') or ''
                    try:
                        article.publication_year = article.publication_date[:4]
                    except IndexError:
                        article.publication_year = ''

                article.save()
                logging.debug(f'Article {"created" if created else "updated"}: {article}')            

        page += 1
        if page > int(response.get('pages', 0)):
            break

    return True
