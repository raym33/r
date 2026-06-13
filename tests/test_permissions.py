"""Tests for local tool permissions and audit logging."""

import json
from pathlib import Path

import pytest

from r_cli.core.config import Config
from r_cli.core.permissions import (
    PermissionDeniedError,
    PermissionManager,
    RiskLevel,
    classify_risk,
)


def permission_config(tmp_path: Path) -> Config:
    config = Config(
        home_dir=str(tmp_path),
        output_dir=str(tmp_path / "output"),
        skills_dir=str(tmp_path / "skills"),
    )
    config.security.audit_path = "audit.jsonl"
    return config


def test_read_only_tool_reduces_skill_risk():
    assert classify_risk("docker", "docker_info") == RiskLevel.MEDIUM
    assert classify_risk("plugin", "plugin_list") == RiskLevel.MEDIUM


def test_dangerous_action_escalates_risk():
    assert classify_risk("fs", "delete_file") == RiskLevel.CRITICAL
    assert classify_risk("code", "run_code") == RiskLevel.CRITICAL
    assert classify_risk("fs", "direct", {"action": "delete"}) == RiskLevel.CRITICAL


def test_non_interactive_high_risk_action_is_denied(tmp_path: Path):
    manager = PermissionManager(permission_config(tmp_path))

    with pytest.raises(PermissionDeniedError, match="approval was not granted"):
        manager.execute("code", "write_code", lambda **_: "written", {"code": "x"})


def test_callback_can_approve_action(tmp_path: Path):
    requests = []
    manager = PermissionManager(
        permission_config(tmp_path),
        approval_callback=lambda request: requests.append(request) or True,
    )

    result = manager.execute("code", "write_code", lambda **_: "written", {"code": "x"})

    assert result == "written"
    assert requests[0].risk == RiskLevel.HIGH


def test_explicit_deny_wins_over_auto_approve(tmp_path: Path):
    config = permission_config(tmp_path)
    config.security.denied_tools = ["code.write_code"]
    manager = PermissionManager(config, auto_approve=True)

    with pytest.raises(PermissionDeniedError, match="explicitly denied"):
        manager.execute("code", "write_code", lambda **_: "written", {"code": "x"})


def test_audit_log_records_decisions(tmp_path: Path):
    config = permission_config(tmp_path)
    manager = PermissionManager(config, auto_approve=True)

    manager.execute("code", "write_code", lambda **_: "written", {"code": "x"})

    records = [
        json.loads(line)
        for line in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert records[-1]["decision"] == "completed"
    assert records[-1]["skill"] == "code"
    assert records[-1]["tool"] == "write_code"
    assert records[-1]["trace_id"]
    assert records[-1]["source"] == "local"
    assert records[-1]["duration_ms"] >= 0


def test_audit_log_redacts_secrets(tmp_path: Path):
    config = permission_config(tmp_path)
    manager = PermissionManager(config, auto_approve=True)

    manager.execute(
        "http",
        "request",
        lambda **_: "ok",
        {"api_key": "top-secret", "headers": {"Authorization": "Bearer secret"}},
    )

    records = [
        json.loads(line)
        for line in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert records[-1]["arguments"]["api_key"] == "[REDACTED]"
    assert records[-1]["arguments"]["headers"]["Authorization"] == "[REDACTED]"
