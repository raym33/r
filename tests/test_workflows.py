"""Tests for declarative R workflows."""

from pathlib import Path
from unittest.mock import patch

import pytest

from r_cli.core.permissions import PermissionDeniedError
from r_cli.workflows import WorkflowError, load_workflow, run_workflow


def write_workflow(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "workflow.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_rejects_dependency_cycles(tmp_path):
    path = write_workflow(
        tmp_path,
        """
steps:
  - id: one
    uses: math.calculate
    depends_on: [two]
  - id: two
    uses: math.calculate
    depends_on: [one]
""",
    )

    with pytest.raises(WorkflowError, match="cycle"):
        load_workflow(path)


def test_load_rejects_invalid_templates(tmp_path):
    path = write_workflow(
        tmp_path,
        """
steps:
  - id: broken
    uses: math.calculate
    with:
      expression: "{{ vars.value "
""",
    )

    with pytest.raises(WorkflowError, match="template"):
        load_workflow(path)


def test_run_passes_results_between_steps(tmp_path):
    path = write_workflow(
        tmp_path,
        """
name: chained
variables:
  multiplier: 3
steps:
  - id: base
    uses: math.calculate
    with:
      expression: 6 * 7
  - id: scaled
    uses: math.calculate
    depends_on: [base]
    with:
      expression: "{{ steps.base.result }} * {{ vars.multiplier }}"
""",
    )
    calls = []

    def fake_execute(skill, tool, arguments, **kwargs):
        calls.append((skill, tool, arguments, kwargs["source"]))
        return 42 if len(calls) == 1 else 126

    with patch("r_cli.workflows.execute_tool", side_effect=fake_execute):
        result = run_workflow(load_workflow(path))

    assert result.status == "completed"
    assert result.steps[-1].result == 126
    assert calls[-1] == (
        "math",
        "calculate",
        {"expression": "42 * 3"},
        "workflow:chained",
    )


def test_run_retries_then_succeeds(tmp_path):
    path = write_workflow(
        tmp_path,
        """
steps:
  - id: unstable
    uses: math.calculate
    retry: 2
    with:
      expression: 1 + 1
""",
    )

    with patch(
        "r_cli.workflows.execute_tool",
        side_effect=[RuntimeError("temporary"), RuntimeError("temporary"), 2],
    ):
        result = run_workflow(load_workflow(path))

    assert result.status == "completed"
    assert result.steps[0].attempts == 3


def test_permission_denial_is_not_retried(tmp_path):
    path = write_workflow(
        tmp_path,
        """
steps:
  - id: guarded
    uses: code.run_python
    retry: 3
""",
    )

    with patch(
        "r_cli.workflows.execute_tool",
        side_effect=PermissionDeniedError("denied"),
    ) as execute:
        result = run_workflow(load_workflow(path))

    execute.assert_called_once()
    assert result.status == "error"
    assert result.steps[0].attempts == 1


def test_failed_step_stops_remaining_work(tmp_path):
    path = write_workflow(
        tmp_path,
        """
steps:
  - id: broken
    uses: math.calculate
  - id: later
    uses: math.calculate
""",
    )

    with patch("r_cli.workflows.execute_tool", side_effect=RuntimeError("boom")):
        result = run_workflow(load_workflow(path))

    assert result.status == "error"
    assert [step.status for step in result.steps] == ["error", "skipped"]


def test_dry_run_does_not_execute_tools(tmp_path):
    path = write_workflow(
        tmp_path,
        """
variables:
  value: 10
steps:
  - id: calculate
    uses: math.calculate
    with:
      expression: "{{ vars.value }} + 2"
""",
    )

    with patch("r_cli.workflows.execute_tool") as execute:
        result = run_workflow(load_workflow(path), dry_run=True)

    execute.assert_not_called()
    assert result.status == "planned"
    assert result.steps[0].result["arguments"]["expression"] == "10 + 2"
