"""R CLI Python SDK - Client library for the R CLI API."""

from .client import RClient, AsyncRClient
from .types import (
    ChatMessage,
    ChatResponse,
    SkillInfo,
    StatusResponse,
    AuthUser,
    APIKeyInfo,
    AuditEvent,
)
from .exceptions import RError, AuthError, RateLimitError, APIError

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
