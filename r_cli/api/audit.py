"""
Audit logging for R CLI API.

Logs all API operations for security and compliance.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel

if TYPE_CHECKING:
    from fastapi import Request


class AuditAction(str, Enum):
    """Types of auditable actions."""

    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"
    AUTH_TOKEN_CREATED = "auth.token_created"
    AUTH_TOKEN_REVOKED = "auth.token_revoked"

    # API Key management
    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"
    API_KEY_DELETED = "api_key.deleted"
    API_KEY_USED = "api_key.used"

    # User management
    USER_CREATED = "user.created"
    USER_DELETED = "user.deleted"
    USER_UPDATED = "user.updated"

    # Chat operations
    CHAT_REQUEST = "chat.request"
    CHAT_RESPONSE = "chat.response"
    CHAT_ERROR = "chat.error"

    # Skill operations
    SKILL_CALLED = "skill.called"
    SKILL_COMPLETED = "skill.completed"
    SKILL_ERROR = "skill.error"
    SKILL_DENIED = "skill.denied"

    # Tool operations
    TOOL_CALLED = "tool.called"
    TOOL_COMPLETED = "tool.completed"
    TOOL_ERROR = "tool.error"

    # Rate limiting
    RATE_LIMIT_EXCEEDED = "rate_limit.exceeded"

    # System
    SERVER_STARTED = "server.started"
    SERVER_STOPPED = "server.stopped"
    CONFIG_CHANGED = "config.changed"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEvent(BaseModel):
    """An audit log event."""

    timestamp: datetime
    action: AuditAction
    severity: AuditSeverity = AuditSeverity.INFO

    # Actor information
    user_id: Optional[str] = None
    username: Optional[str] = None
    auth_type: Optional[str] = None  # jwt, api_key, none
    client_ip: Optional[str] = None

    # Request information
    request_id: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None

    # Action details
    resource: Optional[str] = None  # skill name, endpoint, etc.
    resource_id: Optional[str] = None
    details: Optional[dict[str, Any]] = None

    # Result
    success: bool = True
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None


class AuditLogger:
    """Audit logger that writes to file and optionally to external systems."""

    def __init__(
        self,
        log_dir: Optional[str] = None,
        log_file: str = "audit.log",
        json_format: bool = True,
        max_file_size_mb: int = 100,
        backup_count: int = 10,
    ):
        self.log_dir = Path(log_dir or os.path.expanduser("~/.r-cli/logs"))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / log_file
        self.json_format = json_format

        # Set up logging
        self.logger = logging.getLogger("r_cli.audit")
        self.logger.setLevel(logging.INFO)

        # File handler with rotation
        from logging.handlers import RotatingFileHandler

        handler = RotatingFileHandler(
            self.log_file,
            maxBytes=max_file_size_mb * 1024 * 1024,
            backupCount=backup_count,
        )

        if json_format:
            handler.setFormatter(logging.Formatter("%(message)s"))
        else:
            handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

        self.logger.addHandler(handler)

        # Also log to stderr for critical events
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(logging.Formatter("[AUDIT] %(asctime)s - %(message)s"))
        self.logger.addHandler(console_handler)

    def log(self, event: AuditEvent):
        """Log an audit event."""
        if self.json_format:
            log_data = event.model_dump(mode="json")
            log_data["timestamp"] = event.timestamp.isoformat()
            message = json.dumps(log_data)
        else:
            message = (
                f"{event.action.value} | "
                f"user={event.username or 'anonymous'} | "
                f"resource={event.resource} | "
                f"success={event.success}"
            )
            if event.error_message:
                message += f" | error={event.error_message}"

        # Map severity to logging level
        level_map = {
            AuditSeverity.DEBUG: logging.DEBUG,
            AuditSeverity.INFO: logging.INFO,
            AuditSeverity.WARNING: logging.WARNING,
            AuditSeverity.ERROR: logging.ERROR,
            AuditSeverity.CRITICAL: logging.CRITICAL,
        }

        self.logger.log(level_map[event.severity], message)

    def log_action(
        self,
        action: AuditAction,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        auth_type: Optional[str] = None,
        client_ip: Optional[str] = None,
        request_id: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        duration_ms: Optional[float] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
    ):
        """Convenience method to log an action."""
        event = AuditEvent(
            timestamp=datetime.now(),
            action=action,
            severity=severity,
            user_id=user_id,
            username=username,
            auth_type=auth_type,
            client_ip=client_ip,
            request_id=request_id,
            method=method,
            path=path,
            resource=resource,
            resource_id=resource_id,
            details=details,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
        )
        self.log(event)

    def log_request(
        self,
        request: Request,
        action: AuditAction,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        auth_type: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[dict] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ):
        """Log an action from a FastAPI request."""
        # Extract client IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else None

        # Extract request ID
        request_id = request.headers.get("X-Request-ID")

        self.log_action(
            action=action,
            user_id=user_id,
            username=username,
            auth_type=auth_type,
            client_ip=client_ip,
            request_id=request_id,
            method=request.method,
            path=str(request.url.path),
            resource=resource,
            details=details,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
        )

    def get_recent_events(
        self,
        limit: int = 100,
        action: Optional[AuditAction] = None,
        user_id: Optional[str] = None,
        success: Optional[bool] = None,
    ) -> list[AuditEvent]:
        """Read recent events from the log file."""
        events = []

        if not self.log_file.exists():
            return events

        # Read last N lines
        with open(self.log_file) as f:
            lines = f.readlines()

        for line in reversed(lines[-limit * 2 :]):  # Read extra in case of filtering
            if len(events) >= limit:
                break

            try:
                if self.json_format:
                    data = json.loads(line.strip())
                    event = AuditEvent(**data)
                else:
                    continue  # Can't parse non-JSON format easily

                # Apply filters
                if action and event.action != action:
                    continue
                if user_id and event.user_id != user_id:
                    continue
                if success is not None and event.success != success:
                    continue

                events.append(event)
            except (json.JSONDecodeError, ValueError):
                continue

        return events


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def audit_log(
    action: AuditAction,
    **kwargs,
):
    """Convenience function to log an audit event."""
    logger = get_audit_logger()
    logger.log_action(action, **kwargs)


# Decorator for auditing function calls
def audited(action: AuditAction, resource_param: Optional[str] = None):
    """
    Decorator to audit function calls.

    Usage:
        @audited(AuditAction.SKILL_CALLED, resource_param="skill_name")
        async def call_skill(skill_name: str, ...):
            ...
    """
    import functools
    import time

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            resource = kwargs.get(resource_param) if resource_param else None
            logger = get_audit_logger()

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                logger.log_action(
                    action=action,
                    resource=resource,
                    success=True,
                    duration_ms=duration_ms,
                )

                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                logger.log_action(
                    action=action,
                    resource=resource,
                    success=False,
                    error_message=str(e),
                    duration_ms=duration_ms,
                    severity=AuditSeverity.ERROR,
                )

                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            resource = kwargs.get(resource_param) if resource_param else None
            logger = get_audit_logger()

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                logger.log_action(
                    action=action,
                    resource=resource,
                    success=True,
                    duration_ms=duration_ms,
                )

                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                logger.log_action(
                    action=action,
                    resource=resource,
                    success=False,
                    error_message=str(e),
                    duration_ms=duration_ms,
                    severity=AuditSeverity.ERROR,
                )

                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
