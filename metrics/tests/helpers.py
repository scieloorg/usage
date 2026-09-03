from metrics.counter.indexing import converter


def convert_accumulator(accumulator):
    values = list(accumulator.iter_materialized_values())
    return {
        "month": converter.convert_granularity(iter(values), "month"),
        "year": converter.convert_granularity(iter(values), "year"),
    }
