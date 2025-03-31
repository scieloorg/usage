import langcodes
import re


ITEMS_SEP_FOR_LOCATION = [";", ", ", "|", "/"]
PARTS_SEP_FOR_LOCATION = [" - ", "- ", " -", ", ", "(", "/"]

ITEMS_SEP_FOR_CITY = [",", "|"]
PARTS_SEP_FOR_CITY = []


def remove_extra_spaces(text):
    text = text and text.strip()
    if not text:
        return text
    # padroniza a quantidade de espaços
    return " ".join([item.strip() for item in text.split() if item.strip()])


def standardize_code_and_name(original):
    """
    Dado o texto original, identifica pares de code e nome.
    Os separadores podem separar code e nome e/ou itens de lista.
    Ex.: USP / Unicamp
    São Paulo/SP, Rio de Janeiro/RJ
    """
    text_ = original
    text_ = text_ and text_.strip()
    if not text_:
        return []

    text_ = remove_extra_spaces(text_)
    if not text_:
        yield {"name": None}
        return

    items_separators = ITEMS_SEP_FOR_LOCATION
    parts_separators = PARTS_SEP_FOR_LOCATION

    PARTBR = "~PARTBR~"
    LINEBR = "~LINEBR~"
    for sep in items_separators:
        text_ = text_.replace(sep, PARTBR)
    for sep in parts_separators:
        text_ = text_.replace(sep, PARTBR)

    codes = []
    names = []
    for item in text_.split(PARTBR):
        item = item.strip()
        if not item:
            continue
        if len(item) == 2:
            codes.append(item)
        else:
            names.append(item)

    if len(names) == len(codes):
        for acron, name in zip(codes, names):
            yield {"code": acron, "name": name}
    elif len(names) == 0:
        for acron in codes:
            yield {"code": acron}
    elif len(codes) == 0:
        for name in names:
            yield {"name": name}
    else:
        # como o texto está bem fora do padrão,
        # pode-se evidenciar retornando o original
        yield {"name": original}


def standardize_name(original):
    original = original and original.strip()
    if not original:
        return

    items_separators = ITEMS_SEP_FOR_CITY

    LINEBR = "~LINEBR~"

    text_ = original
    text_ = remove_extra_spaces(text_)

    for sep in items_separators:
        text_ = text_.replace(sep, LINEBR)

    for row in text_.split(LINEBR):
        row = row and row.strip()
        if not row:
            continue
        yield {"name": row}


def standardize_language_code(language_code: str, threshold=0.75):
    """
    Standardizes a media language using langcodes library.

    Parameters:
    media_language (str): The media language to be standardized.
    threshold (float): The minimum score for a language to be considered valid. Default is 0.75.

    Returns:
    str: The standardized media language or None if the input is not a valid language tag.
    """
    if not language_code:
        return 'un'
    
    if langcodes.tag_is_valid(language_code):
        return langcodes.standardize_tag(language_code).split('-')[0]
    
    # Handle special cases
    if language_code.lower() == 'esp':
        return 'es'

    inferred_lang, score = langcodes.best_match(language_code, langcodes.LANGUAGE_ALPHA3.keys())

    if score >= threshold:
        return langcodes.standardize_tag(inferred_lang).split('-')[0]

    # Handle unknown languages
    return 'un'


def standardize_pid_v2(pid_v2):
    """
    Standardizes a PID v2.

    Parameters:
    pid_v2 (str): The PID v2 to be standardized.

    Returns:
    str: The standardized PID v2 or an empty string if the input is not a valid PID v2.
    """
    if not pid_v2 or not pid_v2.lower().startswith('s') or len(pid_v2) < 23:
        return ''
    
    if len(pid_v2) == 23:
        return pid_v2[0].upper() + pid_v2[1:]
    
    if len(pid_v2) > 23:
        return pid_v2[0].upper() + pid_v2[1:23]
    
    if len(pid_v2) < 23:
        return ''


def standardize_pid_v3(pid_v3):
    """
    Standardizes a PID v3 using langcodes library."

    Parameters:
    pid_v3 (str): The PID v3 to be standardized.

    Returns:
    str: The standardized PID v3 or an empty string if the input is not a valid PID v3.
    """

    if not pid_v3:
        return ''

    if len(pid_v3) == 23:
        return pid_v3
    
    if len(pid_v3) > 23:
        return pid_v3[:23]
    
    if len(pid_v3) < 23:
        return ''


def standardize_doi(text):
    """"
    Standardizes a DOI.
    
    Parameters:
    text (str): The DOI to be standardized.

    Returns:
    str: The standardized DOI
    """
    PATTERNS_DOI = [re.compile(pd) for pd in [
        r'10.\d{4,9}/[-._;()/:A-Z0-9]+$',
        r'10.1002/[^\s]+$',
        r'10.\d{4}/\d+-\d+X?(\d+)\d+<[\d\w]+:[\d\w]*>\d+.\d+.\w+;\d$',
        r'10.1207/[\w\d]+\&\d+_\d+$',
        r'10.\d{4,9}/[-._;()/:a-zA-Z0-9]*']
    ]
    matched_doi = False

    for pattern_doi in PATTERNS_DOI:
        matched_doi = pattern_doi.search(text)
        if matched_doi:
            break

    if not matched_doi:
        return  
    
    return matched_doi.group()
