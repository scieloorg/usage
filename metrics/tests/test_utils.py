import io
import tarfile
import unittest

from metrics.utils import (
    get_load_data_function, 
    load_csv, 
    load_tar_gz,
)


class TestUtils(unittest.TestCase):
    
    def setUp(self):
        self.csv_path = '/app/metrics/fixtures/top100articles.csv'
        self.tar_path = '/app/metrics/fixtures/top100articles.tar.gz'

    def test_get_load_data_function_csv(self):
        load_function = get_load_data_function(self.csv_path)
        self.assertEqual(load_function, load_csv)

    def test_get_load_data_function_tar_gz(self):
        load_function = get_load_data_function(self.tar_path)
        self.assertEqual(load_function, load_tar_gz)

    def test_load_csv_from_csv(self):
        result = list(load_csv(self.csv_path))[0]
        expected = {
            "total_item_requests": "13",
            "total_item_investigations": "16",
            "unique_item_requests": "13",
            "unique_item_investigations": "16",
            "print_issn": "0002-7014",
            "pid_issn": "0002-7014",
            "online_issn": "1851-8044",
            "collection": "arg",
            "pid": "S0002-70142005000300005",
            "yop": "2005",
            "year_month_day": "2024-05-26"
        }

        self.assertDictEqual(result, expected)

    def test_load_tar_gz(self):
        result = list(load_tar_gz(self.tar_path))[0]
        expected = {
            "total_item_requests": "13",
            "total_item_investigations": "16",
            "unique_item_requests": "13",
            "unique_item_investigations": "16",
            "print_issn": "0002-7014",
            "pid_issn": "0002-7014",
            "online_issn": "1851-8044",
            "collection": "arg",
            "pid": "S0002-70142005000300005",
            "yop": "2005",
            "year_month_day": "2024-05-26"
        }
        
        self.assertDictEqual(result, expected)
