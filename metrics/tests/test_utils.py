import unittest
import io
import tarfile

from unittest.mock import patch, mock_open

from metrics.utils import (
    get_load_data_function, 
    load_csv, 
    load_tar_gz,
)


class TestUtils(unittest.TestCase):
    
    def setUp(self):
        self.csv_content = "col1,col2,col3\n1,2,3\n4,5,6"
        self.tar_content = io.BytesIO()

        with tarfile.open(fileobj=self.tar_content, mode="w:gz") as tar:
            tarinfo = tarfile.TarInfo(name="example.csv")
            tarinfo.size = len(self.csv_content)
            tar.addfile(tarinfo, io.BytesIO(self.csv_content.encode('utf-8')))

        self.tar_content.seek(0)

    def test_get_load_data_function_csv(self):
        load_function = get_load_data_function("example.csv")
        self.assertEqual(load_function, load_csv)

    def test_get_load_data_function_tar_gz(self):
        load_function = get_load_data_function("example.tar.gz")
        self.assertEqual(load_function, load_tar_gz)

    def test_load_csv(self):
        csv_file = io.StringIO(self.csv_content)
        result = list(load_csv(csv_file, delimiter=',', is_stream=True))
        expected = [
            {"col1": "1", "col2": "2", "col3": "3"},
            {"col1": "4", "col2": "5", "col3": "6"}
        ]
        self.assertEqual(result, expected)

    @patch("builtins.open", new_callable=mock_open, read_data="col1\tcol2\tcol3\n1\t2\t3\n4\t5\t6")
    def test_load_csv_from_file(self, mock_file):
        result = list(load_csv("dummy_path.csv"))
        expected = [
            {"col1": "1", "col2": "2", "col3": "3"},
            {"col1": "4", "col2": "5", "col3": "6"}
        ]
        self.assertEqual(result, expected)

    def test_load_tar_gz(self):
        with patch("builtins.open", mock_open(read_data=self.tar_content.read()), create=True):
            with tarfile.open(fileobj=self.tar_content, mode='r:gz') as tar:
                result = list(load_tar_gz(tar.name))
                expected = [
                    {"col1": "1", "col2": "2", "col3": "3"},
                    {"col1": "4", "col2": "5", "col3": "6"}
                ]
                self.assertEqual(result, expected)
