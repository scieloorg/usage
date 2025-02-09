import hashlib

from scielo_log_validator import validator


def hash_file(path, num_lines=25):
    """
    Calculates the MD5 hash of a file using a combination of its first and last `num_lines` lines, 
    as well as its size.
    
    Args:
        path (str): The path to the file.
        num_lines (int): The number of lines to consider from the beginning and end of the file. Default is 25.

    Returns:
        The MD5 hash digest as a hexadecimal string.
    """
    md5_hash = hashlib.md5()

    with open(path, 'rb') as file:
        # Read the first `num_lines` lines of the file
        first_lines = b''.join([file.readline() for _ in range(num_lines)])
        md5_hash.update(first_lines)

        # Move the file pointer to the end of the file
        file.seek(0, 2)

        # Get the size of the file
        size = file.tell()
        md5_hash.update(str(size).encode())

        # Move the file pointer to the start of the file
        file.seek(-size, 2)

        # Read the last `num_lines` lines of the file
        last_lines = file.readlines()[-num_lines:]
        md5_hash.update(b''.join(last_lines))

    return md5_hash.hexdigest()

def validate_file(path, sample_size=0.05, buffer_size=2048, days_delta=5, apply_path_validation=True, apply_content_validation=True):
    return validator.pipeline_validate(
        path=path, 
        sample_size=sample_size,
        buffer_size=buffer_size,
        days_delta=days_delta,
        apply_path_validation=apply_path_validation,
        apply_content_validation=apply_content_validation,
    )
