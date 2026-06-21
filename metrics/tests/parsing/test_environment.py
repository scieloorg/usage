from django.test import TestCase

from metrics.services.parsing.environment import _get_translator_class


class TranslatorClassTests(TestCase):
    def test_books_maps_to_books_translator(self):
        cls = _get_translator_class("books")
        self.assertEqual(cls.__name__, "URLTranslatorBooksSite")

    def test_classic_maps_to_classic_translator(self):
        cls = _get_translator_class("classic")
        self.assertEqual(cls.__name__, "URLTranslatorClassicSite")

    def test_opac_maps_to_opac_translator(self):
        cls = _get_translator_class("opac")
        self.assertEqual(cls.__name__, "URLTranslatorOPACSite")

    def test_opac_alpha_maps_to_opac_alpha_translator(self):
        cls = _get_translator_class("opac_alpha")
        self.assertEqual(cls.__name__, "URLTranslatorOPACAlphaSite")

    def test_preprints_maps_to_preprints_translator(self):
        cls = _get_translator_class("preprints")
        self.assertEqual(cls.__name__, "URLTranslatorPreprintsSite")

    def test_dataverse_maps_to_dataverse_translator(self):
        cls = _get_translator_class("dataverse")
        self.assertEqual(cls.__name__, "URLTranslatorDataverseSite")

    def test_unknown_name_returns_none(self):
        self.assertIsNone(_get_translator_class("unknown"))

    def test_none_returns_none(self):
        self.assertIsNone(_get_translator_class(None))

    def test_case_insensitive(self):
        cls = _get_translator_class("Books")
        self.assertEqual(cls.__name__, "URLTranslatorBooksSite")
