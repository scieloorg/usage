from django.test import TestCase

from collection.models import Collection
from core.users.tests.factories import UserFactory
from log_manager_config.models import CollectionLogDirectory, LogManagerCollectionConfig


class LogManagerCollectionConfigTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.collection = Collection.objects.create(acron3="books", acron2="bk")

    def test_create_or_update_creates_config(self):
        config = LogManagerCollectionConfig.create_or_update(
            user=self.user,
            collection=self.collection,
            sample_size=0.2,
            buffer_size=4096,
            expected_logs_per_day=3,
        )

        self.assertEqual(config.collection, self.collection)
        self.assertEqual(config.sample_size, 0.2)
        self.assertEqual(config.buffer_size, 4096)
        self.assertEqual(config.expected_logs_per_day, 3)

    def test_create_or_update_updates_existing(self):
        LogManagerCollectionConfig.create_or_update(
            user=self.user,
            collection=self.collection,
            sample_size=0.1,
            buffer_size=2048,
            expected_logs_per_day=1,
        )
        config = LogManagerCollectionConfig.create_or_update(
            user=self.user,
            collection=self.collection,
            sample_size=0.5,
            buffer_size=8192,
            expected_logs_per_day=5,
        )

        self.assertEqual(LogManagerCollectionConfig.objects.count(), 1)
        self.assertEqual(config.sample_size, 0.5)
        self.assertEqual(config.buffer_size, 8192)


class CollectionLogDirectoryTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.collection = Collection.objects.create(acron3="scl", acron2="sc")
        self.config = LogManagerCollectionConfig.create_or_update(
            user=self.user,
            collection=self.collection,
            sample_size=0.1,
            buffer_size=2048,
            expected_logs_per_day=1,
        )

    def test_create_or_update_creates_directory(self):
        directory = CollectionLogDirectory.create_or_update(
            user=self.user,
            config=self.config,
            directory_name="classic-logs",
            path="/data/logs/scl",
            active=True,
            translator_class="classic",
        )

        self.assertEqual(directory.config, self.config)
        self.assertEqual(directory.path, "/data/logs/scl")
        self.assertEqual(directory.translator_class, "classic")

    def test_translator_class_defaults_to_classic(self):
        directory = CollectionLogDirectory.create_or_update(
            user=self.user,
            config=self.config,
            directory_name="logs",
            path="/data/logs/scl",
            active=True,
            translator_class=None,
        )

        self.assertEqual(directory.translator_class, "classic")
