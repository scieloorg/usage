import csv
import io
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
