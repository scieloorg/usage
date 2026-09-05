import logging

import requests
from django.conf import settings

from core.utils import standardizer


def _request_json(url):
    try:
        response = requests.get(url, timeout=settings.DATAVERSE_SLEEP_TIME)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        logging.error("Error fetching %s: %s", url, exc)
        return {}


def _get_dataverse_contents(dataverse_id):
    url = f"{settings.DATAVERSE_ENDPOINT}/dataverses/{dataverse_id}/contents"
    return _request_json(url).get("data", [])


def _get_files(dataset_id):
    url = f"{settings.DATAVERSE_ENDPOINT}/datasets/{dataset_id}/versions/:latest/files"
    return _request_json(url).get("data", [])


def iter_dataset_metadata(from_date=None, until_date=None):
    yield from _iter_dataverse_contents(
        settings.DATAVERSE_ROOT_COLLECTION,
        settings.DATAVERSE_ROOT_COLLECTION,
        from_date,
        until_date,
    )


def _iter_dataverse_contents(
    dataverse_id,
    dataverse_title,
    from_date=None,
    until_date=None,
):
    for item in _get_dataverse_contents(dataverse_id):
        item_type = item.get("type")

        if item_type == "dataverse":
            yield from _iter_dataverse_contents(
                item["id"],
                item["title"],
                from_date,
                until_date,
            )
            continue

        if item_type != "dataset":
            continue

        yield from _iter_dataset_files(
            item,
            dataverse_title,
            from_date,
            until_date,
        )


def _iter_dataset_files(dataset, dataverse_title, from_date=None, until_date=None):
    dataset_id = dataset["id"]
    doi = standardizer.standardize_doi(dataset.get("persistentUrl"))
    if not doi:
        logging.warning("Dataset %s does not have a DOI.", dataset_id)
        return

    publication_date = dataset.get("publicationDate")
    if publication_date:
        if (from_date and publication_date < from_date) or (
            until_date and publication_date > until_date
        ):
            return

    for file_data in _get_files(dataset_id):
        file_persistent_id = file_data["dataFile"].get("persistentId")
        standardized_persistent_id = (
            standardizer.standardize_pid_generic(file_persistent_id)
            if file_persistent_id
            else None
        )

        yield {
            "title": dataverse_title,
            "dataset_doi": doi,
            "dataset_published": publication_date,
            "file_id": file_data["dataFile"]["id"],
            "file_name": file_data["label"],
            "file_url": f"{settings.DATAVERSE_ENDPOINT}/access/datafile/{file_data['dataFile']['id']}",
            "file_persistent_id": standardized_persistent_id,
        }
