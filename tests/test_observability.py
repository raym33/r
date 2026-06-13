"""Tests for local execution trace queries."""

import json
from pathlib import Path

from r_cli.core.config import Config
from r_cli.observability import TraceStore


def trace_config(tmp_path: Path) -> Config:
    config = Config(home_dir=str(tmp_path))
    config.security.audit_path = "audit.jsonl"
    return config


def write_records(config: Config, records: list[dict]) -> None:
    path = Path(config.home_dir) / config.security.audit_path
    path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")


def test_summary_uses_terminal_events_only(tmp_path):
    config = trace_config(tmp_path)
    write_records(
        config,
        [
            {"decision": "allowed", "skill": "math", "source": "cli"},
            {
                "decision": "completed",
                "skill": "math",
                "source": "cli",
                "duration_ms": 10,
            },
            {
                "decision": "error",
                "skill": "pdf",
                "source": "agent",
                "duration_ms": 30,
            },
            {"decision": "denied", "skill": "docker", "source": "cli"},
        ],
    )

    summary = TraceStore(config).summary()

    assert summary["total"] == 3
    assert summary["success_rate"] == 50.0
    assert summary["average_duration_ms"] == 20.0
    assert summary["by_source"] == {"cli": 2, "agent": 1}


def test_read_filters_and_limits(tmp_path):
    config = trace_config(tmp_path)
    write_records(
        config,
        [
            {"decision": "completed", "skill": "math", "risk": "low"},
            {"decision": "completed", "skill": "pdf", "risk": "low"},
            {"decision": "error", "skill": "pdf", "risk": "low"},
        ],
    )

    records = TraceStore(config).read(limit=1, skill="pdf", terminal_only=True)

    assert records == [{"decision": "error", "skill": "pdf", "risk": "low"}]


def test_export_csv_serializes_nested_values(tmp_path):
    config = trace_config(tmp_path)
    write_records(config, [{"decision": "completed", "arguments": {"value": 1}}])
    output = tmp_path / "traces.csv"

    count = TraceStore(config).export(output, "csv")

    assert count == 1
    assert '"{""value"": 1}"' in output.read_text(encoding="utf-8")
