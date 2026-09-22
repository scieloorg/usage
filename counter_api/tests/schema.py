import json
from functools import lru_cache
from pathlib import Path

from jsonschema.validators import validator_for

SCHEMA_PATH = Path(__file__).parents[1] / "schemas" / "COUNTER_API_5_1_1.json"


@lru_cache(maxsize=1)
def _specification():
    with SCHEMA_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)


def validate_report(payload, report_id):
    specification = _specification()
    schema_name = report_id.upper()
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "components": specification["components"],
        "$ref": f"#/components/schemas/{schema_name}",
    }
    validator = validator_for(schema)(schema)

    validator.validate(payload)
