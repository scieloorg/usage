import logging

from scielo_usage_counter.translator.classic import URLTranslatorClassicSite
from scielo_usage_counter.translator.dataverse import URLTranslatorDataverseSite
from scielo_usage_counter.translator.opac import URLTranslatorOPACSite
from scielo_usage_counter.translator.opac_alpha import URLTranslatorOPACAlphaSite
from scielo_usage_counter.translator.preprints import URLTranslatorPreprintsSite

from core.utils.date_utils import get_date_obj


def extract_date_from_validation_dict(validation):
    """
    Extracts the date from the validation dict of a log file.

    Args:
        validation (dict): The validation dict of the log file.

    Returns:
        datetime.date: The extracted date.
    """
    try:
        date_str = validation.get('probably_date')
        return get_date_obj(date_str, '%Y-%m-%d')
    except Exception as e:
        logging.error(f"Failed to extract date from validation: {e}")
        return None


def translator_class_name_to_obj(name: str):
    """
    Translates a class name to a class object."

    Parameters:
        name (str): The name of the URL translator site.
    """
    if not name or not isinstance(name, str):
        return None
    
    translator_classes = {
        'classic': URLTranslatorClassicSite,
        'dataverse': URLTranslatorDataverseSite,
        'opac': URLTranslatorOPACSite,
        'opac_alpha': URLTranslatorOPACAlphaSite,
        'preprints': URLTranslatorPreprintsSite
    }
    return translator_classes.get(name.lower())
