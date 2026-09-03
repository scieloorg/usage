import logging
from time import sleep

import requests
from django.conf import settings


def fetch_counter_dict(from_date, until_date, page=1, *, endpoint):
    for attempt in range(1, settings.OPAC_MAX_RETRIES + 1):
        params = {
            "begin_date": from_date,
            "end_date": until_date,
            "page": page,
        }

        response = requests.get(url=endpoint, params=params, verify=False)

        try:
            response.raise_for_status()
            logging.info(response.url)
        except requests.exceptions.HTTPError:
            logging.warning(
                "Could not collect data from %s. Waiting %d seconds for attempt %d of %d",
                response.url,
                settings.OPAC_SLEEP_TIME,
                attempt,
                settings.OPAC_MAX_RETRIES,
            )
            sleep(settings.OPAC_SLEEP_TIME)
        else:
            return response.json()

    return {}
