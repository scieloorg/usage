import logging

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db import DataError
from django.utils.translation import gettext as _

from collection.models import Collection
from config import celery_app
from core.utils import date_utils
from core.utils.utils import _get_user

from journal.models import Journal

from tracker.models import ArticleEvent
from tracker.choices import ARTICLE_EVENT_TYPE_MULTIPLE_OBJS_RETURNED, ARTICLE_EVENT_TYPE_DATA_ERROR

from . import models, utils


User = get_user_model()

@celery_app.task(bind=True, name=_('Load article data from Article Meta'), timelimit=-1)
def task_load_article_from_article_meta(self, from_date=None, until_date=None, days_to_go_back=None, collection=None, issn=None, force_update=True, user_id=None, username=None):
    user = _get_user(self.request, username=username, user_id=user_id)

    from_date, until_date = date_utils.get_date_range_str(from_date, until_date, days_to_go_back)
    logging.info(f'Loading articles from Article Meta. From: {from_date}, Until: {until_date}, Collection: {collection}, ISSN: {issn}.')

    offset = 0
    limit = 1000
    while True:
        logging.info(f'{from_date}, {until_date}, {offset}, {limit}, {collection}, {issn}')
        response = utils.fetch_article_meta_dict(from_date, until_date, offset=offset, limit=limit, collection=collection, issn=issn)
        objects = response.get('objects')
        if not objects:
            break

        for obj in objects:
            codes = obj.get('code_title')

            for issn_code in codes:
                jou = Journal.objects.filter(
                    Q(issns__electronic_issn=issn_code) | 
                    Q(issns__scielo_issn=issn_code) | 
                    Q(issns__print_issn=issn_code)
                ).first()
                if not jou:
                    continue

            if not jou:
                logging.info(f'Journal not found for ISSNs: {codes}')
                continue

            col_obj = Collection.objects.get(acron3=obj.get('collection'))
            if not col_obj:
                logging.info(f'Collection not found: {obj.get("collection")}')
                continue

            try:
                article, created = models.Article.objects.get_or_create(collection=col_obj, scielo_issn=jou.scielo_issn, pid_v2=obj.get('code'))
                if created or force_update:
                    article.files = obj.get('files') or {}
                    article.processing_date = obj.get('processing_date') or ''
                    article.publication_date = obj.get('publication_date') or ''
                    article.publication_year = obj.get('publication_year') or ''
                    article.default_lang = obj.get('default_language') or ''
                    article.text_langs = obj.get('text_langs') or ''

                article.save()
                logging.info(f'Article {"created" if created else "updated"}: {article}')
            except article.MultipleObjectsReturned as e:
                logging.error(f'Error getting Article: {e}. Collection: {col_obj}, ISSN: {jou.scielo_issn}, PIDv2: {obj.get("code")}')
                ArticleEvent.create(
                    user=user,
                    event_type=ARTICLE_EVENT_TYPE_MULTIPLE_OBJS_RETURNED,
                    message=f'Error getting Article: {e}. Collection: {col_obj}, ISSN: {jou.scielo_issn}, PIDv2: {obj.get("code")}',
                    data=obj
                )
                continue
            except DataError as e:
                logging.error(f'Error saving Article: {e}. Collection: {col_obj}, ISSN: {jou.scielo_issn}, PIDv2: {obj.get("code")}')
                ArticleEvent.create(
                    user=user,
                    event_type=ARTICLE_EVENT_TYPE_DATA_ERROR,
                    message=f'Error saving Article: {e}. Collection: {col_obj}, ISSN: {jou.scielo_issn}, PIDv2: {obj.get("code")}',
                    data=obj
                )
                continue

        offset += limit

    return True


@celery_app.task(bind=True, name=_('Load article data from OPAC'), timelimit=-1)
def task_load_article_from_opac(self, collection='scl', from_date=None, until_date=None, days_to_go_back=None, page=1, force_update=True, user_id=None, username=None):
    user = _get_user(self.request, username=username, user_id=user_id)

    from_date, until_date = date_utils.get_date_range_str(from_date, until_date, days_to_go_back)
    logging.info(f'Loading articles from OPAC. From: {from_date}, Until: {until_date}')

    while True:
        response = utils.fetch_opac_dict(from_date, until_date, page=page)

        documents = response.get('documents')

        for doc_id, doc in documents.items():
            col_obj = Collection.objects.get(acron3=collection)
            if not col_obj:
                logging.error(f'Collection not found: {collection}')
                continue

            journal = Journal.objects.get(collection=col_obj, acronym=doc.get('journal_acronym'))
            if not journal:
                logging.error(f'Journal not found: {doc.get("journal_acronym")}')
                continue

            try:
                article, created = models.Article.objects.get_or_create(collection=col_obj, scielo_issn=journal.scielo_issn, pid_v2=doc.get('pid_v2'))
            except article.MultipleObjectsReturned as e:
                logging.error(f'Error getting Article: {e}. Collection: {col_obj}, Journal: {journal.scielo_issn}, PIDv2: {doc.get("pid_v2")}')
                ArticleEvent.create(
                    user=user,
                    event_type=ARTICLE_EVENT_TYPE_MULTIPLE_OBJS_RETURNED,
                    message=f'Error creating Article: {e}. Collection: {col_obj}, Journal: {journal.scielo_issn}, PIDv2: {doc.get("pid_v2")}',
                    data=doc
                )
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

                try:
                    article.save()
                    logging.debug(f'Article {"created" if created else "updated"}: {article}')            
                except DataError as e:
                    logging.error(f'Error saving Article: {e}. Collection: {col_obj}, Journal: {journal.scielo_issn}, PIDv2: {doc.get("pid_v2")}')
                    ArticleEvent.create(
                        user=user,
                        event_type=ARTICLE_EVENT_TYPE_DATA_ERROR,
                        message=f'Error saving Article: {e}. Collection: {col_obj}, Journal: {journal.scielo_issn}, PIDv2: {doc.get("pid_v2")}',
                        data=doc
                    )
                    continue

        page += 1
        if page > int(response.get('pages', 0)):
            break

    return True


@celery_app.task(bind=True, name=_('Load preprint data from SciELO Preprints'), timelimit=-1)
def task_load_preprints_from_preprints_api(self, from_date=None, until_date=None, days_to_go_back=None, force_update=True, user_id=None, username=None):
    user = _get_user(self.request, username=username, user_id=user_id)

    from_date, until_date = date_utils.get_date_range_str(from_date, until_date, days_to_go_back)
    logging.info(f'Loading preprints from SciELO Preprints. From: {from_date}, Until: {until_date}')

    col_obj = Collection.objects.get(acron3='preprints')
    if not col_obj:
        logging.error(f'Collection not found: preprints')
        return False

    for record in utils.fetch_preprint_oai_pmh(from_date, until_date):
        data = utils.extract_preprint_data(record)

        if not data.get('pid_generic'):
            logging.error(f'Preprint ID not found in record: {record}')
            continue

        try:
            article, created = models.Article.objects.get_or_create(collection=col_obj, pid_generic=data['pid_generic'])
            if created or force_update:
                article.text_langs = data.get('text_langs')
                article.default_lang = data.get('default_language')
                article.publication_date = data.get('publication_date')
                article.publication_year = data.get('publication_year')
                
                # Preprints do not have a scielo_issn yet
                article.scielo_issn = '0000-0000'

                article.save()
                logging.debug(f'Article {"created" if created else "updated"}: {article}')
        except models.Article.MultipleObjectsReturned as e:
            logging.error(f'Error creating Article: {e}. Collection: {col_obj}, PID: {data["pid_generic"]}')
            ArticleEvent.create(
                user=user,
                event_type=ARTICLE_EVENT_TYPE_MULTIPLE_OBJS_RETURNED,
                message=f'Error creating Article: {e}. Collection: {col_obj}, PID: {data["pid_generic"]}',
                data=data
            )
            continue
        except DataError as e:
            logging.error(f'Error saving Article: {e}. Collection: {col_obj}, PID: {data["pid_generic"]}')
            ArticleEvent.create(
                user=user,
                event_type=ARTICLE_EVENT_TYPE_DATA_ERROR,
                message=f'Error saving Article: {e}. Collection: {col_obj}, PID: {data["pid_generic"]}',
                data=data
            )
            continue


@celery_app.task(bind=True, name=_('Load dataset metadata from Dataverse'), timelimit=-1)
def task_load_dataset_metadata_from_dataverse(self, from_date=None, until_date=None, days_to_go_back=None, force_update=True, user_id=None, username=None):
    user = _get_user(self.request, username=username, user_id=user_id)

    from_date, until_date = date_utils.get_date_range_str(from_date, until_date, days_to_go_back)
    logging.info(f'Loading dataset metadata from SciELO Data. From: {from_date}, Until: {until_date}')

    col_obj = Collection.objects.get(acron3='data')
    if not col_obj:
        logging.error(f'Collection not found: data')
        return False

    for record in utils.fetch_dataverse_metadata(from_date, until_date):
        dataset_doi = record.get('dataset_doi')
        if not dataset_doi:
            logging.error(f'Dataset DOI not found in record: {record}')
            continue

        try:
            dataset, created = models.Article.objects.get_or_create(collection=col_obj, pid_generic=dataset_doi)
            if created or force_update:
                dataset.publication_date = record.get('dataset_published')

                file_persistent_id = record.get('file_persistent_id')
                file_id = record.get('file_id')
                file_name = record.get('file_name')
                file_url = record.get('file_url')

                if file_id:
                    dataset.files[file_id] = {'name': file_name, 'url': file_url, 'file_persisent_id': file_persistent_id}

                dataset.save()
                logging.debug(f'Dataset {"created" if created else "updated"}: {dataset}')
        except models.Article.MultipleObjectsReturned as e:
            logging.error(f'Error creating Dataset: {e}. Collection: {col_obj}, PID: {dataset_doi}')
            ArticleEvent.create(
                user=user,
                event_type=ARTICLE_EVENT_TYPE_MULTIPLE_OBJS_RETURNED,
                message=f'Error creating Dataset: {e}. Collection: {col_obj}, PID: {dataset_doi}',
                data=record
            )
            continue
        except DataError as e:
            logging.error(f'Error saving Dataset: {e}. Collection: {col_obj}, PID: {dataset_doi}')
            ArticleEvent.create(
                user=user,
                event_type=ARTICLE_EVENT_TYPE_DATA_ERROR,
                message=f'Error saving Dataset: {e}. Collection: {col_obj}, PID: {dataset_doi}',
                data=record
            )
            continue

    return True
