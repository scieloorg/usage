from datetime import date
from itertools import islice

from django.conf import settings
from django.core.management.base import BaseCommand
from opensearchpy import helpers

from collection.models import Collection
from metrics.opensearch.client import OpenSearchUsageClient
from metrics.opensearch.names import generate_metadata_alias, generate_month_index_name

DEFAULT_BATCH_SIZE = 500
MAX_PUBLICATION_YEAR = 9999


class Command(BaseCommand):
    help = "Add the YOP mapping and backfill monthly COUNTER facts."

    def add_arguments(self, parser):
        parser.add_argument("--collection", required=True)
        parser.add_argument("--start-month", required=True)
        parser.add_argument("--end-month", required=True)
        parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        collection = Collection.objects.get(acron3=options["collection"])
        batch_size = options["batch_size"]
        if batch_size <= 0:
            raise ValueError("batch-size must be greater than zero")

        try:
            start_month = date.fromisoformat(f"{options['start_month']}-01")
            end_month = date.fromisoformat(f"{options['end_month']}-01")
        except ValueError:
            raise ValueError("months must use YYYY-MM")

        if start_month > end_month:
            raise ValueError("start-month must not be later than end-month")

        client = OpenSearchUsageClient().client
        facts_alias = generate_month_index_name(
            settings.OPENSEARCH_INDEX_NAME,
            collection.acron3,
        )
        documents_alias = generate_metadata_alias(
            settings.OPENSEARCH_INDEX_NAME,
            "documents",
        )

        if not options["dry_run"]:
            indexes = client.indices.get_alias(name=facts_alias)
            for index_name in indexes:
                client.indices.put_mapping(
                    index=index_name,
                    body={"properties": {"publication_year": {"type": "integer"}}},
                )

        query = {
            "query": {
                "range": {
                    "month": {
                        "gte": options["start_month"],
                        "lte": options["end_month"],
                    }
                }
            },
            "_source": ["document_key", "publication_year"],
        }
        hits = helpers.scan(client, index=facts_alias, query=query)
        totals = {
            "updated": 0,
            "correct": 0,
            "missing_metadata": 0,
            "invalid_yop": 0,
        }

        while True:
            batch = list(islice(hits, batch_size))
            if not batch:
                break

            keys = sorted(
                {
                    hit["_source"].get("document_key")
                    for hit in batch
                    if hit["_source"].get("document_key")
                }
            )
            metadata = client.mget(index=documents_alias, body={"ids": keys})
            years = {
                document["_id"]: document["_source"].get("publication_year")
                for document in metadata.get("docs", [])
                if document.get("found")
            }

            actions = []

            for hit in batch:
                document_key = hit["_source"].get("document_key")
                if document_key not in years:
                    totals["missing_metadata"] += 1
                    continue

                year = years[document_key]
                if not isinstance(year, int) or year < 1 or year > MAX_PUBLICATION_YEAR:
                    totals["invalid_yop"] += 1
                    year = 1

                if hit["_source"].get("publication_year") == year:
                    totals["correct"] += 1
                    continue

                actions.append(
                    {
                        "_op_type": "update",
                        "_index": hit["_index"],
                        "_id": hit["_id"],
                        "doc": {"publication_year": year},
                    }
                )

            totals["updated"] += len(actions)
            if actions and not options["dry_run"]:
                helpers.bulk(client, actions, chunk_size=batch_size)

        self.stdout.write(" ".join(f"{name}={value}" for name, value in totals.items()))
