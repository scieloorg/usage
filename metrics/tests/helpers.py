from metrics.counter.indexing import converter


def convert_accumulator(accumulator):
    values = list(accumulator.iter_materialized_values())
    return {
        "month": dict(converter.iter_partitioned_values(values, "month")),
        "year": dict(converter.iter_partitioned_values(values, "year")),
    }
