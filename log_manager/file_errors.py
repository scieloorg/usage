import gzip
import hashlib
import zlib

FILE_READ_ERROR_CODE = "file_read_error"
FILE_READ_EXCEPTIONS = (EOFError, OSError, zlib.error)
CATALOG_EMPTY_PREFIX = "catalog-empty"
CATALOG_ERROR_PREFIX = "catalog-error"


def build_file_read_error(exc, stage):
    return {
        "code": FILE_READ_ERROR_CODE,
        "kind": _get_error_kind(exc),
        "stage": stage,
        "exception": exc.__class__.__name__,
        "message": str(exc),
    }


def build_catalog_error_hash(collection_code, path):
    return _build_catalog_path_hash(CATALOG_ERROR_PREFIX, collection_code, path)


def build_catalog_empty_hash(collection_code, path):
    return _build_catalog_path_hash(CATALOG_EMPTY_PREFIX, collection_code, path)


def _build_catalog_path_hash(prefix, collection_code, path):
    identity = f"{prefix}\0{collection_code}\0{path}".encode("utf-8")
    return hashlib.md5(identity).hexdigest()


def _get_error_kind(exc):
    if isinstance(exc, EOFError):
        return "truncated"
    if isinstance(exc, (gzip.BadGzipFile, zlib.error)):
        return "corrupted"
    return "io"
