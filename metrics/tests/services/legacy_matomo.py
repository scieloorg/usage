import gzip
import hashlib
import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from metrics.legacy_matomo.manifest import ARTICLE_METRIC_PROFILE
from metrics.opensearch.keys import document_key, metric_key, source_key

ARTICLE_DIMENSIONS = {
    "metric_scope": "item",
    "data_type": "Article",
    "parent_data_type": "Journal",
    "article_version": None,
    "access_type": "Open",
    "access_method": "Regular",
}
METRICS = {
    "total_requests": 3,
    "total_investigations": 4,
    "unique_requests": 1,
    "unique_investigations": 2,
}


def write_jsonl(path, metric_id, document):
    encoded = (
        json.dumps(
            {"_id": metric_id, "_source": document},
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    with gzip.GzipFile(filename=path, mode="wb", mtime=0) as output:
        output.write(encoded)
    return {
        "path": str(path),
        "documents": 1,
        "totals": METRICS,
        "uncompressed_sha256": hashlib.sha256(encoded).hexdigest(),
    }


class LegacyManifestTestCase(SimpleTestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        source_identifier = source_key("scl", "journal", "0103-2100")
        document_identifier = document_key("scl", "article", "pid")
        counter_document = {
            "collection": "scl",
            "source_key": source_identifier,
            "document_key": document_identifier,
            "month": "2025-08",
            **{
                key: value
                for key, value in ARTICLE_DIMENSIONS.items()
                if value is not None
            },
            **METRICS,
            "daily_metrics": {"01": METRICS},
        }
        counter_id = metric_key(
            collection="scl",
            source_identifier=source_identifier,
            document_identifier=document_identifier,
            period="2025-08",
            **ARTICLE_DIMENSIONS,
        )
        analytics_document = {
            "year": "2025",
            "source_key": source_identifier,
            "document_key": document_identifier,
            **{
                key: value
                for key, value in ARTICLE_DIMENSIONS.items()
                if value is not None
            },
            "country_code": "BR",
            "content_language": "pt",
            **METRICS,
        }
        analytics_id = metric_key(
            collection="scl",
            source_identifier=source_identifier,
            document_identifier=document_identifier,
            period="2025",
            projection="country_language",
            country_code="BR",
            content_language="pt",
            **ARTICLE_DIMENSIONS,
        )
        counter = write_jsonl(root / "counter.jsonl.gz", counter_id, counter_document)
        counter.update({"month": "2025-08", "dataset": "counter"})
        analytics = write_jsonl(
            root / "analytics.jsonl.gz", analytics_id, analytics_document
        )
        analytics.update({"source_month": "2025-08", "dataset": "analytics"})
        self.manifest = {
            "schema_version": 2,
            "migration": "legacy-matomo",
            "metric_profile": ARTICLE_METRIC_PROFILE,
            "source": {"database": "matomo", "collection": "nbr"},
            "month": "2025-08",
            "source_days": ["2025-08-01"],
            "empty_days": [],
            "target": {"collection": "scl"},
            "counter": counter,
            "analytics": analytics,
        }

    def tearDown(self):
        self.temporary_directory.cleanup()
