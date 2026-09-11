import re
from urllib.parse import unquote, urlparse

from core.utils.date_utils import coerce_datetime


def accumulate(results, counter_access, line, reporting_date=None):
    access_url = counter_access.get("access_url") or _normalized_access_path(
        line.get("url")
    )
    counter_access = {**counter_access, "access_url": access_url}

    client_name = line.get("client_name")
    client_version = line.get("client_version")
    local_datetime = coerce_datetime(line.get("local_datetime"))
    ip_address = line.get("ip_address")

    if local_datetime is None:
        raise ValueError("Invalid local_datetime in parsed log line.")

    reporting_date = reporting_date or local_datetime.date()
    access_datetime = local_datetime.replace(minute=0, second=0, microsecond=0)
    second_of_hour = local_datetime.minute * 60 + local_datetime.second

    session_key = (
        client_name,
        client_version,
        ip_address,
        reporting_date.toordinal(),
        access_datetime.hour,
    )
    raw_record = _build_record(
        counter_access=counter_access,
        line=line,
        reporting_date=reporting_date,
    )
    access_url_key = access_url or "|".join(
        [
            str(counter_access.get("pid_generic") or ""),
            str(counter_access.get("media_format") or ""),
            str(counter_access.get("content_type") or ""),
        ]
    )

    results.accumulate_access(
        data=raw_record,
        session_key=session_key,
        url=access_url_key,
        second=second_of_hour,
    )


def _build_record(
    counter_access,
    line,
    reporting_date,
):
    collection = counter_access.get("collection")
    source_key = _source_key(counter_access, collection)
    pid_v2 = counter_access.get("pid_v2")
    pid_v3 = counter_access.get("pid_v3")
    pid_generic = counter_access.get("pid_generic")
    media_format = counter_access.get("media_format")
    content_language = counter_access.get("media_language")
    content_type = counter_access.get("content_type")
    access_country_code = line.get("country_code")
    access_date = reporting_date.strftime("%Y-%m-%d")

    return {
        "collection": collection,
        "source_key": source_key,
        "document_type": counter_access.get("document_type"),
        "pid_v2": pid_v2,
        "pid_v3": pid_v3,
        "pid_generic": pid_generic,
        "title_pid_generic": counter_access.get("title_pid_generic") or pid_generic,
        "media_format": media_format,
        "content_language": content_language,
        "content_type": content_type,
        "access_country_code": access_country_code,
        "access_date": access_date,
        "publication_year": counter_access.get("publication_year"),
        "counter_access_type": counter_access.get("counter_access_type") or "Open",
        "access_method": counter_access.get("access_method") or "Regular",
        "source": _source_metadata(counter_access),
    }


def _normalized_access_path(url):
    if not url:
        return None
    parsed_url = urlparse(str(url).strip())
    path = (
        parsed_url.path if parsed_url.scheme or parsed_url.netloc else str(url).strip()
    )
    path = unquote(path or "")
    path = path.split("?", 1)[0].split("#", 1)[0].split()[0]
    path = re.sub(r"/+", "/", path)
    path = path.rstrip(".,;:")
    return path or None


def _source_metadata(counter_access):
    return {
        "source_type": counter_access.get("source_type"),
        "source_id": counter_access.get("source_id"),
    }


def _source_key(counter_access, fallback):
    return (
        counter_access.get("source_id")
        or counter_access.get("scielo_issn")
        or counter_access.get("source_type")
        or fallback
    )
