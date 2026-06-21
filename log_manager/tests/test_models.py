from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase

from collection.models import Collection
from log_manager import choices
from log_manager.models import LogFile


class LogFileModelTests(TestCase):
    def setUp(self):
        self.collection = Collection.objects.create(acron3="books", acron2="bk")

    def test_create_or_update_creates_log_file(self):
        log_file = LogFile.create_or_update(
            collection=self.collection,
            path="/tmp/new.log.gz",
            stat_result={"size": 10},
            hash="1" * 32,
        )

        self.assertEqual(log_file.collection, self.collection)
        self.assertEqual(log_file.path, "/tmp/new.log.gz")
        self.assertEqual(log_file.status, choices.LOG_FILE_STATUS_CREATED)

    def test_create_or_update_refetches_existing_after_integrity_error(self):
        existing = LogFile.objects.create(
            collection=self.collection,
            path="/tmp/existing.log.gz",
            stat_result={"size": 10},
            hash="1" * 32,
            status=choices.LOG_FILE_STATUS_CREATED,
        )

        with patch.object(LogFile.objects, "get_or_create", side_effect=IntegrityError):
            log_file = LogFile.create_or_update(
                collection=self.collection,
                path="/tmp/existing.log.gz",
                stat_result={"size": 10},
                hash=existing.hash,
            )

        self.assertEqual(log_file.pk, existing.pk)
