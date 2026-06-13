"""Declarative, reproducible workflows for R tools."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from jinja2 import StrictUndefined
from jinja2.nativetypes import NativeEnvironment
from jinja2.sandbox import SandboxedEnvironment

from r_cli.core.permissions import PermissionDeniedError
from r_cli.tool_runner import (
    ToolRunnerError,
    execute_tool,
    normalize_result,
    resolve_tool,
    validate_arguments,
)

if TYPE_CHECKING:
    from r_cli.core.config import Config
    from r_cli.core.permissions import ApprovalCallback

MAX_WORKFLOW_STEPS = 100
ROOT_KEYS = {"version", "name", "variables", "steps"}
STEP_KEYS = {
    "id",
    "uses",
    "with",
    "depends_on",
    "if",
    "retry",
    "continue_on_error",
}


class WorkflowError(ValueError):
    """Raised when a workflow is invalid or cannot complete."""


class SandboxedNativeEnvironment(SandboxedEnvironment, NativeEnvironment):
    """Render native Python values without exposing unsafe template operations."""


@dataclass
class WorkflowStep:
    """One tool invocation in a workflow."""

    id: str
    uses: str
    with_: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    condition: Any = True
    retry: int = 0
    continue_on_error: bool = False

    @property
    def target(self) -> tuple[str, str]:
        skill, tool = self.uses.split(".", 1)
        return skill, tool


@dataclass
class Workflow:
    """Validated workflow definition."""

    name: str
    steps: list[WorkflowStep]
    variables: dict[str, Any] = field(default_factory=dict)
    version: int = 1


@dataclass
class StepResult:
    """Serializable result of one workflow step."""

    id: str
    target: str
    status: str
    result: Any = None
    error: str | None = None
    attempts: int = 0
    duration_ms: float = 0.0


@dataclass
class WorkflowResult:
    """Serializable workflow execution report."""

    name: str
    status: str
    steps: list[StepResult]
    duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "steps": [asdict(step) for step in self.steps],
        }


def load_workflow(path: str | Path) -> Workflow:
    """Load and validate a workflow YAML file."""
    workflow_path = Path(path).expanduser()
    try:
        raw = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"Workflow not found: {workflow_path}") from exc
    except yaml.YAMLError as exc:
        raise WorkflowError(f"Invalid workflow YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise WorkflowError("Workflow must be a YAML object")
    unknown_root_keys = set(raw) - ROOT_KEYS
    if unknown_root_keys:
        raise WorkflowError(
            f"Unknown workflow fields: {', '.join(sorted(unknown_root_keys))}"
        )
    if raw.get("version", 1) != 1:
        raise WorkflowError("Unsupported workflow version; expected version: 1")
    name = raw.get("name") or workflow_path.stem
    if not isinstance(name, str) or not name.strip():
        raise WorkflowError("Workflow name must be a non-empty string")

    raw_variables = raw.get("variables", {})
    if not isinstance(raw_variables, dict):
        raise WorkflowError("Workflow variables must be an object")
    raw_steps = raw.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise WorkflowError("Workflow must contain at least one step")
    if len(raw_steps) > MAX_WORKFLOW_STEPS:
        raise WorkflowError(f"Workflow exceeds the {MAX_WORKFLOW_STEPS}-step limit")

    steps = [_parse_step(item, index) for index, item in enumerate(raw_steps, 1)]
    _validate_graph(steps)
    for step in steps:
        _validate_templates(step.with_)
        _validate_templates(step.condition)
    return Workflow(
        name=name.strip(),
        version=1,
        variables=raw_variables,
        steps=steps,
    )


def run_workflow(
    workflow: Workflow,
    variables: dict[str, Any] | None = None,
    config: Config | None = None,
    approval_callback: ApprovalCallback | None = None,
    auto_approve: bool = False,
    dry_run: bool = False,
) -> WorkflowResult:
    """Execute workflow steps in dependency order."""
    from r_cli.core.config import Config

    active_config = config or Config.load()
    context: dict[str, Any] = {
        "vars": {**workflow.variables, **(variables or {})},
        "steps": {},
    }
    pending = {step.id: step for step in workflow.steps}
    results: list[StepResult] = []
    started_at = time.perf_counter()
    failed = False

    while pending:
        ready = [
            step
            for step in workflow.steps
            if step.id in pending and all(dependency in context["steps"] for dependency in step.depends_on)
        ]
        if not ready:
            raise WorkflowError("Workflow dependencies could not be resolved")

        for step in ready:
            del pending[step.id]
            dependency_failed = any(
                context["steps"][dependency]["status"] in {"error", "skipped"}
                for dependency in step.depends_on
            )
            if dependency_failed:
                result = StepResult(step.id, step.uses, "skipped", error="dependency failed")
            elif not _is_truthy(_render(step.condition, context)):
                result = StepResult(step.id, step.uses, "skipped")
            elif dry_run:
                result = StepResult(
                    step.id,
                    step.uses,
                    "planned",
                    result={"arguments": _render(step.with_, context)},
                )
            else:
                result = _run_step(
                    workflow,
                    step,
                    context,
                    active_config,
                    approval_callback,
                    auto_approve,
                )

            results.append(result)
            context["steps"][step.id] = {
                "status": result.status,
                "result": f"<result:{step.id}>"
                if result.status == "planned"
                else result.result,
                "error": result.error,
            }
            if result.status == "error":
                failed = True
                if not step.continue_on_error:
                    for blocked in pending.values():
                        results.append(
                            StepResult(
                                blocked.id,
                                blocked.uses,
                                "skipped",
                                error=f"workflow stopped after {step.id}",
                            )
                        )
                    pending.clear()
                    break

    duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
    status = "planned" if dry_run else ("error" if failed else "completed")
    return WorkflowResult(workflow.name, status, results, duration_ms)


def validate_workflow_tools(workflow: Workflow, config: Config | None = None) -> None:
    """Resolve every target and validate its declared argument names."""
    from r_cli.core.config import Config

    active_config = config or Config.load()
    for step in workflow.steps:
        skill, tool = step.target
        match = resolve_tool(skill, tool, active_config)
        validate_arguments(match.tool, step.with_)


def _parse_step(raw: Any, index: int) -> WorkflowStep:
    if not isinstance(raw, dict):
        raise WorkflowError(f"Step {index} must be an object")
    unknown_keys = set(raw) - STEP_KEYS
    if unknown_keys:
        raise WorkflowError(
            f"Step {index} has unknown fields: {', '.join(sorted(unknown_keys))}"
        )
    step_id = raw.get("id")
    uses = raw.get("uses")
    if not isinstance(step_id, str) or not step_id.strip():
        raise WorkflowError(f"Step {index} requires a non-empty id")
    if not isinstance(uses, str) or uses.count(".") != 1 or not all(uses.split(".")):
        raise WorkflowError(f"Step '{step_id}' uses must be 'skill.tool'")

    arguments = raw.get("with", {})
    dependencies = raw.get("depends_on", [])
    retry = raw.get("retry", 0)
    if not isinstance(arguments, dict):
        raise WorkflowError(f"Step '{step_id}' with must be an object")
    if isinstance(dependencies, str):
        dependencies = [dependencies]
    if not isinstance(dependencies, list) or not all(
        isinstance(item, str) for item in dependencies
    ):
        raise WorkflowError(f"Step '{step_id}' depends_on must be a list of step IDs")
    if not isinstance(retry, int) or not 0 <= retry <= 10:
        raise WorkflowError(f"Step '{step_id}' retry must be between 0 and 10")

    return WorkflowStep(
        id=step_id.strip(),
        uses=uses,
        with_=arguments,
        depends_on=dependencies,
        condition=raw.get("if", True),
        retry=retry,
        continue_on_error=bool(raw.get("continue_on_error", False)),
    )


def _validate_graph(steps: list[WorkflowStep]) -> None:
    ids = [step.id for step in steps]
    if len(ids) != len(set(ids)):
        raise WorkflowError("Workflow step IDs must be unique")
    known = set(ids)
    for step in steps:
        missing = set(step.depends_on) - known
        if missing:
            raise WorkflowError(
                f"Step '{step.id}' has unknown dependencies: {', '.join(sorted(missing))}"
            )
        if step.id in step.depends_on:
            raise WorkflowError(f"Step '{step.id}' cannot depend on itself")

    visiting: set[str] = set()
    visited: set[str] = set()
    by_id = {step.id: step for step in steps}

    def visit(step_id: str) -> None:
        if step_id in visiting:
            raise WorkflowError("Workflow dependency cycle detected")
        if step_id in visited:
            return
        visiting.add(step_id)
        for dependency in by_id[step_id].depends_on:
            visit(dependency)
        visiting.remove(step_id)
        visited.add(step_id)

    for step_id in ids:
        visit(step_id)


def _run_step(
    workflow: Workflow,
    step: WorkflowStep,
    context: dict[str, Any],
    config: Config,
    approval_callback: ApprovalCallback | None,
    auto_approve: bool,
) -> StepResult:
    started_at = time.perf_counter()
    arguments = _render(step.with_, context)
    skill, tool = step.target
    last_error: Exception | None = None
    attempts = 0

    for attempt in range(1, step.retry + 2):
        attempts = attempt
        try:
            value = execute_tool(
                skill,
                tool,
                arguments,
                config=config,
                approval_callback=approval_callback,
                auto_approve=auto_approve,
                source=f"workflow:{workflow.name}",
            )
            return StepResult(
                step.id,
                step.uses,
                "completed",
                result=normalize_result(value),
                attempts=attempt,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 3),
            )
        except (PermissionDeniedError, ToolRunnerError, WorkflowError) as exc:
            last_error = exc
            break
        except Exception as exc:
            last_error = exc

    return StepResult(
        step.id,
        step.uses,
        "error",
        error=str(last_error),
        attempts=attempts,
        duration_ms=round((time.perf_counter() - started_at) * 1000, 3),
    )


def _render(value: Any, context: dict[str, Any]) -> Any:
    environment = SandboxedNativeEnvironment(undefined=StrictUndefined, autoescape=False)
    try:
        if isinstance(value, str):
            return environment.from_string(value).render(context)
        if isinstance(value, dict):
            return {key: _render(item, context) for key, item in value.items()}
        if isinstance(value, list):
            return [_render(item, context) for item in value]
        return value
    except Exception as exc:
        raise WorkflowError(f"Template rendering failed: {exc}") from exc


def _validate_templates(value: Any) -> None:
    environment = SandboxedNativeEnvironment(undefined=StrictUndefined, autoescape=False)
    try:
        if isinstance(value, str):
            environment.parse(value)
        elif isinstance(value, dict):
            for item in value.values():
                _validate_templates(item)
        elif isinstance(value, list):
            for item in value:
                _validate_templates(item)
    except Exception as exc:
        raise WorkflowError(f"Invalid workflow template: {exc}") from exc


def _is_truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "none", "null"}
    return bool(value)
