from django.test import SimpleTestCase

from counter_api.identifiers import counter_identifiers


class CounterIdentifierTests(SimpleTestCase):
    def test_normalizes_standard_and_proprietary_identifiers(self):
        result = dict(
            counter_identifiers(
                {
                    "identifiers": {
                        "doi": "https://doi.org/10.1234/example",
                        "isbn": "8575410326",
                        "pid_v2": "legacy-id",
                        "pid_generic": "canonical-id",
                    }
                }
            )
        )

        self.assertEqual(result["DOI"], "10.1234/example")
        self.assertEqual(result["ISBN"], "978-85-7541-032-5")
        self.assertEqual(result["Proprietary"], "SciELO:canonical-id")
