from django.core.management.base import BaseCommand

from metrics.services.metadata_sync import DEFAULT_BATCH_SIZE, sync_metadata


class Command(BaseCommand):
    help = "Sync COUNTER source and document metadata to OpenSearch."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
        parser.add_argument("--full", action="store_true")

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if batch_size <= 0:
            raise ValueError("batch-size must be greater than zero")

        result = sync_metadata(batch_size=batch_size, full=options["full"])

        self.stdout.write(" ".join(f"{name}={value}" for name, value in result.items()))
