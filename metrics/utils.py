import csv


def load_csv(path, delimiter='\t'):
    with open(path) as fin:
        for row in csv.DictReader(fin, fieldnames=fin.readline().strip().split(delimiter), delimiter=delimiter):
            yield row
