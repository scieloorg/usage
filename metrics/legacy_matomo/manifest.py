import json
from datetime import date

ARTICLE_METRIC_PROFILE = "article-usage-v1"
DEFAULT_HISTORICAL_CUTOFF = date(2025, 12, 31)
HISTORICAL_CUTOFFS = {
    "scl": date(2026, 6, 30),
}
MANIFEST_SCHEMA_VERSION = 2
MIGRATION_NAME = "legacy-matomo"
SOURCE_COLLECTION_ALIASES = {
    ("nbr", "scl"),
}
UNSUPPORTED_COLLECTIONS = {"books", "data"}


def load_manifest(path):
    with open(path, encoding="utf-8") as source:
        return json.load(source)


def build_migration_id(manifest, dataset):
    file_hash = manifest[dataset]["uncompressed_sha256"]
    return "%s:v%d:%s:%s:%s:%s" % (
        MIGRATION_NAME,
        MANIFEST_SCHEMA_VERSION,
        manifest["target"]["collection"],
        manifest["month"],
        dataset,
        file_hash,
    )


def validate_migration_scope(manifest):
    if manifest.get("metric_profile") != ARTICLE_METRIC_PROFILE:
        raise ValueError("Unsupported migration metric profile.")

    source_collection = manifest["source"]["collection"]
    target_collection = manifest["target"]["collection"]
    if target_collection in UNSUPPORTED_COLLECTIONS:
        raise ValueError(
            "Collection %s is not supported by the article migration."
            % target_collection
        )
    if (
        source_collection != target_collection
        and (source_collection, target_collection) not in SOURCE_COLLECTION_ALIASES
    ):
        raise ValueError(
            "Unsupported source-to-target collection mapping: %s -> %s."
            % (source_collection, target_collection)
        )

    historical_cutoff = HISTORICAL_CUTOFFS.get(
        target_collection,
        DEFAULT_HISTORICAL_CUTOFF,
    )
    invalid = [
        value
        for value in manifest["source_days"]
        if date.fromisoformat(value) > historical_cutoff
    ]
    if invalid:
        raise ValueError(
            "Historical import for %s is limited to %s; found %s."
            % (target_collection, historical_cutoff.isoformat(), invalid[0])
        )
