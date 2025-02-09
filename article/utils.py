import logging
import requests
import os

from sickle import Sickle
from time import sleep


ARTICLEMETA_ENDPOINT = os.environ.get('ARTICLEMETA_COLLECT_URL', 'http://articlemeta.scielo.org/api/v1/article/counter_dict')
ARTICLEMETA_MAX_RETRIES = int(os.environ.get('ARTICLEMETA_COLLECT_MAX_RETRIES', 5))
ARTICLEMETA_SLEEP_TIME = int(os.environ.get('ARTICLEMETA_COLLECT_URL_SLEEP_TIME', 30))

OPAC_ENDPOINT = os.environ.get('OPAC_ENDPOINT', 'https://www.scielo.br/api/v1/counter_dict')
OPAC_MAX_RETRIES = int(os.environ.get('OPAC_COLLECT_MAX_RETRIES', 5))
OPAC_SLEEP_TIME = int(os.environ.get('OPAC_COLLECT_URL_SLEEP_TIME', 30))

OAI_PMH_PREPRINT_ENDPOINT = os.environ.get('OAI_PMH_PREPRINT_ENDPOINT', 'https://preprints.scielo.org/index.php/scielo/oai')
OAI_METADATA_PREFIX = os.environ.get('OAI_METADATA_PREFIX', 'oai_dc')
OAI_PMH_MAX_RETRIES = int(os.environ.get('OAI_PMH_MAX_RETRIES', 5))


def fetch_article_meta_dict(from_date, until_date, offset=0, limit=1000, collection=None, issn=None):
    for t in range(1, ARTICLEMETA_MAX_RETRIES + 1):
        params = {
            'from': from_date,
            'until': until_date,
            'offset': offset,
            'limit': limit
        }

        if collection:
            params['collection'] = collection

        if issn:
            params['issn'] = issn

        response = requests.get(ARTICLEMETA_ENDPOINT, params=params)

        try:
            response.raise_for_status()
            logging.debug(response.url)

        except requests.exceptions.HTTPError:
            logging.warning(
                'Failed to collect data from %s. Waiting %d seconds before retry %d of %d' % (
                    response.url, 
                    ARTICLEMETA_SLEEP_TIME, 
                    t, 
                    ARTICLEMETA_MAX_RETRIES
                )
            )
            sleep(ARTICLEMETA_SLEEP_TIME)

        else:
            return response.json()


def fetch_opac_dict(begin_date, end_date, page=1):
    for t in range(1, OPAC_MAX_RETRIES + 1):
        params = {
            'begin': begin_date, 
            'end': end_date, 
            'page': page
        }

        response = requests.get(url=OPAC_ENDPOINT, params=params, verify=False)

        try:
            response.raise_for_status()
            logging.debug(response.url)

        except requests.exceptions.HTTPError:
            logging.warning('Não foi possível coletar dados de %s. Aguardando %d segundos para tentativa %d de %d' % (response.url, OPAC_SLEEP_TIME, t, OPAC_MAX_RETRIES))
            sleep(OPAC_SLEEP_TIME)

        else:
            return response.json()


def fetch_preprint_oai_pmh(from_date, until_date):
    oai_client = Sickle(endpoint=OAI_PMH_PREPRINT_ENDPOINT, max_retries=OAI_PMH_MAX_RETRIES, verify=False)
    records = oai_client.ListRecords(**{
        'metadataPrefix': OAI_METADATA_PREFIX,
        'from': from_date,
        'until': until_date,
    })

    for r in records:
        yield r
