import logging
import requests
import os

from sickle import Sickle
from time import sleep

from core.utils import standardizer


ARTICLEMETA_ENDPOINT = os.environ.get('ARTICLEMETA_COLLECT_URL', 'http://articlemeta.scielo.org/api/v1/article/counter_dict')
ARTICLEMETA_MAX_RETRIES = int(os.environ.get('ARTICLEMETA_MAX_RETRIES', 5))
ARTICLEMETA_SLEEP_TIME = int(os.environ.get('ARTICLEMETA_SLEEP_TIME', 30))

OPAC_ENDPOINT = os.environ.get('OPAC_ENDPOINT', 'https://www.scielo.br/api/v1/counter_dict')
OPAC_MAX_RETRIES = int(os.environ.get('OPAC_MAX_RETRIES', 5))
OPAC_SLEEP_TIME = int(os.environ.get('OPAC_SLEEP_TIME', 30))

OAI_PMH_PREPRINT_ENDPOINT = os.environ.get('OAI_PMH_PREPRINT_ENDPOINT', 'https://preprints.scielo.org/index.php/scielo/oai')
OAI_METADATA_PREFIX = os.environ.get('OAI_METADATA_PREFIX', 'oai_dc')
OAI_PMH_MAX_RETRIES = int(os.environ.get('OAI_PMH_MAX_RETRIES', 5))

DATAVERSE_ENDPOINT = os.environ.get('DATAVERSE_ENDPOINT', 'https://data.scielo.org/api')
DATAVERSE_ROOT_COLLECTION = os.environ.get('DATAVERSE_ROOT_COLLECTION', 'scielodata')
DATAVERSE_MAX_RETRIES = int(os.environ.get('DATAVERSE_MAX_RETRIES', 5))
DATAVERSE_SLEEP_TIME = int(os.environ.get('DATAVERSE_SLEEP_TIME', 30))


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
            logging.info(response.url)

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


def fetch_opac_dict(from_date, until_date, page=1):
    for t in range(1, OPAC_MAX_RETRIES + 1):
        params = {
            'begin_date': from_date, 
            'end_date': until_date, 
            'page': page
        }

        response = requests.get(url=OPAC_ENDPOINT, params=params, verify=False)

        try:
            response.raise_for_status()
            logging.info(response.url)

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


def extract_preprint_data(record):
    pid_generic = _extract_preprint_compatible_identifer(record.header.identifier)
    text_langs = [standardizer.standardize_language_code(l) for l in record.metadata.get('language', [])]
    publication_date = record.metadata.get('date', [''])[0]
    default_language = text_langs[0] if text_langs else ''
    publication_year = _extract_preprint_publication_year_from_date(publication_date)

    data = {
        'pid_generic': pid_generic,
        'text_langs': text_langs,
        'publication_date': publication_date,
        'default_language': default_language,
        'publication_year': publication_year
    }

    return data


def _extract_preprint_compatible_identifer(pid_v2):
    try:
        # piv_v2 should be something like oai:ops.preprints.scielo.org:preprint/1195
        # we are using the last part of the string as the identifier
        return pid_v2.split(':')[-1].split('/')[1]
    except IndexError:
        return ''


def _extract_preprint_publication_year_from_date(date_str):
    try:
        return date_str[:4]
    except IndexError:
        return ''


def fetch_dataverse_metadata(from_date=None, until_date=None):
    def get_subdataverses():
        url = f"{DATAVERSE_ENDPOINT}/dataverses/{DATAVERSE_ROOT_COLLECTION}/contents"
        try:
            response = requests.get(url, timeout=DATAVERSE_SLEEP_TIME)
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching subdataverses: {e}")
            return []

    def get_datasets(subdataverse_id):
        url = f"{DATAVERSE_ENDPOINT}/dataverses/{subdataverse_id}/contents"
        try:
            response = requests.get(url, timeout=DATAVERSE_SLEEP_TIME)
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching datasets for subdataverse {subdataverse_id}: {e}")
            return []

    def get_files(dataset_id):
        url = f"{DATAVERSE_ENDPOINT}/datasets/{dataset_id}/versions/:latest/files"
        try:
            response = requests.get(url, timeout=DATAVERSE_SLEEP_TIME)
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching files for dataset {dataset_id}: {e}")
            return []

    subdataverses = get_subdataverses()

    for subdataverse in subdataverses:
        if subdataverse["type"] != "dataverse":
            continue

        subdataverse_id = subdataverse["id"]
        subdataverse_title = subdataverse["title"]
        datasets = get_datasets(subdataverse_id)

        for dataset in datasets:
            if dataset["type"] != "dataset":
                continue

            dataset_id = dataset["id"]
            doi = standardizer.standardize_doi(dataset.get("persistentUrl"))
            if not doi:
                logging.warning(f"Dataset {dataset_id} does not have a DOI.")
                continue

            publication_date = dataset.get("publicationDate", None)

            if publication_date:
                if (from_date and publication_date < from_date) or (until_date and publication_date > until_date):
                    continue

            files = get_files(dataset_id)

            for file in files:
                file_persistent_id = file["dataFile"].get("persistentId", None)
                file_persistent_id_stz = standardizer.standardize_pid_generic(file_persistent_id) if file_persistent_id else None

                yield {
                    "title": subdataverse_title,
                    "dataset_doi": doi,
                    "dataset_published": publication_date,
                    "file_id": file["dataFile"]["id"],
                    "file_name": file["label"],
                    "file_url": f"{DATAVERSE_ENDPOINT}/access/datafile/{file['dataFile']['id']}",
                    "file_persistent_id": file_persistent_id_stz,
                }
