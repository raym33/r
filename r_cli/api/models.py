"""Pydantic models for R CLI API requests and responses."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

# ============================================================================
# Status Models
# ============================================================================


class HealthStatus(str, Enum):
    """Health status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class LLMStatus(BaseModel):
    """LLM backend status."""

    connected: bool = False
    backend: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    error: Optional[str] = None


class StatusResponse(BaseModel):
    """Response for /v1/status endpoint."""

    status: HealthStatus = HealthStatus.HEALTHY
    version: str
    uptime_seconds: float
    llm: LLMStatus
    skills_loaded: int
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# Chat Models
# ============================================================================


class ChatMessage(BaseModel):
    """A single chat message."""

    role: str = Field(..., description="Message role: system, user, or assistant")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request for /v1/chat endpoint."""

    messages: list[ChatMessage] = Field(..., description="Conversation messages")
    model: Optional[str] = Field(None, description="Override model name")
    stream: bool = Field(True, description="Enable streaming response")
    temperature: Optional[float] = Field(None, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, gt=0)
    tools_enabled: bool = Field(True, description="Allow skill/tool usage")


class ChatChoice(BaseModel):
    """A single chat completion choice."""

    index: int = 0
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatUsage(BaseModel):
    """Token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    """Non-streaming response for /v1/chat endpoint."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoice]
    usage: Optional[ChatUsage] = None


class ChatStreamDelta(BaseModel):
    """Delta content for streaming responses."""

    role: Optional[str] = None
    content: Optional[str] = None


class ChatStreamChoice(BaseModel):
    """A single streaming choice."""

    index: int = 0
    delta: ChatStreamDelta
    finish_reason: Optional[str] = None


class ChatStreamResponse(BaseModel):
    """Streaming response chunk for /v1/chat endpoint."""

    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatStreamChoice]


# ============================================================================
# Skills Models
# ============================================================================


class ToolParameter(BaseModel):
    """A tool parameter definition."""

    name: str
    type: str
    description: str
    required: bool = False
    default: Optional[Any] = None


class ToolInfo(BaseModel):
    """Information about a single tool."""

    name: str
    description: str
    parameters: list[ToolParameter] = []


class SkillInfo(BaseModel):
    """Information about a skill."""

    name: str
    description: str
    tools: list[ToolInfo] = []
    category: Optional[str] = None


class SkillsResponse(BaseModel):
    """Response for /v1/skills endpoint."""

    total: int
    skills: list[SkillInfo]


class ToolCallRequest(BaseModel):
    """Request to call a specific tool."""

    skill: str = Field(..., description="Skill name")
    tool: str = Field(..., description="Tool name within the skill")
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    """Response from a tool call."""

    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: float = 0


# ============================================================================
# Error Models
# ============================================================================


class ErrorDetail(BaseModel):
    """Error detail."""

    code: str
    message: str
    details: Optional[dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail
