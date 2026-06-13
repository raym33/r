"""Tests for the persistent Agent OS runtime."""

from pathlib import Path
from unittest.mock import patch

import pytest

from r_cli.agent_os import (
    AgentManifest,
    AgentOS,
    AgentOSError,
    load_agent_manifest,
    validate_agent_capabilities,
)
from r_cli.core.config import Config
from r_cli.core.memory import Memory


def os_config(tmp_path: Path) -> Config:
    return Config(
        home_dir=str(tmp_path / "home"),
        output_dir=str(tmp_path / "output"),
        skills_dir=str(tmp_path / "skills"),
    )


def test_manifest_resolves_relative_workflow(tmp_path):
    workflow = tmp_path / "job.yaml"
    workflow.write_text(
        "steps:\n  - id: calculate\n    uses: math.calculate\n    with:\n      expression: 2 + 2\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "agent.yaml"
    manifest.write_text(
        """
name: calculator
description: Deterministic calculator
kind: workflow
workflow: job.yaml
""",
        encoding="utf-8",
    )

    result = load_agent_manifest(manifest)

    assert result.workflow == str(workflow.resolve())


def test_install_list_and_remove_agent(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    manifest = AgentManifest("writer", "Writes things", skills=["text"])

    runtime.install(manifest)

    assert runtime.get_agent("writer") == manifest
    assert runtime.list_agents()[0]["task_count"] == 0
    runtime.remove("writer")
    assert runtime.list_agents() == []
    assert runtime.list_events()[0]["event_type"] == "agent.removed"


def test_duplicate_agent_requires_replace(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    runtime.install(AgentManifest("writer", "First"))

    with pytest.raises(AgentOSError, match="already exists"):
        runtime.install(AgentManifest("writer", "Second"))

    runtime.install(AgentManifest("writer", "Second"), replace=True)
    assert runtime.get_agent("writer").description == "Second"


def test_run_records_completed_task_and_events(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    runtime.install(AgentManifest("writer", "Writes things"))

    with patch.object(runtime, "_run_assistant", return_value="finished"):
        task = runtime.run("writer", "Write a report")

    assert task["status"] == "completed"
    assert task["result"] == "finished"
    assert [event["event_type"] for event in runtime.list_events()] == [
        "task.completed",
        "task.running",
        "task.queued",
        "agent.installed",
    ]
    assert runtime.list_events()[2]["payload"] == {"input_length": 14}


def test_run_persists_failures(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    runtime.install(AgentManifest("writer", "Writes things"))

    with patch.object(runtime, "_run_assistant", side_effect=RuntimeError("model offline")):
        task = runtime.run("writer", "Write a report")

    assert task["status"] == "failed"
    assert task["error"] == "model offline"
    assert runtime.status()["tasks"]["failed"] == 1


def test_agent_with_task_history_cannot_be_removed(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    runtime.install(AgentManifest("writer", "Writes things"))
    with patch.object(runtime, "_run_assistant", return_value="done"):
        runtime.run("writer", "Task")

    with pytest.raises(AgentOSError, match="task history"):
        runtime.remove("writer")


def test_agent_memory_namespaces_are_isolated(tmp_path):
    config = os_config(tmp_path)
    writer = Memory(config, namespace="writer")
    reviewer = Memory(config, namespace="reviewer")
    writer.add_short_term("writer memory")
    writer.save_session()

    assert reviewer.load_session() is False
    assert Memory(config, namespace="writer").load_session() is True


def test_unknown_agent_capability_is_rejected():
    with pytest.raises(AgentOSError, match="unknown-skill"):
        validate_agent_capabilities(
            AgentManifest("agent", "Agent", skills=["math", "unknown-skill"])
        )


def test_broad_host_capability_requires_explicit_unsafe_flag():
    with pytest.raises(AgentOSError, match="unsafe_capabilities"):
        validate_agent_capabilities(AgentManifest("coder", "Coder", skills=["code"]))

    validate_agent_capabilities(
        AgentManifest(
            "coder",
            "Coder",
            skills=["code"],
            unsafe_capabilities=True,
        )
    )


def test_network_agent_requires_explicit_hosts():
    with pytest.raises(AgentOSError, match="allowed host"):
        validate_agent_capabilities(
            AgentManifest("agent", "Agent", skills=["http"], network_access=True)
        )
