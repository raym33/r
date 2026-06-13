"""Read and summarize local execution traces."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from r_cli.core.config import Config

TERMINAL_DECISIONS = {"completed", "denied", "error"}


class TraceStore:
    """Query the JSONL audit trail as execution traces."""

    def __init__(self, config: Config):
        path = Path(config.security.audit_path).expanduser()
        self.path = path if path.is_absolute() else Path(config.home_dir).expanduser() / path

    def read(
        self,
        limit: int | None = None,
        decision: str | None = None,
        risk: str | None = None,
        skill: str | None = None,
        source: str | None = None,
        terminal_only: bool = False,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        if not self.path.exists():
            return records

        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if terminal_only and record.get("decision") not in TERMINAL_DECISIONS:
                continue
            if decision and record.get("decision") != decision:
                continue
            if risk and record.get("risk") != risk:
                continue
            if skill and record.get("skill") != skill:
                continue
            if source and record.get("source", "local") != source:
                continue
            records.append(record)
        return records[-limit:] if limit else records

    def summary(self) -> dict[str, Any]:
        records = self.read(terminal_only=True)
        durations = sorted(
            float(record["duration_ms"]) for record in records if "duration_ms" in record
        )
        decisions = Counter(record.get("decision", "unknown") for record in records)
        completed = decisions["completed"]
        errors = decisions["error"]
        executed = completed + errors
        return {
            "total": len(records),
            "completed": completed,
            "errors": errors,
            "denied": decisions["denied"],
            "success_rate": round(completed / executed * 100, 2) if executed else 0.0,
            "average_duration_ms": round(sum(durations) / len(durations), 3) if durations else 0.0,
            "p50_duration_ms": _percentile(durations, 0.50),
            "p95_duration_ms": _percentile(durations, 0.95),
            "by_skill": dict(Counter(record.get("skill", "unknown") for record in records)),
            "by_source": dict(Counter(record.get("source", "local") for record in records)),
        }

    def export(self, output: Path, file_format: str) -> int:
        records = self.read()
        output.parent.mkdir(parents=True, exist_ok=True)
        if file_format == "json":
            output.write_text(json.dumps(records, indent=2, default=str) + "\n", encoding="utf-8")
        else:
            fieldnames = sorted({key for record in records for key in record})
            with output.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for record in records:
                    writer.writerow(
                        {
                            key: json.dumps(value, default=str)
                            if isinstance(value, (dict, list))
                            else value
                            for key, value in record.items()
                        }
                    )
        return len(records)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    index = min(round((len(values) - 1) * percentile), len(values) - 1)
    return round(values[index], 3)
