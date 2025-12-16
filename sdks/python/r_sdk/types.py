"""Type definitions for R CLI SDK."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class ChatMessage:
    """A chat message."""

    role: str  # "user", "assistant", "system"
    content: str


@dataclass
class ToolCall:
    """A tool call made during chat."""

    name: str
    arguments: dict[str, Any]
    result: Any | None = None


@dataclass
class ChatResponse:
    """Response from chat completion."""

    message: str
    skill_used: str | None = None
    tools_called: list[ToolCall] | None = None
    model: str | None = None
    usage: dict[str, int] | None = None


@dataclass
class ToolInfo:
    """Information about a skill tool."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class SkillInfo:
    """Information about a skill."""

    name: str
    description: str
    version: str
    category: str
    enabled: bool
    tools: list[ToolInfo]


@dataclass
class LLMStatus:
    """LLM connection status."""

    connected: bool
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None


@dataclass
class StatusResponse:
    """Server status response."""

    status: str  # "healthy", "degraded", "unhealthy"
    version: str
    uptime_seconds: float
    llm: LLMStatus
    skills_loaded: int
    timestamp: str


@dataclass
class AuthUser:
    """Authenticated user info."""

    user_id: str
    username: str
    scopes: list[str]
    auth_type: str


@dataclass
class APIKeyInfo:
    """API key information."""

    key_id: str
    name: str
    scopes: list[str]
    created_at: datetime
    last_used: datetime | None = None


@dataclass
class AuditEvent:
    """Audit log event."""

    timestamp: str
    action: str
    severity: str
    success: bool
    username: str | None = None
    resource: str | None = None
    client_ip: str | None = None
    auth_type: str | None = None
    duration_ms: float | None = None
    error_message: str | None = None
