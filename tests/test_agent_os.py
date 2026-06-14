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


def test_programmatic_install_validates_broad_capabilities(tmp_path):
    runtime = AgentOS(os_config(tmp_path))

    with pytest.raises(AgentOSError, match="unsafe_capabilities"):
        runtime.install(AgentManifest("coder", "Coder", skills=["code"]))


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


def test_create_and_start_task_separately(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    runtime.install(AgentManifest("writer", "Writes things"))
    queued = runtime.create_task("writer", "Write a report")

    with patch.object(runtime, "_run_assistant", return_value="finished"):
        task = runtime.run_task(queued["id"])

    assert queued["status"] == "queued"
    assert task["status"] == "completed"
    assert task["result"] == "finished"


def test_run_persists_failures(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    runtime.install(AgentManifest("writer", "Writes things"))

    with patch.object(runtime, "_run_assistant", side_effect=RuntimeError("model offline")):
        task = runtime.run("writer", "Write a report")

    assert task["status"] == "failed"
    assert task["error"] == "model offline"
    assert runtime.status()["tasks"]["failed"] == 1


def test_cancel_running_task_persists_terminal_state(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    runtime.install(AgentManifest("writer", "Writes things"))

    def cancel_during_run(*args, **kwargs):
        running = runtime.list_tasks(status="running")
        assert len(running) == 1
        runtime.cancel_task(running[0]["id"], reason="user requested stop")
        return "finished too late"

    with patch.object(runtime, "_run_assistant", side_effect=cancel_during_run):
        task = runtime.run("writer", "Write a report")

    assert task["status"] == "cancelled"
    assert task["result"] is None
    assert task["error"] == "user requested stop"
    assert runtime.status()["tasks"]["cancelled"] == 1
    assert [event["event_type"] for event in runtime.list_events(limit=5)[:4]] == [
        "task.cancelled",
        "task.running",
        "task.queued",
        "agent.installed",
    ]


def test_completed_task_cannot_be_cancelled(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    runtime.install(AgentManifest("writer", "Writes things"))
    with patch.object(runtime, "_run_assistant", return_value="done"):
        task = runtime.run("writer", "Task")

    with pytest.raises(AgentOSError, match="already completed"):
        runtime.cancel_task(task["id"])


def test_pause_and_resume_queued_task(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    runtime.install(AgentManifest("writer", "Writes things"))
    with runtime._connect() as connection:
        connection.execute(
            """
            INSERT INTO tasks(id, agent_name, input, status, created_at)
            VALUES ('task123', 'writer', 'Draft report', 'queued', 'now')
            """
        )

    paused = runtime.pause_task("task123", reason="waiting for approval")
    resumed = runtime.resume_task("task123")

    assert paused["status"] == "paused"
    assert paused["error"] == "waiting for approval"
    assert resumed["status"] == "queued"
    assert resumed["error"] is None
    assert runtime.status()["tasks"]["queued"] == 1
    assert [event["event_type"] for event in runtime.list_events(limit=3)[:2]] == [
        "task.resumed",
        "task.paused",
    ]


def test_running_task_cannot_be_paused(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    runtime.install(AgentManifest("writer", "Writes things"))
    with runtime._connect() as connection:
        connection.execute(
            """
            INSERT INTO tasks(id, agent_name, input, status, created_at, started_at)
            VALUES ('task123', 'writer', 'Draft report', 'running', 'now', 'now')
            """
        )

    with pytest.raises(AgentOSError, match="already running"):
        runtime.pause_task("task123")


def test_only_queued_tasks_can_start(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    runtime.install(AgentManifest("writer", "Writes things"))
    with runtime._connect() as connection:
        connection.execute(
            """
            INSERT INTO tasks(id, agent_name, input, status, created_at)
            VALUES ('task123', 'writer', 'Draft report', 'paused', 'now')
            """
        )

    with pytest.raises(AgentOSError, match="is not queued"):
        runtime.run_task("task123")


def test_paused_task_cannot_start_accidentally(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    runtime.install(AgentManifest("writer", "Writes things"))
    with runtime._connect() as connection:
        connection.execute(
            """
            INSERT INTO tasks(id, agent_name, input, status, created_at)
            VALUES ('task123', 'writer', 'Draft report', 'paused', 'now')
            """
        )

    assert runtime._set_task_state("task123", "running") is False
    assert runtime.get_task("task123")["status"] == "paused"


def test_task_capsule_redacts_sensitive_content_by_default(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    runtime.install(
        AgentManifest(
            "writer",
            "Private description",
            system_prompt="Private prompt",
            skills=["text"],
            filesystem_roots=[str(tmp_path / "private"), str(tmp_path / "docs")],
        )
    )

    with patch.object(runtime, "_run_assistant", return_value="private result"):
        task = runtime.run("writer", "Private input")

    capsule = runtime.export_task_capsule(task["id"])

    assert capsule["kind"] == "r.agent_os.task_capsule"
    assert capsule["content_included"] is False
    assert capsule["redaction"]["enabled"] is True
    assert capsule["task"]["input"] == "[redacted]"
    assert capsule["task"]["result"] == "[redacted]"
    assert capsule["agent"]["description"] == "[redacted]"
    assert capsule["agent"]["system_prompt"] == "[redacted]"
    assert capsule["agent"]["filesystem_roots"] == ["[redacted]"]
    assert capsule["security"]["skills_count"] == 1
    assert capsule["security"]["filesystem_roots_count"] == 2
    assert [event["event_type"] for event in capsule["events"]] == [
        "task.queued",
        "task.running",
        "task.completed",
    ]


def test_task_capsule_can_include_content_explicitly(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    runtime.install(AgentManifest("writer", "Private description"))

    with patch.object(runtime, "_run_assistant", return_value="private result"):
        task = runtime.run("writer", "Private input")

    capsule = runtime.export_task_capsule(task["id"], include_content=True)

    assert capsule["content_included"] is True
    assert capsule["redaction"]["enabled"] is False
    assert capsule["task"]["input"] == "Private input"
    assert capsule["task"]["result"] == "private result"
    assert capsule["agent"]["description"] == "Private description"


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


def test_network_policy_is_validated_even_without_skills():
    with pytest.raises(AgentOSError, match="allowed host"):
        validate_agent_capabilities(AgentManifest("agent", "Agent", network_access=True))


def test_empty_agent_skill_list_is_a_deny_all_capability_set(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    manifest = AgentManifest("chat-only", "No tool access", skills=[])
    captured = {}

    class FakeLLM:
        def set_system_prompt(self, prompt):
            captured["prompt"] = prompt

    class FakeAgent:
        def __init__(self, config, **kwargs):
            captured["mode"] = config.skills.mode
            captured["enabled"] = config.skills.enabled
            captured["enforce_roots"] = config.security.enforce_filesystem_roots
            self.llm = FakeLLM()

        def load_skills(self, verbose=False):
            captured["loaded"] = True

        def run(self, task_input, show_thinking=False):
            return "done"

    with patch("r_cli.core.agent.Agent", FakeAgent):
        result = runtime._run_assistant(manifest, "Hello", None, False)

    assert result == "done"
    assert captured["mode"] == "whitelist"
    assert captured["enabled"] == []
    assert captured["enforce_roots"] is True


def test_workflow_agent_uses_the_same_capability_boundary(tmp_path):
    runtime = AgentOS(os_config(tmp_path))
    workflow = tmp_path / "workflow.yaml"
    workflow.write_text("steps: []\n", encoding="utf-8")
    manifest = AgentManifest(
        "calculator",
        "Restricted workflow",
        kind="workflow",
        workflow=str(workflow),
        skills=["math"],
    )
    captured = {}

    class FakeResult:
        status = "ok"
        steps = []

        def to_dict(self):
            return {"status": "ok"}

    def fake_run_workflow(definition, **kwargs):
        config = kwargs["config"]
        captured["mode"] = config.skills.mode
        captured["enabled"] = config.skills.enabled
        captured["enforce_roots"] = config.security.enforce_filesystem_roots
        return FakeResult()

    with (
        patch("r_cli.workflows.load_workflow", return_value={"steps": []}),
        patch("r_cli.workflows.run_workflow", side_effect=fake_run_workflow),
    ):
        result = runtime._run_workflow_agent(manifest, "Calculate", None, False)

    assert result == {"status": "ok"}
    assert captured == {
        "mode": "whitelist",
        "enabled": ["math"],
        "enforce_roots": True,
    }


@pytest.mark.parametrize("field", ["network_access", "unsafe_capabilities"])
def test_manifest_rejects_string_booleans(tmp_path, field):
    manifest = tmp_path / "agent.yaml"
    manifest.write_text(
        f"""
name: unsafe
description: Invalid boolean
skills: []
{field}: "false"
""",
        encoding="utf-8",
    )

    with pytest.raises(AgentOSError, match=field):
        load_agent_manifest(manifest)


@pytest.mark.parametrize(
    "host",
    ["https://api.example.com", "api.example.com:443", "*.example.com"],
)
def test_manifest_rejects_ambiguous_allowed_hosts(tmp_path, host):
    manifest = tmp_path / "agent.yaml"
    manifest.write_text(
        f"""
name: networked
description: Invalid host rule
skills: [http]
network_access: true
allowed_hosts:
  - "{host}"
""",
        encoding="utf-8",
    )

    with pytest.raises(AgentOSError, match="Invalid agent allowed host"):
        load_agent_manifest(manifest)
