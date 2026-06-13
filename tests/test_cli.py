"""Tests for the R CLI command-line interface."""

import json
from unittest.mock import patch

from click.testing import CliRunner

from r_cli.diagnostics import Diagnostic
from r_cli.main import cli


def test_bare_message_is_treated_as_chat():
    runner = CliRunner()

    with patch("r_cli.main.single_query") as single_query:
        result = runner.invoke(cli, ["explain", "quantum", "physics"])

    assert result.exit_code == 0
    single_query.assert_called_once_with(
        "explain quantum physics",
        "ps2",
        True,
        None,
        True,
        False,
    )


def test_help_shows_core_workflows():
    runner = CliRunner()

    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert 'r "Explain what Python is"' in result.output
    assert "r doctor" in result.output
    assert "-h, --help" in result.output


def test_tool_command_executes_with_typed_arguments():
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["tool", "math", "calculate", "--arg", "expression=2+3*4"],
    )

    assert result.exit_code == 0
    assert result.output.strip() == "14"


def test_tool_command_forwards_explicit_approval():
    runner = CliRunner()

    with patch("r_cli.tool_runner.execute_tool", return_value="ok") as execute_tool:
        result = runner.invoke(
            cli,
            ["tool", "code", "run_python", "--arg", "code=print(1)", "--yes"],
        )

    assert result.exit_code == 0
    assert execute_tool.call_args.kwargs["auto_approve"] is True


def test_permissions_explain_outputs_risk_json():
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["permissions", "explain", "docker", "docker_run", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["risk"] == "critical"
    assert payload["requires_confirmation"] is True


def test_traces_summary_outputs_json(tmp_path):
    runner = CliRunner()
    config_path = tmp_path / "config.yaml"
    audit_path = tmp_path / "audit.jsonl"
    config_path.write_text(
        f"home_dir: {tmp_path}\nsecurity:\n  audit_path: {audit_path}\n",
        encoding="utf-8",
    )
    audit_path.write_text(
        json.dumps(
            {
                "decision": "completed",
                "skill": "math",
                "source": "cli",
                "duration_ms": 12,
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        ["traces", "summary", "--json"],
        env={"R_CLI_CONFIG": str(config_path)},
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["completed"] == 1


def test_workflow_init_validate_and_run(tmp_path):
    runner = CliRunner()
    path = tmp_path / "workflow.yaml"

    initialized = runner.invoke(cli, ["workflow", "init", str(path)])
    validated = runner.invoke(cli, ["workflow", "validate", str(path), "--json"])
    executed = runner.invoke(cli, ["workflow", "run", str(path), "--json"])

    assert initialized.exit_code == 0
    assert json.loads(validated.output)["valid"] is True
    payload = json.loads(executed.output)
    assert executed.exit_code == 0
    assert payload["status"] == "completed"
    assert payload["steps"][-1]["result"] == 84


def test_agent_os_manifest_lifecycle(tmp_path):
    runner = CliRunner()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"home_dir: {tmp_path / 'home'}\n", encoding="utf-8")
    environment = {"R_CLI_CONFIG": str(config_path)}
    manifest = tmp_path / "agent.yaml"

    initialized = runner.invoke(cli, ["os", "init", str(manifest)], env=environment)
    installed = runner.invoke(
        cli,
        ["os", "agent", "install", str(manifest)],
        env=environment,
    )
    listed = runner.invoke(cli, ["os", "agent", "list", "--json"], env=environment)
    status = runner.invoke(cli, ["os", "status", "--json"], env=environment)

    assert initialized.exit_code == 0
    assert installed.exit_code == 0
    assert json.loads(listed.output)[0]["name"] == "researcher"
    assert json.loads(status.output)["agents"] == 1


def test_agent_os_security_outputs_json(tmp_path):
    runner = CliRunner()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"home_dir: {tmp_path / 'home'}\n", encoding="utf-8")

    result = runner.invoke(
        cli,
        ["os", "security", "--json"],
        env={"R_CLI_CONFIG": str(config_path)},
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["checks"][0]["name"] == "Local LLM endpoint"


def test_agent_os_cancel_marks_running_task(tmp_path):
    runner = CliRunner()
    config_path = tmp_path / "config.yaml"
    home = tmp_path / "home"
    config_path.write_text(f"home_dir: {home}\n", encoding="utf-8")
    environment = {"R_CLI_CONFIG": str(config_path)}

    from r_cli.agent_os import AgentManifest, AgentOS
    from r_cli.core.config import Config

    runtime = AgentOS(Config(home_dir=str(home)))
    runtime.install(AgentManifest("worker", "Does work"))
    with runtime._connect() as connection:
        connection.execute(
            """
            INSERT INTO tasks(id, agent_name, input, status, created_at, started_at)
            VALUES ('task123', 'worker', 'work', 'running', 'now', 'now')
            """
        )

    result = runner.invoke(
        cli,
        ["os", "cancel", "task123", "--reason", "stop now", "--json"],
        env=environment,
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "cancelled"
    assert payload["error"] == "stop now"


def test_agent_os_pause_and_resume_task(tmp_path):
    runner = CliRunner()
    config_path = tmp_path / "config.yaml"
    home = tmp_path / "home"
    config_path.write_text(f"home_dir: {home}\n", encoding="utf-8")
    environment = {"R_CLI_CONFIG": str(config_path)}

    from r_cli.agent_os import AgentManifest, AgentOS
    from r_cli.core.config import Config

    runtime = AgentOS(Config(home_dir=str(home)))
    runtime.install(AgentManifest("worker", "Does work"))
    with runtime._connect() as connection:
        connection.execute(
            """
            INSERT INTO tasks(id, agent_name, input, status, created_at)
            VALUES ('task123', 'worker', 'work', 'queued', 'now')
            """
        )

    paused = runner.invoke(
        cli,
        ["os", "pause", "task123", "--reason", "needs review", "--json"],
        env=environment,
    )
    resumed = runner.invoke(
        cli,
        ["os", "resume", "task123", "--json"],
        env=environment,
    )

    assert paused.exit_code == 0
    assert json.loads(paused.output)["status"] == "paused"
    assert json.loads(paused.output)["error"] == "needs review"
    assert resumed.exit_code == 0
    assert json.loads(resumed.output)["status"] == "queued"


def test_serve_refuses_network_bind_without_explicit_expose():
    runner = CliRunner()

    result = runner.invoke(cli, ["serve", "--host", "0.0.0.0"])

    assert result.exit_code != 0
    assert "--expose" in result.output


def test_mcp_add_and_list(tmp_path):
    runner = CliRunner()
    config_path = tmp_path / "config.yaml"
    environment = {"R_CLI_CONFIG": str(config_path)}

    added = runner.invoke(
        cli,
        [
            "mcp",
            "add",
            "demo",
            "--command",
            "uvx",
            "--arg",
            "demo-server",
            "--env",
            "MODE=test",
        ],
        env=environment,
    )
    listed = runner.invoke(cli, ["mcp", "list", "--json"], env=environment)

    assert added.exit_code == 0
    payload = json.loads(listed.output)
    assert payload["demo"]["command"] == "uvx"
    assert payload["demo"]["args"] == ["demo-server"]
    assert payload["demo"]["env"] == {"MODE": "test"}


def test_project_inspect_outputs_json(tmp_path):
    runner = CliRunner()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")

    result = runner.invoke(cli, ["project", "inspect", str(tmp_path), "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output)["stacks"] == ["Python"]


def test_project_init_creates_local_profile(tmp_path):
    runner = CliRunner()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")

    result = runner.invoke(cli, ["project", "init", str(tmp_path)])

    assert result.exit_code == 0
    assert (tmp_path / ".r-cli.yaml").exists()


def test_pdf_reads_content_from_file(tmp_path):
    runner = CliRunner()
    markdown = tmp_path / "report.md"
    markdown.write_text("# Report\n\nHello")

    with patch("r_cli.main.create_agent") as create_agent:
        result = runner.invoke(cli, ["pdf", "--file", str(markdown), "--author", "Ramon"])

    assert result.exit_code == 0
    create_agent.assert_called_once_with(selected_skills=["pdf"])
    create_agent.return_value.run_skill_directly.assert_called_once_with(
        "pdf",
        content="# Report\n\nHello",
        title=None,
        output=None,
        template="minimal",
        author="Ramon",
    )


def test_known_commands_are_not_treated_as_chat():
    runner = CliRunner()

    with patch("r_cli.main.create_agent") as create_agent:
        create_agent.return_value.skills = {}
        result = runner.invoke(cli, ["skills"])

    assert result.exit_code == 0
    create_agent.assert_called_once_with()


def test_chat_accepts_stream_option_after_subcommand():
    runner = CliRunner()

    with patch("r_cli.main.single_query") as single_query:
        result = runner.invoke(cli, ["chat", "--no-stream", "hello"])

    assert result.exit_code == 0
    single_query.assert_called_once_with("hello", "ps2", True, None, False, False)


def test_config_path_uses_environment_override():
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["config", "--path"],
        env={"R_CLI_CONFIG": "/tmp/r-cli-test.yaml"},
    )

    assert result.exit_code == 0
    assert result.output.strip() == "/tmp/r-cli-test.yaml"


def test_doctor_json_is_machine_readable():
    runner = CliRunner()
    checks = [Diagnostic("Python", "ok", "3.12")]

    with patch("r_cli.diagnostics.collect_diagnostics", return_value=checks):
        result = runner.invoke(cli, ["doctor", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "status": "ok",
        "checks": [
            {
                "name": "Python",
                "status": "ok",
                "message": "3.12",
                "hint": None,
            }
        ],
    }


def test_status_is_an_alias_for_doctor():
    runner = CliRunner()
    checks = [Diagnostic("Python", "ok", "3.12")]

    with patch("r_cli.diagnostics.collect_diagnostics", return_value=checks):
        result = runner.invoke(cli, ["status", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "ok"


def test_completion_generates_shell_script():
    runner = CliRunner()

    result = runner.invoke(cli, ["completion", "zsh"])

    assert result.exit_code == 0
    assert "_r_completion" in result.output


def test_piped_input_is_treated_as_chat_without_animation():
    runner = CliRunner()

    with patch("r_cli.main.single_query") as single_query:
        result = runner.invoke(cli, input="summarize this\n")

    assert result.exit_code == 0
    single_query.assert_called_once_with("summarize this", "ps2", False, None, True, False)


def test_global_stream_option_is_forwarded_to_chat():
    runner = CliRunner()

    with patch("r_cli.main.single_query") as single_query:
        result = runner.invoke(cli, ["--no-stream", "chat", "hello"])

    assert result.exit_code == 0
    single_query.assert_called_once_with("hello", "ps2", True, None, False, False)
