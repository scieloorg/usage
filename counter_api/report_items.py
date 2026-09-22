from time import monotonic

from counter_api.exceptions import service_unavailable
from counter_api.report_entries import build_entries


def build_report_items(report_id, platform, begin, records, params, deadline=None):
    entries, exceptions = build_entries(
        report_id,
        platform,
        records,
        params,
        deadline,
    )
    items = _serialize_entries(
        report_id,
        entries,
        begin,
        params,
        deadline,
    )

    return items, exceptions


def iter_report_items(items):
    for item in items:
        if "Items" in item:
            for nested in item["Items"]:
                yield item, nested
        else:
            yield {}, item


def _serialize_entries(report_id, entries, begin, params, deadline):
    grouped = {}

    for entry in entries:
        if deadline and monotonic() >= deadline:
            raise service_unavailable()

        identifiers = entry["source_ids"] or entry["item_ids"]
        item_key = (
            entry["name"],
            entry["publisher"],
            entry["platform"],
            identifiers,
        )
        if report_id.startswith("tr"):
            item_key += (entry["source_key"],)
        if report_id == "ir":
            item_key += (entry["document_key"],)
            if params.get("Include_Parent_Details"):
                item_key += (entry["source_key"],)

        item = grouped.setdefault(
            item_key,
            {
                "name": entry["name"],
                "publisher": entry["publisher"],
                "platform": entry["platform"],
                "identifiers": identifiers,
                "source_key": entry.get("source_key", ""),
                "parent_data_type": entry.get("parent_data_type", ""),
                "parent_title": entry.get("parent_title", ""),
                "parent_ids": entry.get("parent_ids", ()),
                "attributes": {},
            },
        )

        attribute_key = (
            entry["data_type"],
            entry["yop"],
            entry["access_type"],
            entry["access_method"],
        )
        attributes = item["attributes"].setdefault(attribute_key, {})
        performance = attributes.setdefault(entry["metric_type"], {})
        monthly = entry["performance"]

        if params.get("Granularity") == "Totals":
            performance[begin.strftime("%Y-%m")] = sum(monthly.values())
        else:
            performance.update(monthly)

    items = []
    parents = {}
    parentless = []

    for item in grouped.values():
        if deadline and monotonic() >= deadline:
            raise service_unavailable()

        report_item = {
            _name_field(report_id): item["name"],
            "Platform": item["platform"],
            "Attribute_Performance": [],
        }
        if report_id != "pr":
            report_item["Publisher"] = item["publisher"]
        if item["identifiers"]:
            report_item["Item_ID"] = dict(item["identifiers"])

        for attribute_key, performance in item["attributes"].items():
            data_type, yop, access_type, access_method = attribute_key
            attribute_performance = {"Performance": performance}

            if data_type:
                attribute_performance["Data_Type"] = data_type
            if yop:
                attribute_performance["YOP"] = yop
            if access_type:
                attribute_performance["Access_Type"] = access_type
            if access_method:
                attribute_performance["Access_Method"] = access_method

            report_item["Attribute_Performance"].append(attribute_performance)

        if report_id == "ir" and params.get("Include_Parent_Details"):
            if item["source_key"] and item["parent_data_type"]:
                parent = parents.setdefault(
                    item["source_key"],
                    {
                        "Title": item["parent_title"],
                        "Data_Type": item["parent_data_type"],
                        "Item_ID": dict(item["parent_ids"]),
                        "Items": [],
                    },
                )
                parent["Items"].append(report_item)
            else:
                parentless.append(report_item)
        else:
            items.append(report_item)

    if report_id == "ir" and params.get("Include_Parent_Details"):
        items = list(parents.values())
        if parentless:
            items.append({"Items": parentless})

    if report_id == "ir":
        if items and not params.get("Include_Parent_Details"):
            items = [{"Items": sorted(items, key=lambda item: item["Item"])}]

        return sorted(items, key=lambda item: item.get("Title", ""))

    return sorted(items, key=lambda item: item[_name_field(report_id)])


def _name_field(report_id):
    if report_id == "pr":
        return "Platform"
    if report_id == "ir":
        return "Item"

    return "Title"
