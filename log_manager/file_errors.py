import gzip
import hashlib
import zlib


FILE_READ_ERROR_CODE = "file_read_error"
FILE_READ_EXCEPTIONS = (EOFError, OSError, zlib.error)


def build_file_read_error(exc, stage):
    return {
        "code": FILE_READ_ERROR_CODE,
        "kind": _get_error_kind(exc),
        "stage": stage,
        "exception": exc.__class__.__name__,
        "message": str(exc),
    }


def build_catalog_error_hash(collection_code, path):
    identity = f"catalog-error\0{collection_code}\0{path}".encode("utf-8")
    return hashlib.md5(identity).hexdigest()


def get_file_read_error(validation):
    file_error = (validation or {}).get("file_error") or {}
    if file_error.get("code") == FILE_READ_ERROR_CODE:
        return file_error
    return None


def _get_error_kind(exc):
    if isinstance(exc, EOFError):
        return "truncated"
    if isinstance(exc, (gzip.BadGzipFile, zlib.error)):
        return "corrupted"
    return "io"
