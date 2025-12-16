"""R CLI API - REST API daemon for R Agent Runtime."""

from r_cli.api.server import create_app, run_server

# Auth exports
from r_cli.api.auth import (
    AuthResult,
    AuthStorage,
    Token,
    create_access_token,
    get_current_auth,
    require_auth,
    require_scopes,
)

# Permissions exports
from r_cli.api.permissions import (
    PermissionChecker,
    Scope,
    check_skill_permission,
)

# Rate limiting exports
from r_cli.api.rate_limit import (
    RateLimiter,
    RateLimitConfig,
    RateLimitMiddleware,
    get_rate_limiter,
)

# Audit exports
from r_cli.api.audit import (
    AuditAction,
    AuditEvent,
    AuditLogger,
    audit_log,
    get_audit_logger,
)

__all__ = [
    # Server
    "create_app",
    "run_server",
    # Auth
    "AuthResult",
    "AuthStorage",
    "Token",
    "create_access_token",
    "get_current_auth",
    "require_auth",
    "require_scopes",
    # Permissions
    "PermissionChecker",
    "Scope",
    "check_skill_permission",
    # Rate limiting
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitMiddleware",
    "get_rate_limiter",
    # Audit
    "AuditAction",
    "AuditEvent",
    "AuditLogger",
    "audit_log",
    "get_audit_logger",
]
