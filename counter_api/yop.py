def valid_yop(value):
    if len(value) == 4 and value.isdigit():
        return 1 <= int(value) <= 9999

    if (
        len(value) != 9
        or value[4] != "-"
        or not value[:4].isdigit()
        or not value[5:].isdigit()
    ):
        return False

    start = int(value[:4])
    end = int(value[5:])

    return 1 <= start <= end <= 9999


def yop_filter(values):
    if not values or any(not valid_yop(value) for value in values):
        return None

    years = []
    for value in values:
        if "-" not in value:
            years.append({"term": {"publication_year": int(value)}})
            continue

        years.append(
            {
                "range": {
                    "publication_year": {
                        "gte": int(value[:4]),
                        "lte": int(value[5:]),
                    }
                }
            }
        )

    if any(value.startswith("0001") for value in values):
        years.append({"bool": {"must_not": {"exists": {"field": "publication_year"}}}})

    return {"bool": {"should": years, "minimum_should_match": 1}}


def matches_yop(publication_year, values):
    try:
        year = int(publication_year)
    except (TypeError, ValueError):
        year = 1

    if year < 1 or year > 9999:
        year = 1

    for value in values:
        if "-" not in value and year == int(value):
            return True
        if "-" in value and int(value[:4]) <= year <= int(value[5:]):
            return True

    return False
