import re
from urllib.parse import unquote, urlparse

from core.utils.date_utils import coerce_datetime, truncate_datetime_to_hour


def accumulate(results, counter_access, line):
    access_url = counter_access.get("access_url") or _normalized_access_path(
        line.get("url")
    )
    counter_access = {**counter_access, "access_url": access_url}

    client_name = line.get("client_name")
    client_version = line.get("client_version")
    local_datetime = coerce_datetime(line.get("local_datetime"))
    ip_address = line.get("ip_address")

    access_datetime = truncate_datetime_to_hour(local_datetime)
    if access_datetime is None or local_datetime is None:
        raise ValueError("Invalid local_datetime in parsed log line.")
    second_of_hour = local_datetime.minute * 60 + local_datetime.second

    user_session_id = _generate_user_session_id(
        client_name,
        client_version,
        ip_address,
        access_datetime,
    )
    raw_record = _build_record(
        counter_access=counter_access,
        line=line,
        access_datetime=access_datetime,
        second_of_hour=second_of_hour,
        user_session_id=user_session_id,
    )
    item_access_id = raw_record["id"]

    if item_access_id not in results:
        results[item_access_id] = raw_record["data"]

    _increment_timestamp_count(
        results[item_access_id]["click_timestamps"],
        second_of_hour,
    )

    access_url_key = access_url or "|".join(
        [
            str(counter_access.get("pid_generic") or ""),
            str(counter_access.get("media_format") or ""),
            str(counter_access.get("content_type") or ""),
        ]
    )
    timestamps_by_url = results[item_access_id].setdefault(
        "click_timestamps_by_url", {}
    )
    url_timestamps = timestamps_by_url.setdefault(access_url_key, {})
    _increment_timestamp_count(url_timestamps, second_of_hour)


def _build_record(counter_access, line, access_datetime, second_of_hour, user_session_id):
    collection = counter_access.get("collection")
    source_key = _source_key(counter_access, collection)
    pid_v2 = counter_access.get("pid_v2")
    pid_v3 = counter_access.get("pid_v3")
    pid_generic = counter_access.get("pid_generic")
    media_format = counter_access.get("media_format")
    content_language = counter_access.get("media_language")
    content_type = counter_access.get("content_type")
    access_country_code = line.get("country_code")
    access_date = access_datetime.strftime("%Y-%m-%d")

    return {
        "id": _generate_item_access_id(
            user_session_id=user_session_id,
            col_acron3=collection,
            source_key=source_key,
            pid_v2=pid_v2,
            pid_v3=pid_v3,
            pid_generic=pid_generic,
            content_language=content_language,
            access_country_code=access_country_code,
            media_format=media_format,
            content_type=content_type,
        ),
        "data": {
            "collection": collection,
            "source_key": source_key,
            "document_type": counter_access.get("document_type"),
            "pid_v2": pid_v2,
            "pid_v3": pid_v3,
            "pid_generic": pid_generic,
            "document": _document_metadata(counter_access),
            "title_pid_generic": counter_access.get("title_pid_generic") or pid_generic,
            "user_session_id": user_session_id,
            "click_timestamps": {second_of_hour: 0},
            "click_timestamps_by_url": {},
            "access_url": counter_access.get("access_url"),
            "media_format": media_format,
            "content_language": content_language,
            "content_type": content_type,
            "access_country_code": access_country_code,
            "access_date": access_date,
            "access_year": access_date[:4],
            "access_month": access_date[:7].replace("-", ""),
            "publication_year": counter_access.get("publication_year"),
            "counter_access_type": counter_access.get("counter_access_type") or "Open",
            "access_method": counter_access.get("access_method") or "Regular",
            "source": _source_metadata(counter_access),
        },
    }


def _increment_timestamp_count(timestamps, key):
    if key not in timestamps:
        timestamps[key] = 0
    timestamps[key] += 1


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


def _generate_user_session_id(
    client_name, client_version, ip_address, datetime, sep="|"
):
    dt_year_month_day = datetime.strftime("%Y-%m-%d")
    dt_hour = datetime.strftime("%H")

    return sep.join(
        [
            str(client_name),
            str(client_version),
            str(ip_address),
            str(dt_year_month_day),
            str(dt_hour),
        ]
    )


def _document_metadata(counter_access):
    document_title = counter_access.get("document_title")
    return {"title": document_title} if document_title else {}


def _source_metadata(counter_access):
    return {
        "source_type": counter_access.get("source_type"),
        "source_id": counter_access.get("source_id"),
        "scielo_issn": counter_access.get("scielo_issn"),
        "main_title": counter_access.get("source_main_title"),
        "identifiers": counter_access.get("source_identifiers"),
        "access_type": counter_access.get("source_access_type"),
        "city": counter_access.get("source_city"),
        "country": counter_access.get("source_country"),
        "subject_area_capes": counter_access.get("source_subject_area_capes"),
        "subject_area_wos": counter_access.get("source_subject_area_wos"),
        "acronym": counter_access.get("source_acronym"),
        "publisher_name": counter_access.get("source_publisher_name"),
    }


def _source_key(counter_access, fallback):
    return (
        counter_access.get("source_id")
        or counter_access.get("scielo_issn")
        or counter_access.get("source_type")
        or fallback
    )


def _generate_item_access_id(
    col_acron3,
    source_key,
    pid_v2,
    pid_v3,
    pid_generic,
    user_session_id,
    access_country_code,
    content_language,
    media_format,
    content_type,
    sep="|",
):
    return sep.join(
        [
            col_acron3,
            str(source_key or ""),
            pid_v2 or "",
            pid_v3 or "",
            pid_generic or "",
            str(user_session_id or ""),
            str(access_country_code or ""),
            str(content_language or ""),
            str(media_format or ""),
            str(content_type or ""),
        ]
    )
