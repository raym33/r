"""Tests for direct tool execution."""

import pytest

from r_cli.core.llm import Tool
from r_cli.tool_runner import (
    ToolRunnerError,
    build_arguments,
    normalize_result,
    parse_key_value,
    validate_arguments,
)


def sample_tool() -> Tool:
    return Tool(
        name="sample",
        description="Sample tool",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["name"],
        },
        handler=lambda **kwargs: kwargs,
    )


def test_parse_key_value_decodes_json_values():
    assert parse_key_value("count=3") == ("count", 3)
    assert parse_key_value("enabled=true") == ("enabled", True)
    assert parse_key_value('items=["a","b"]') == ("items", ["a", "b"])
    assert parse_key_value("name=R CLI") == ("name", "R CLI")


def test_build_arguments_merges_json_and_key_values():
    result = build_arguments('{"name": "R", "count": 1}', ("count=2",))

    assert result == {"name": "R", "count": 2}


def test_build_arguments_rejects_non_object_json():
    with pytest.raises(ToolRunnerError, match="JSON object"):
        build_arguments("[1, 2]", ())


def test_validate_arguments_reports_missing_values():
    with pytest.raises(ToolRunnerError, match="name"):
        validate_arguments(sample_tool(), {"count": 1})


def test_validate_arguments_reports_unknown_values():
    with pytest.raises(ToolRunnerError, match="extra"):
        validate_arguments(sample_tool(), {"name": "R", "extra": True})


def test_normalize_result_decodes_json_text():
    assert normalize_result('{"pages": 2}') == {"pages": 2}
    assert normalize_result("ordinary text") == "ordinary text"
