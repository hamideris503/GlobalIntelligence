"""Mock باید برای هر ویژگی schema خروجی معتبر بسازد (const/enum/default/anyOf/min/max/nullable...)."""
from __future__ import annotations

import pytest
from jsonschema import validate

from backend.ai.providers.mock import _mock_from_schema
from domains.claims.evidence_prompts import EVIDENCE_SCHEMA
from domains.claims.prompts import CLAIMS_SCHEMA
from domains.events.prompts import EVENT_SCHEMA
from domains.news.classifier_schema import CLASSIFY_SCHEMA, EXTRACT_SCHEMA

PROJECT_SCHEMAS = [CLASSIFY_SCHEMA, EXTRACT_SCHEMA, EVENT_SCHEMA, CLAIMS_SCHEMA, EVIDENCE_SCHEMA]

FEATURE_SCHEMAS = [
    {"type": "string", "enum": ["supports", "contradicts"]},
    {"type": "string", "const": "fixed"},
    {"type": "integer", "default": 7},
    {"type": "number", "minimum": 0.2, "maximum": 1.0},
    {"type": "integer", "minimum": 5},
    {"type": ["string", "null"]},
    {"anyOf": [{"type": "null"}, {"type": "string", "enum": ["a", "b"]}]},
    {"oneOf": [{"type": "integer", "minimum": 3}, {"type": "string"}]},
    {"type": "array", "items": {"type": "string"}, "minItems": 2},
    {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["x"],
            "properties": {"x": {"type": "number", "minimum": 1}},
        },
    },
    {
        "type": "object",
        "required": ["a"],
        "properties": {"a": {"type": "string", "enum": ["z"]}, "b": {"type": "string"}},
    },
]


@pytest.mark.parametrize("schema", PROJECT_SCHEMAS)
def test_project_schemas_get_valid_mock_output(schema: dict) -> None:
    validate(_mock_from_schema(schema), schema)


@pytest.mark.parametrize("schema", FEATURE_SCHEMAS)
def test_schema_features_produce_valid_output(schema: dict) -> None:
    validate(_mock_from_schema(schema), schema)


def test_mock_is_deterministic() -> None:
    assert _mock_from_schema(EVIDENCE_SCHEMA) == _mock_from_schema(EVIDENCE_SCHEMA)
