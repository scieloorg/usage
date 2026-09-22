from django.test import SimpleTestCase

from config.sentry import scrub_api_key


class SentryTests(SimpleTestCase):
    def test_removes_api_key_from_error_and_transaction_events(self):
        event = {
            "request": {
                "url": "https://example.org/r51/reports/tr?api_key=secret&platform=scl",
                "query_string": "api_key=secret&platform=scl",
            }
        }

        result = scrub_api_key(event, {})

        self.assertEqual(result["request"]["query_string"], "")
        self.assertEqual(
            result["request"]["url"],
            "https://example.org/r51/reports/tr",
        )
