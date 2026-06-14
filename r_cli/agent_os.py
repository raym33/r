"""Persistent process and identity runtime for AI agents."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from r_cli.core.config import Config
    from r_cli.core.permissions import ApprovalCallback

AGENT_KINDS = {"assistant", "workflow"}
TASK_STATES = {"queued", "paused", "running", "completed", "failed", "cancelled"}
TERMINAL_TASK_STATES = {"completed", "failed", "cancelled"}
REDACTED = "[redacted]"


class AgentOSError(RuntimeError):
    """Raised when the Agent OS runtime cannot complete an operation."""


@dataclass
class AgentManifest:
    """Persistent identity and capabilities for one agent."""

    name: str
    description: str
    kind: str = "assistant"
    system_prompt: str = "You are a focused local AI agent."
    skills: list[str] | None = None
    workflow: str | None = None
    network_access: bool = False
    allowed_hosts: list[str] | None = None
    filesystem_roots: list[str] | None = None
    unsafe_capabilities: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentOS:
    """SQLite-backed registry and task supervisor."""

    def __init__(self, config: Config):
        self.config = config
        home = Path(config.home_dir).expanduser()
        home.mkdir(parents=True, exist_ok=True)
        self.path = home / "agent-os.db"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    name TEXT PRIMARY KEY,
                    manifest TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    input TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    FOREIGN KEY(agent_name) REFERENCES agents(name)
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    agent_name TEXT,
                    task_id TEXT,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id);
                """
            )

    def install(self, manifest: AgentManifest, replace: bool = False) -> None:
        """Install an agent identity from a validated manifest."""
        validate_agent_capabilities(manifest)
        now = _now()
        payload = json.dumps(manifest.to_dict())
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT 1 FROM agents WHERE name = ?", (manifest.name,)
            ).fetchone()
            if existing and not replace:
                raise AgentOSError(f"Agent already exists: {manifest.name}")
            if existing:
                connection.execute(
                    "UPDATE agents SET manifest = ?, updated_at = ? WHERE name = ?",
                    (payload, now, manifest.name),
                )
            else:
                connection.execute(
                    "INSERT INTO agents(name, manifest, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (manifest.name, payload, now, now),
                )
            self._emit(
                connection,
                "agent.installed",
                manifest.name,
                None,
                {"kind": manifest.kind, "skills": manifest.skills or []},
            )

    def remove(self, name: str) -> None:
        """Remove an agent that has no task history."""
        with self._connect() as connection:
            try:
                cursor = connection.execute("DELETE FROM agents WHERE name = ?", (name,))
            except sqlite3.IntegrityError as exc:
                raise AgentOSError(
                    f"Agent '{name}' has task history and cannot be removed"
                ) from exc
            if cursor.rowcount == 0:
                raise AgentOSError(f"Unknown agent: {name}")
            self._emit(connection, "agent.removed", name, None, {})

    def get_agent(self, name: str) -> AgentManifest:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT manifest FROM agents WHERE name = ?", (name,)
            ).fetchone()
        if row is None:
            raise AgentOSError(f"Unknown agent: {name}")
        return AgentManifest(**json.loads(row["manifest"]))

    def list_agents(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT a.name, a.manifest, a.created_at, a.updated_at,
                       COUNT(t.id) AS task_count,
                       SUM(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END) AS completed
                FROM agents a
                LEFT JOIN tasks t ON t.agent_name = a.name
                GROUP BY a.name
                ORDER BY a.name
                """
            ).fetchall()
        return [
            {
                **json.loads(row["manifest"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "task_count": row["task_count"],
                "completed": row["completed"] or 0,
            }
            for row in rows
        ]

    def run(
        self,
        name: str,
        task_input: str,
        approval_callback: ApprovalCallback | None = None,
        auto_approve: bool = False,
    ) -> dict[str, Any]:
        """Create and synchronously supervise one task."""
        task = self.create_task(name, task_input)
        return self.run_task(
            task["id"],
            approval_callback=approval_callback,
            auto_approve=auto_approve,
        )

    def create_task(self, name: str, task_input: str) -> dict[str, Any]:
        """Create a queued task without starting execution."""
        self.get_agent(name)
        if not task_input.strip():
            raise AgentOSError("Task input must be non-empty")
        task_id = uuid.uuid4().hex[:12]
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks(id, agent_name, input, status, created_at)
                VALUES (?, ?, ?, 'queued', ?)
                """,
                (task_id, name, task_input, _now()),
            )
            self._emit(
                connection,
                "task.queued",
                name,
                task_id,
                {"input_length": len(task_input)},
            )
        return self.get_task(task_id)

    def run_task(
        self,
        task_id: str,
        approval_callback: ApprovalCallback | None = None,
        auto_approve: bool = False,
    ) -> dict[str, Any]:
        """Run one existing queued task synchronously."""
        task = self.get_task(task_id)
        if task["status"] != "queued":
            raise AgentOSError(f"Task {task_id} is not queued")
        manifest = self.get_agent(task["agent_name"])
        if not self._set_task_state(task_id, "running"):
            raise AgentOSError(f"Task {task_id} could not enter the running state")
        try:
            if manifest.kind == "workflow":
                result = self._run_workflow_agent(
                    manifest,
                    task["input"],
                    approval_callback,
                    auto_approve,
                )
            else:
                result = self._run_assistant(
                    manifest,
                    task["input"],
                    approval_callback,
                    auto_approve,
                )
        except Exception as exc:
            self._set_task_state(task_id, "failed", error=str(exc))
            return self.get_task(task_id)

        self._set_task_state(task_id, "completed", result=result)
        return self.get_task(task_id)

    def cancel_task(self, task_id: str, reason: str = "cancelled by user") -> dict[str, Any]:
        """Mark a queued or running task as cancelled."""
        reason = reason.strip() or "cancelled by user"
        now = _now()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise AgentOSError(f"Unknown task: {task_id}")
            if row["status"] in TERMINAL_TASK_STATES:
                raise AgentOSError(f"Task {task_id} is already {row['status']}")
            connection.execute(
                """
                UPDATE tasks
                SET status = 'cancelled', error = ?, finished_at = ?
                WHERE id = ?
                """,
                (reason, now, task_id),
            )
            self._emit(
                connection,
                "task.cancelled",
                row["agent_name"],
                task_id,
                {"reason": reason, "previous_status": row["status"]},
            )
        return self.get_task(task_id)

    def pause_task(self, task_id: str, reason: str = "paused by user") -> dict[str, Any]:
        """Pause a queued task before a worker starts it."""
        reason = reason.strip() or "paused by user"
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise AgentOSError(f"Unknown task: {task_id}")
            if row["status"] in TERMINAL_TASK_STATES:
                raise AgentOSError(f"Task {task_id} is already {row['status']}")
            if row["status"] == "paused":
                raise AgentOSError(f"Task {task_id} is already paused")
            if row["status"] == "running":
                raise AgentOSError(f"Task {task_id} is already running; cancel it instead")
            connection.execute(
                """
                UPDATE tasks
                SET status = 'paused', error = ?, finished_at = NULL
                WHERE id = ?
                """,
                (reason, task_id),
            )
            self._emit(
                connection,
                "task.paused",
                row["agent_name"],
                task_id,
                {"reason": reason, "previous_status": row["status"]},
            )
        return self.get_task(task_id)

    def resume_task(self, task_id: str) -> dict[str, Any]:
        """Return a paused task to the queued state."""
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise AgentOSError(f"Unknown task: {task_id}")
            if row["status"] != "paused":
                raise AgentOSError(f"Task {task_id} is not paused")
            connection.execute(
                """
                UPDATE tasks
                SET status = 'queued', error = NULL, finished_at = NULL
                WHERE id = ?
                """,
                (task_id,),
            )
            self._emit(
                connection,
                "task.resumed",
                row["agent_name"],
                task_id,
                {"previous_status": row["status"]},
            )
        return self.get_task(task_id)

    def _run_assistant(
        self,
        manifest: AgentManifest,
        task_input: str,
        approval_callback: ApprovalCallback | None,
        auto_approve: bool,
    ) -> str:
        from r_cli.core.agent import Agent

        config = self.config.model_copy(deep=True)
        _apply_agent_security(config, manifest)
        agent = Agent(
            config,
            approval_callback=approval_callback,
            auto_approve=auto_approve,
            source=f"agent-os:{manifest.name}",
            memory_namespace=manifest.name,
        )
        agent.load_skills(verbose=False)
        agent.llm.set_system_prompt(manifest.system_prompt)
        return agent.run(task_input, show_thinking=False)

    def _run_workflow_agent(
        self,
        manifest: AgentManifest,
        task_input: str,
        approval_callback: ApprovalCallback | None,
        auto_approve: bool,
    ) -> dict[str, Any]:
        from r_cli.workflows import load_workflow, run_workflow

        if not manifest.workflow:
            raise AgentOSError(f"Workflow agent '{manifest.name}' has no workflow")
        config = self.config.model_copy(deep=True)
        _apply_agent_security(config, manifest)
        workflow = load_workflow(manifest.workflow)
        result = run_workflow(
            workflow,
            variables={"task": task_input},
            config=config,
            approval_callback=approval_callback,
            auto_approve=auto_approve,
        )
        if result.status == "error":
            failed = next(
                (step.error for step in result.steps if step.status == "error"),
                "workflow failed",
            )
            raise AgentOSError(failed)
        return result.to_dict()

    def _set_task_state(
        self,
        task_id: str,
        status: str,
        result: Any = None,
        error: str | None = None,
    ) -> bool:
        if status not in TASK_STATES:
            raise AgentOSError(f"Invalid task state: {status}")
        now = _now()
        with self._connect() as connection:
            current = connection.execute(
                "SELECT agent_name, status FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if current is None:
                raise AgentOSError(f"Unknown task: {task_id}")
            if current["status"] in TERMINAL_TASK_STATES and current["status"] != status:
                return False
            if status == "running" and current["status"] != "queued":
                return False
            if status == "running":
                connection.execute(
                    "UPDATE tasks SET status = ?, started_at = ? WHERE id = ?",
                    (status, now, task_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE tasks
                    SET status = ?, result = ?, error = ?, finished_at = ?
                    WHERE id = ?
                    """,
                    (
                        status,
                        json.dumps(result, default=str) if result is not None else None,
                        error,
                        now,
                        task_id,
                    ),
                )
            self._emit(
                connection,
                f"task.{status}",
                current["agent_name"],
                task_id,
                {"error": error} if error else {},
            )
        return True

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise AgentOSError(f"Unknown task: {task_id}")
        return _task_dict(row)

    def list_tasks(
        self,
        limit: int = 20,
        status: str | None = None,
        agent_name: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if status:
            if status not in TASK_STATES:
                raise AgentOSError(f"Invalid task state: {status}")
            clauses.append("status = ?")
            values.append(status)
        if agent_name:
            clauses.append("agent_name = ?")
            values.append(agent_name)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM tasks {where} ORDER BY created_at DESC LIMIT ?",
                values,
            ).fetchall()
        return [_task_dict(row) for row in rows]

    def list_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_event_dict(row) for row in rows]

    def export_task_capsule(
        self,
        task_id: str,
        include_content: bool = False,
    ) -> dict[str, Any]:
        """Export a privacy-preserving audit capsule for one task."""
        with self._connect() as connection:
            task_row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if task_row is None:
                raise AgentOSError(f"Unknown task: {task_id}")
            agent_row = connection.execute(
                "SELECT manifest, created_at, updated_at FROM agents WHERE name = ?",
                (task_row["agent_name"],),
            ).fetchone()
            event_rows = connection.execute(
                """
                SELECT * FROM events
                WHERE task_id = ?
                ORDER BY id ASC
                """,
                (task_id,),
            ).fetchall()

        task = _task_dict(task_row)
        manifest = json.loads(agent_row["manifest"]) if agent_row else {}
        security = _capsule_security_summary(manifest)
        if not include_content:
            task = _redact_task_content(task)
            manifest = _redact_manifest_content(manifest)

        return {
            "schema_version": 1,
            "kind": "r.agent_os.task_capsule",
            "exported_at": _now(),
            "content_included": include_content,
            "redaction": {
                "enabled": not include_content,
                "placeholder": REDACTED,
                "fields": [] if include_content else _capsule_redacted_fields(),
            },
            "task": task,
            "agent": {
                **manifest,
                "created_at": agent_row["created_at"] if agent_row else None,
                "updated_at": agent_row["updated_at"] if agent_row else None,
            },
            "security": security,
            "events": [_event_dict(row) for row in event_rows],
        }

    def status(self) -> dict[str, Any]:
        with self._connect() as connection:
            agents = connection.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
            task_rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM tasks GROUP BY status"
            ).fetchall()
            events = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        tasks = dict.fromkeys(sorted(TASK_STATES), 0)
        tasks.update({row["status"]: row["count"] for row in task_rows})
        return {
            "database": str(self.path),
            "agents": agents,
            "tasks": tasks,
            "events": events,
        }

    @staticmethod
    def _emit(
        connection: sqlite3.Connection,
        event_type: str,
        agent_name: str | None,
        task_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO events(timestamp, event_type, agent_name, task_id, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (_now(), event_type, agent_name, task_id, json.dumps(payload, default=str)),
        )


def load_agent_manifest(path: str | Path) -> AgentManifest:
    """Load and validate an agent manifest."""
    manifest_path = Path(path).expanduser().resolve()
    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AgentOSError(f"Agent manifest not found: {manifest_path}") from exc
    except yaml.YAMLError as exc:
        raise AgentOSError(f"Invalid agent manifest YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise AgentOSError("Agent manifest must be a YAML object")

    allowed = {
        "name",
        "description",
        "kind",
        "system_prompt",
        "skills",
        "workflow",
        "network_access",
        "allowed_hosts",
        "filesystem_roots",
        "unsafe_capabilities",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise AgentOSError(f"Unknown agent fields: {', '.join(sorted(unknown))}")
    name = raw.get("name")
    description = raw.get("description")
    kind = raw.get("kind", "assistant")
    skills = raw.get("skills")
    if not isinstance(name, str) or not name.strip():
        raise AgentOSError("Agent name must be a non-empty string")
    if not name.replace("-", "").replace("_", "").isalnum():
        raise AgentOSError("Agent name may contain letters, numbers, hyphens, and underscores")
    if not isinstance(description, str) or not description.strip():
        raise AgentOSError("Agent description must be a non-empty string")
    if kind not in AGENT_KINDS:
        raise AgentOSError(f"Agent kind must be one of: {', '.join(sorted(AGENT_KINDS))}")
    if skills is not None and (
        not isinstance(skills, list) or not all(isinstance(skill, str) for skill in skills)
    ):
        raise AgentOSError("Agent skills must be a list of names")
    system_prompt = raw.get("system_prompt", "You are a focused local AI agent.")
    if not isinstance(system_prompt, str) or not system_prompt.strip():
        raise AgentOSError("Agent system_prompt must be a non-empty string")

    workflow = raw.get("workflow")
    if kind == "workflow":
        if not isinstance(workflow, str) or not workflow:
            raise AgentOSError("Workflow agents require a workflow path")
        workflow_path = (manifest_path.parent / workflow).resolve()
        if not workflow_path.exists():
            raise AgentOSError(f"Agent workflow not found: {workflow_path}")
        workflow = str(workflow_path)

    network_access = raw.get("network_access", False)
    unsafe_capabilities = raw.get("unsafe_capabilities", False)
    if not isinstance(network_access, bool):
        raise AgentOSError("Agent network_access must be true or false")
    if not isinstance(unsafe_capabilities, bool):
        raise AgentOSError("Agent unsafe_capabilities must be true or false")

    allowed_hosts = raw.get("allowed_hosts", [])
    if not isinstance(allowed_hosts, list) or not all(
        isinstance(host, str) and host for host in allowed_hosts
    ):
        raise AgentOSError("Agent allowed_hosts must be a list of host names")
    from r_cli.security import normalize_host_rule

    try:
        allowed_hosts = [normalize_host_rule(host) for host in allowed_hosts]
    except ValueError as exc:
        raise AgentOSError(f"Invalid agent allowed host: {exc}") from exc
    roots = raw.get("filesystem_roots", [])
    if not isinstance(roots, list) or not all(
        isinstance(root, str) and root.strip() for root in roots
    ):
        raise AgentOSError("Agent filesystem_roots must be a list of paths")
    resolved_roots = [
        str((manifest_path.parent / root).resolve()) if not Path(root).is_absolute() else root
        for root in roots
    ]

    return AgentManifest(
        name=name.strip(),
        description=description.strip(),
        kind=kind,
        system_prompt=system_prompt.strip(),
        skills=skills,
        workflow=workflow,
        network_access=network_access,
        allowed_hosts=allowed_hosts,
        filesystem_roots=resolved_roots,
        unsafe_capabilities=unsafe_capabilities,
    )


def validate_agent_capabilities(manifest: AgentManifest) -> None:
    """Ensure native skill capabilities exist before installing an agent."""
    if not isinstance(manifest.network_access, bool):
        raise AgentOSError("Agent network_access must be true or false")
    if not isinstance(manifest.unsafe_capabilities, bool):
        raise AgentOSError("Agent unsafe_capabilities must be true or false")
    if manifest.skills is not None and (
        not isinstance(manifest.skills, list)
        or not all(isinstance(skill, str) and skill for skill in manifest.skills)
    ):
        raise AgentOSError("Agent skills must be a list of names")
    if manifest.allowed_hosts is not None and (
        not isinstance(manifest.allowed_hosts, list)
        or not all(isinstance(host, str) and host for host in manifest.allowed_hosts)
    ):
        raise AgentOSError("Agent allowed_hosts must be a list of host names")
    if manifest.filesystem_roots is not None and (
        not isinstance(manifest.filesystem_roots, list)
        or not all(isinstance(root, str) and root for root in manifest.filesystem_roots)
    ):
        raise AgentOSError("Agent filesystem_roots must be a list of paths")

    from r_cli.skills import get_all_skills

    available = {skill.name for skill in get_all_skills()}
    skills = set(manifest.skills or [])
    unknown = sorted(skills - available)
    if unknown:
        raise AgentOSError(f"Unknown agent skills: {', '.join(unknown)}")
    from r_cli.security import UNCONFINED_SKILLS

    broad = sorted(skills & UNCONFINED_SKILLS)
    if broad and not manifest.unsafe_capabilities:
        raise AgentOSError(
            "Broad host capabilities require unsafe_capabilities: true: " + ", ".join(broad)
        )
    if manifest.network_access and not manifest.allowed_hosts:
        raise AgentOSError("Network-enabled agents require at least one allowed host")
    if manifest.allowed_hosts:
        from r_cli.security import normalize_host_rule

        try:
            manifest.allowed_hosts = [normalize_host_rule(host) for host in manifest.allowed_hosts]
        except (TypeError, ValueError) as exc:
            raise AgentOSError(f"Invalid agent allowed host: {exc}") from exc


def _apply_agent_security(config: Config, manifest: AgentManifest) -> None:
    config.skills.mode = "whitelist"
    config.skills.enabled = list(manifest.skills or [])
    config.security.network_access = manifest.network_access
    config.security.allowed_hosts = manifest.allowed_hosts or []
    config.security.filesystem_roots = manifest.filesystem_roots or []
    config.security.enforce_filesystem_roots = True


def _task_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = json.loads(row["result"]) if row["result"] else None
    return {
        "id": row["id"],
        "agent_name": row["agent_name"],
        "input": row["input"],
        "status": row["status"],
        "result": result,
        "error": row["error"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


def _event_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "timestamp": row["timestamp"],
        "event_type": row["event_type"],
        "agent_name": row["agent_name"],
        "task_id": row["task_id"],
        "payload": json.loads(row["payload"]),
    }


def _redact_task_content(task: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(task)
    for field in ("input", "result", "error"):
        if redacted.get(field) is not None:
            redacted[field] = REDACTED
    return redacted


def _redact_manifest_content(manifest: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(manifest)
    for field in ("description", "system_prompt", "workflow"):
        if redacted.get(field) is not None:
            redacted[field] = REDACTED
    for field in ("allowed_hosts", "filesystem_roots"):
        if redacted.get(field):
            redacted[field] = [REDACTED]
    return redacted


def _capsule_redacted_fields() -> list[str]:
    return [
        "task.input",
        "task.result",
        "task.error",
        "agent.description",
        "agent.system_prompt",
        "agent.workflow",
        "agent.allowed_hosts",
        "agent.filesystem_roots",
    ]


def _capsule_security_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    skills = manifest.get("skills") or []
    allowed_hosts = manifest.get("allowed_hosts") or []
    filesystem_roots = manifest.get("filesystem_roots") or []
    return {
        "skills_count": len(skills),
        "network_access": bool(manifest.get("network_access", False)),
        "allowed_hosts_count": len(allowed_hosts),
        "filesystem_roots_count": len(filesystem_roots),
        "unsafe_capabilities": bool(manifest.get("unsafe_capabilities", False)),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
