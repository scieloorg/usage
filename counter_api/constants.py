RELEASE = "5.1"
PROPRIETARY_NAMESPACE = "SciELO"
COMPOSITE_PAGE_SIZE = 1000
METADATA_BATCH_SIZE = 1000
EXCEL_MAX_ROWS = 1048576
SPOOL_SIZE = 8 * 1024 * 1024
METRICS = {
    "Total_Item_Investigations": "total_investigations",
    "Unique_Item_Investigations": "unique_investigations",
    "Total_Item_Requests": "total_requests",
    "Unique_Item_Requests": "unique_requests",
}
TITLE_METRICS = {
    "Unique_Title_Investigations": "unique_investigations",
    "Unique_Title_Requests": "unique_requests",
}
STANDARD_VIEWS = {
    "tr_j3": {
        "filters": {
            "Data_Type": ["Journal"],
            "Access_Method": ["Regular"],
            "Metric_Type": list(METRICS),
        },
        "attributes": ["Access_Type"],
    },
    "tr_b3": {
        "filters": {
            "Data_Type": ["Book", "Reference_Work"],
            "Access_Method": ["Regular"],
            "Metric_Type": [*METRICS, *TITLE_METRICS],
        },
        "attributes": ["Data_Type", "YOP", "Access_Type"],
    },
}
HOST_TYPES = {
    "journals": "eJournal",
    "books": "eBook",
    "preprints": "Repository",
    "repositories": "Repository",
    "data": "Data_Repository",
}
REPORTS = {
    "pr": {
        "name": "Platform Report",
        "collections": tuple(HOST_TYPES),
    },
    "tr": {
        "name": "Title Report",
        "collections": ("journals", "books"),
    },
    "tr_j3": {
        "name": "Journal Usage by Access Type",
        "collections": ("journals",),
    },
    "tr_b3": {
        "name": "Book Usage by Access Type",
        "collections": ("books",),
    },
    "ir": {
        "name": "Item Report",
        "collections": tuple(HOST_TYPES),
    },
}
