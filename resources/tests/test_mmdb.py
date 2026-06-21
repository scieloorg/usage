from django.test import TestCase

from resources.models import MMDB


class MMDBModelTests(TestCase):
    def test_save_computes_sha256_hash_as_pk(self):
        data = b"fake mmdb binary data"
        mmdb = MMDB(data=data, url="https://example.org/GeoLite2-Country.mmdb")
        mmdb.save()

        self.assertEqual(mmdb.pk, MMDB.compute_hash(data))
        self.assertEqual(MMDB.objects.count(), 1)

    def test_different_data_produces_different_hash(self):
        mmdb1 = MMDB(data=b"data-v1")
        mmdb1.save()
        mmdb2 = MMDB(data=b"data-v2")
        mmdb2.save()

        self.assertNotEqual(mmdb1.pk, mmdb2.pk)
        self.assertEqual(MMDB.objects.count(), 2)
