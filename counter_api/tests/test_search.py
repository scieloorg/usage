from time import monotonic
from unittest.mock import Mock

from django.test import SimpleTestCase
from opensearchpy.exceptions import OpenSearchException

from counter_api.exceptions import CounterAPIError
from counter_api.search import search


class SearchTests(SimpleTestCase):
    def test_converts_opensearch_failures_to_counter_exception(self):
        client = Mock()
        client.search.side_effect = OpenSearchException("connection failed")

        with self.assertRaises(CounterAPIError) as raised:
            search(client, "usage_month_status", {}, monotonic() + 1)

        self.assertEqual(raised.exception.code, 1000)
        self.assertEqual(raised.exception.status_code, 503)
