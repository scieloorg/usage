import csv
import io
import langcodes
import tarfile


def get_load_data_function(file_path):
    """
    Determines the appropriate data loading function based on the file extension.

    Parameters:
    file_path (str): The path to the file.

    Returns:
    function: The corresponding function to load data from the file.
    """
    if file_path.lower().endswith('.csv'):
        return load_csv
    
    if file_path.lower().endswith('.tar.gz') or ('.tar' in file_path.lower() and file_path.lower().endswith('.gz')):
        return load_tar_gz


def load_csv(file_obj, delimiter='\t', is_stream=False):
    """
    Loads and processes a CSV file, yielding each row as a dictionary.

    Parameters:
    file_obj (str or io.StringIO): The path to the file or a file-like object.
    delimiter (str): The delimiter used in the CSV file. Default is tab ('\t').
    is_stream (bool): Indicates whether file_obj is a file-like object (stream). Default is False.

    Yields:
    dict: Each row of the CSV file as a dictionary.
    """
    if is_stream:
        file_obj = io.StringIO(file_obj.decode('utf-8'))

    with file_obj if is_stream else open(file_obj) as fin:
        first_line = fin.readline().strip()
        if not first_line:
            return
        
        header = first_line.split(delimiter)
        reader = csv.DictReader(
            fin, 
            fieldnames=header,
            delimiter=delimiter,
        )
        for row in reader:
            yield row


def load_tar_gz(file_path, delimiter='\t'):
    """
    Loads and processes CSV files from within a tar.gz archive, yielding each row as a dictionary.

    Parameters:
    file_path (str): The path to the tar.gz file.
    delimiter (str): The delimiter used in the CSV file. Default is tab ('\t').

    Yields:
    dict: Each row of each CSV file within the tar.gz archive as a dictionary.
    """
    with tarfile.open(file_path, 'r:gz') as tar:
        for member in tar.getmembers():
            if member.isfile() and member.name.lower().endswith('.csv'):
                file_content = tar.extractfile(member).read()
                yield from load_csv(
                    file_content, 
                    delimiter=delimiter, 
                    is_stream=True
                )


def standardize_media_language(media_language: str, threshold=0.75):
    """
    Standardizes a media language using langcodes library.

    Parameters:
    media_language (str): The media language to be standardized.
    threshold (float): The minimum score for a language to be considered valid. Default is 0.75.

    Returns:
    str: The standardized media language or None if the input is not a valid language tag.
    """
    if not media_language:
        return 'un'
    
    if langcodes.tag_is_valid(media_language):
        return langcodes.standardize_tag(media_language).split('-')[0]
    
    # Handle special cases
    if media_language.lower() == 'esp':
        return 'es'

    inferred_lang, score = langcodes.best_match(media_language, langcodes.LANGUAGE_ALPHA3.keys())

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
