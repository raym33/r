"""Direct, schema-aware execution of R CLI tools."""

import json
from dataclasses import dataclass
from typing import Any

from r_cli.core.agent import Skill
from r_cli.core.config import Config
from r_cli.core.llm import Tool
from r_cli.core.permissions import ApprovalCallback, PermissionManager


class ToolRunnerError(ValueError):
    """Raised when a skill, tool, or argument is invalid."""


@dataclass
class ToolMatch:
    """A resolved skill and tool."""

    skill: Skill
    tool: Tool


def load_skill(skill_name: str, config: Config | None = None) -> Skill:
    """Load one skill by its public name."""
    from r_cli.skills import get_all_skills

    active_config = config or Config.load()
    active_config.ensure_directories()
    for skill_class in get_all_skills():
        if getattr(skill_class, "name", None) == skill_name:
            return skill_class(active_config)
    raise ToolRunnerError(f"Unknown skill: {skill_name}")


def resolve_tool(skill_name: str, tool_name: str, config: Config | None = None) -> ToolMatch:
    """Resolve a tool from a skill."""
    skill = load_skill(skill_name, config)
    for tool in skill.get_tools():
        if tool.name == tool_name:
            return ToolMatch(skill=skill, tool=tool)

    available = ", ".join(tool.name for tool in skill.get_tools()) or "none"
    raise ToolRunnerError(
        f"Unknown tool '{tool_name}' for skill '{skill_name}'. Available: {available}"
    )


def parse_key_value(value: str) -> tuple[str, Any]:
    """Parse KEY=VALUE, decoding VALUE as JSON when possible."""
    if "=" not in value:
        raise ToolRunnerError(f"Expected KEY=VALUE, got: {value}")

    key, raw_value = value.split("=", 1)
    key = key.strip()
    if not key:
        raise ToolRunnerError("Argument names cannot be empty")

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        parsed = raw_value
    return key, parsed


def build_arguments(params: str | None, values: tuple[str, ...]) -> dict[str, Any]:
    """Combine a JSON object and repeated KEY=VALUE arguments."""
    arguments: dict[str, Any] = {}
    if params:
        try:
            decoded = json.loads(params)
        except json.JSONDecodeError as exc:
            raise ToolRunnerError(f"Invalid JSON in --params: {exc.msg}") from exc
        if not isinstance(decoded, dict):
            raise ToolRunnerError("--params must contain a JSON object")
        arguments.update(decoded)

    for value in values:
        key, parsed = parse_key_value(value)
        arguments[key] = parsed
    return arguments


def validate_arguments(tool: Tool, arguments: dict[str, Any]) -> None:
    """Validate required and unknown arguments using the tool JSON schema."""
    schema = tool.parameters or {}
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    missing = [name for name in required if name not in arguments]
    if missing:
        raise ToolRunnerError(f"Missing required arguments: {', '.join(missing)}")

    unknown = sorted(set(arguments) - set(properties))
    if unknown and properties:
        raise ToolRunnerError(f"Unknown arguments: {', '.join(unknown)}")


def execute_tool(
    skill_name: str,
    tool_name: str,
    arguments: dict[str, Any],
    config: Config | None = None,
    approval_callback: ApprovalCallback | None = None,
    auto_approve: bool = False,
) -> Any:
    """Resolve, validate, and execute a tool."""
    active_config = config or Config.load()
    match = resolve_tool(skill_name, tool_name, active_config)
    validate_arguments(match.tool, arguments)
    permissions = PermissionManager(
        active_config,
        approval_callback=approval_callback,
        auto_approve=auto_approve,
    )
    return permissions.execute(skill_name, tool_name, match.tool.handler, arguments)


def normalize_result(result: Any) -> Any:
    """Decode JSON returned as text while preserving ordinary strings."""
    if not isinstance(result, str):
        return result
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return result
