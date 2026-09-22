from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from counter_api.models import APIKey


class Command(BaseCommand):
    help = "Issue a COUNTER API key and print its value once."

    def add_arguments(self, parser):
        parser.add_argument("name")
        parser.add_argument("--expires-at")

    def handle(self, *args, **options):
        expires_at = None
        if options["expires_at"]:
            expires_at = parse_datetime(options["expires_at"])
            if expires_at is None:
                raise ValueError("expires-at must be an ISO 8601 datetime")
            if timezone.is_naive(expires_at):
                expires_at = timezone.make_aware(expires_at)

        key, value = APIKey.issue(options["name"], expires_at=expires_at)
        self.stdout.write(f"id={key.pk}")
        self.stdout.write(f"api_key={value}")
