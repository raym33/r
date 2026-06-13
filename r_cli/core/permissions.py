"""Local permission policy and audit trail for tool execution."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from r_cli.core.config import Config


class RiskLevel(str, Enum):
    """Execution risk used by the local CLI policy."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


SKILL_RISKS: dict[str, RiskLevel] = {
    "pdf": RiskLevel.LOW,
    "pdftools": RiskLevel.MEDIUM,
    "resume": RiskLevel.LOW,
    "markdown": RiskLevel.LOW,
    "json": RiskLevel.LOW,
    "yaml": RiskLevel.LOW,
    "text": RiskLevel.LOW,
    "math": RiskLevel.LOW,
    "datetime": RiskLevel.LOW,
    "semver": RiskLevel.LOW,
    "mime": RiskLevel.LOW,
    "ocr": RiskLevel.LOW,
    "translate": RiskLevel.LOW,
    "weather": RiskLevel.LOW,
    "fs": RiskLevel.MEDIUM,
    "archive": RiskLevel.MEDIUM,
    "sql": RiskLevel.MEDIUM,
    "rag": RiskLevel.MEDIUM,
    "http": RiskLevel.MEDIUM,
    "web": RiskLevel.MEDIUM,
    "websearch": RiskLevel.MEDIUM,
    "calendar": RiskLevel.MEDIUM,
    "clipboard": RiskLevel.MEDIUM,
    "msoffice": RiskLevel.MEDIUM,
    "image": RiskLevel.MEDIUM,
    "audio": RiskLevel.MEDIUM,
    "video": RiskLevel.MEDIUM,
    "code": RiskLevel.HIGH,
    "git": RiskLevel.HIGH,
    "multiagent": RiskLevel.HIGH,
    "imagegen": RiskLevel.HIGH,
    "screenshot": RiskLevel.HIGH,
    "plugin": RiskLevel.CRITICAL,
    "docker": RiskLevel.CRITICAL,
    "ssh": RiskLevel.CRITICAL,
    "email": RiskLevel.CRITICAL,
    "power": RiskLevel.CRITICAL,
    "p2p": RiskLevel.CRITICAL,
    "distributed_ai": RiskLevel.CRITICAL,
}

READ_ONLY_HINTS = {
    "check",
    "compare",
    "detect",
    "find",
    "get",
    "info",
    "inspect",
    "list",
    "parse",
    "preview",
    "read",
    "search",
    "show",
    "status",
    "validate",
}

CRITICAL_HINTS = {
    "delete",
    "disable",
    "enable",
    "execute",
    "install",
    "kill",
    "push",
    "reboot",
    "remove",
    "run",
    "send",
    "shutdown",
    "uninstall",
}

HIGH_HINTS = {
    "add",
    "commit",
    "create",
    "deploy",
    "extract",
    "generate",
    "merge",
    "move",
    "pull",
    "rotate",
    "split",
    "update",
    "watermark",
    "write",
}


class PermissionDeniedError(RuntimeError):
    """Raised when local policy rejects a tool execution."""


@dataclass
class PermissionRequest:
    """A permission decision presented to a user or audit log."""

    skill: str
    tool: str
    risk: RiskLevel
    arguments: dict[str, Any]
    reason: str

    @property
    def target(self) -> str:
        return f"{self.skill}.{self.tool}"


ApprovalCallback = Callable[[PermissionRequest], bool]


def classify_risk(
    skill_name: str,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> RiskLevel:
    """Classify a call using skill defaults and action-oriented tool names."""
    base = SKILL_RISKS.get(skill_name, RiskLevel.HIGH)
    action_text = " ".join(
        str(value)
        for key, value in (arguments or {}).items()
        if key.lower() in {"action", "operation", "mode"}
    )
    tokens = set(
        f"{tool_name} {action_text}".lower().replace("-", "_").replace(" ", "_").split("_")
    )

    if tokens & CRITICAL_HINTS:
        return max(base, RiskLevel.CRITICAL, key=_risk_value)
    if tokens & HIGH_HINTS:
        return max(base, RiskLevel.HIGH, key=_risk_value)
    if tokens & READ_ONLY_HINTS:
        return min(base, RiskLevel.MEDIUM, key=_risk_value)
    return base


def _risk_value(risk: RiskLevel) -> int:
    return {
        RiskLevel.LOW: 0,
        RiskLevel.MEDIUM: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.CRITICAL: 3,
    }[risk]


class PermissionManager:
    """Authorize and audit local skill/tool execution."""

    def __init__(
        self,
        config: Config,
        approval_callback: ApprovalCallback | None = None,
        auto_approve: bool = False,
    ):
        self.config = config
        self.security = config.security
        self.approval_callback = approval_callback
        self.auto_approve = auto_approve

    def authorize(
        self,
        skill_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> PermissionRequest:
        """Authorize a call or raise PermissionDeniedError."""
        arguments = arguments or {}
        target = f"{skill_name}.{tool_name}"
        risk = classify_risk(skill_name, tool_name, arguments)
        audit_arguments = _redact_arguments(arguments)

        if skill_name in self.security.denied_skills or target in self.security.denied_tools:
            return self._deny(
                skill_name,
                tool_name,
                risk,
                audit_arguments,
                "explicitly denied by policy",
            )

        if skill_name in self.security.allowed_skills or target in self.security.allowed_tools:
            request = PermissionRequest(
                skill_name, tool_name, risk, audit_arguments, "explicitly allowed by policy"
            )
            self._audit(request, "allowed")
            return request

        mode = self.security.mode
        requires_confirmation = (
            skill_name in self.config.skills.require_confirmation
            or risk.value in self.security.confirm_risk
        )

        if mode == "permissive" or not requires_confirmation:
            request = PermissionRequest(
                skill_name,
                tool_name,
                risk,
                audit_arguments,
                "allowed by policy",
            )
            self._audit(request, "allowed")
            return request

        if mode == "strict":
            return self._deny(
                skill_name,
                tool_name,
                risk,
                audit_arguments,
                "strict mode blocks actions requiring confirmation",
            )

        request = PermissionRequest(
            skill_name,
            tool_name,
            risk,
            audit_arguments,
            f"{risk.value}-risk action requires approval",
        )
        approved = self.auto_approve or (
            self.approval_callback is not None and self.approval_callback(request)
        )
        if not approved:
            return self._deny(
                skill_name,
                tool_name,
                risk,
                audit_arguments,
                "approval was not granted",
            )

        self._audit(request, "approved")
        return request

    def execute(
        self,
        skill_name: str,
        tool_name: str,
        handler: Callable[..., Any],
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Authorize, execute, and audit a handler."""
        arguments = arguments or {}
        request = self.authorize(skill_name, tool_name, arguments)
        try:
            result = handler(**arguments)
        except Exception as exc:
            self._audit(request, "error", error=str(exc))
            raise
        self._audit(request, "completed")
        return result

    def wrap(
        self,
        skill_name: str,
        tool_name: str,
        handler: Callable[..., Any],
    ) -> Callable[..., Any]:
        """Return a guarded tool handler."""

        def guarded(**kwargs: Any) -> Any:
            return self.execute(skill_name, tool_name, handler, kwargs)

        return guarded

    def _deny(
        self,
        skill_name: str,
        tool_name: str,
        risk: RiskLevel,
        arguments: dict[str, Any],
        reason: str,
    ) -> PermissionRequest:
        request = PermissionRequest(skill_name, tool_name, risk, arguments, reason)
        self._audit(request, "denied")
        raise PermissionDeniedError(
            f"Permission denied for {request.target} ({risk.value} risk): {reason}"
        )

    def _audit(
        self,
        request: PermissionRequest,
        decision: str,
        error: str | None = None,
    ) -> None:
        if not self.security.audit_enabled:
            return

        path = Path(self.security.audit_path).expanduser()
        if not path.is_absolute():
            path = Path(self.config.home_dir).expanduser() / path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **asdict(request),
            "risk": request.risk.value,
            "decision": decision,
        }
        if error:
            payload["error"] = error
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")


def _redact_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Remove common secrets before prompts and audit persistence."""
    sensitive_tokens = ("password", "secret", "token", "api_key", "authorization", "credential")

    def redact(value: Any, key: str = "") -> Any:
        if any(token in key.lower() for token in sensitive_tokens):
            return "[REDACTED]"
        if isinstance(value, dict):
            return {
                item_key: redact(item_value, item_key) for item_key, item_value in value.items()
            }
        if isinstance(value, list):
            return [redact(item) for item in value]
        return value

    return {key: redact(value, key) for key, value in arguments.items()}
