from datetime import date
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

    def test_parsing_candidates_exclude_file_read_errors(self):
        read_error = LogFile.objects.create(
            collection=self.collection,
            path="/tmp/read-error.log.gz",
            stat_result={},
            hash="2" * 32,
            status=choices.LOG_FILE_STATUS_ERROR,
            date=date(2026, 9, 4),
            validation={
                "file_error": {
                    "code": "file_read_error",
                    "kind": "corrupted",
                    "stage": "validation",
                }
            },
        )
        parse_error = LogFile.objects.create(
            collection=self.collection,
            path="/tmp/parse-error.log.gz",
            stat_result={},
            hash="3" * 32,
            status=choices.LOG_FILE_STATUS_ERROR,
            date=date(2026, 9, 4),
        )

        access_dates = LogFile.distinct_access_dates_for_parsing(
            collection=self.collection,
            from_date=date(2026, 9, 4),
            until_date=date(2026, 9, 4),
            status_filters=[choices.LOG_FILE_STATUS_ERROR],
        )
        log_files = LogFile.for_collection_date(
            collection=self.collection,
            access_date=date(2026, 9, 4),
            status_filters=[choices.LOG_FILE_STATUS_ERROR],
        )

        self.assertEqual(access_dates, [date(2026, 9, 4)])
        self.assertEqual(log_files, [parse_error])
        self.assertNotIn(read_error, log_files)
