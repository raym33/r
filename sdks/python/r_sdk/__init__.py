"""R CLI Python SDK - Client library for the R CLI API."""

from .client import AsyncRClient, RClient
from .exceptions import APIError, AuthError, RateLimitError, RError
from .types import (
    APIKeyInfo,
    AuditEvent,
    AuthUser,
    ChatMessage,
    ChatResponse,
    SkillInfo,
    StatusResponse,
)

__version__ = "0.1.0"
__all__ = [
    "RClient",
    "AsyncRClient",
    "ChatMessage",
    "ChatResponse",
    "SkillInfo",
    "StatusResponse",
    "AuthUser",
    "APIKeyInfo",
    "AuditEvent",
    "RError",
    "AuthError",
    "RateLimitError",
    "APIError",
]
