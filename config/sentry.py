from urllib.parse import parse_qsl, urlsplit, urlunsplit


def scrub_api_key(event, _hint):
    request = event.get("request") or {}
    query_string = request.get("query_string") or ""
    url = request.get("url") or ""
    url_query = urlsplit(url).query if url else ""

    if not _contains_api_key(query_string) and not _contains_api_key(url_query):
        return event

    request["query_string"] = ""
    if url:
        parts = urlsplit(url)
        request["url"] = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    return event


def _contains_api_key(query_string):
    if not isinstance(query_string, str):
        return False

    return any(
        name.lower() == "api_key"
        for name, _value in parse_qsl(query_string, keep_blank_values=True)
    )
