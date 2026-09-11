from metrics.counter.indexing import converter


def convert_accumulator(accumulator):
    values = list(accumulator.iter_materialized_values())
    return {
        "counter": dict(converter.iter_partitioned_values(values, "counter")),
        "analytics": dict(converter.iter_partitioned_values(values, "analytics")),
    }
