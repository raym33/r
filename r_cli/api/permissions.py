"""
Permission scopes for R CLI API.

Defines granular permissions for skills and operations.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Scope(str, Enum):
    """Available permission scopes."""

    # General scopes
    READ = "read"  # Read-only access (status, list skills)
    WRITE = "write"  # Write access (create files, modify data)
    EXECUTE = "execute"  # Execute code/commands
    ADMIN = "admin"  # Full access including user management

    # Skill-specific scopes
    SKILL_PDF = "skill:pdf"
    SKILL_CODE = "skill:code"
    SKILL_SQL = "skill:sql"
    SKILL_FS = "skill:fs"
    SKILL_GIT = "skill:git"
    SKILL_DOCKER = "skill:docker"
    SKILL_SSH = "skill:ssh"
    SKILL_EMAIL = "skill:email"
    SKILL_WEB = "skill:web"
    SKILL_RAG = "skill:rag"
    SKILL_VOICE = "skill:voice"
    SKILL_DESIGN = "skill:design"
    SKILL_LOGS = "skill:logs"
    SKILL_BENCHMARK = "skill:benchmark"
    SKILL_OPENAPI = "skill:openapi"

    # Chat scopes
    CHAT = "chat"  # Access to chat endpoint
    CHAT_STREAM = "chat:stream"  # Access to streaming chat

    # Tool scopes
    TOOL_CALL = "tool:call"  # Direct tool invocation


class SkillRiskLevel(str, Enum):
    """Risk level for skills."""

    LOW = "low"  # Safe operations (pdf, resume)
    MEDIUM = "medium"  # File access (fs, sql)
    HIGH = "high"  # System operations (code, git)
    CRITICAL = "critical"  # Remote/dangerous (ssh, docker, email)


# Skill to scope mapping
SKILL_SCOPES: dict[str, str] = {
    "pdf": Scope.SKILL_PDF,
    "latex": Scope.SKILL_PDF,
    "resume": Scope.READ,
    "code": Scope.SKILL_CODE,
    "sql": Scope.SKILL_SQL,
    "json": Scope.READ,
    "fs": Scope.SKILL_FS,
    "archive": Scope.SKILL_FS,
    "clipboard": Scope.WRITE,
    "git": Scope.SKILL_GIT,
    "docker": Scope.SKILL_DOCKER,
    "ssh": Scope.SKILL_SSH,
    "email": Scope.SKILL_EMAIL,
    "http": Scope.SKILL_WEB,
    "web": Scope.SKILL_WEB,
    "rag": Scope.SKILL_RAG,
    "multiagent": Scope.EXECUTE,
    "voice": Scope.SKILL_VOICE,
    "design": Scope.SKILL_DESIGN,
    "ocr": Scope.READ,
    "screenshot": Scope.READ,
    "calendar": Scope.WRITE,
    "translate": Scope.READ,
    "plugin": Scope.ADMIN,
    "logs": Scope.SKILL_LOGS,
    "benchmark": Scope.SKILL_BENCHMARK,
    "openapi": Scope.SKILL_OPENAPI,
}

# Skill risk levels
SKILL_RISK_LEVELS: dict[str, SkillRiskLevel] = {
    "pdf": SkillRiskLevel.LOW,
    "latex": SkillRiskLevel.LOW,
    "resume": SkillRiskLevel.LOW,
    "json": SkillRiskLevel.LOW,
    "ocr": SkillRiskLevel.LOW,
    "translate": SkillRiskLevel.LOW,
    "screenshot": SkillRiskLevel.LOW,
    "calendar": SkillRiskLevel.LOW,
    "clipboard": SkillRiskLevel.MEDIUM,
    "fs": SkillRiskLevel.MEDIUM,
    "archive": SkillRiskLevel.MEDIUM,
    "sql": SkillRiskLevel.MEDIUM,
    "rag": SkillRiskLevel.MEDIUM,
    "http": SkillRiskLevel.MEDIUM,
    "web": SkillRiskLevel.MEDIUM,
    "logs": SkillRiskLevel.MEDIUM,
    "benchmark": SkillRiskLevel.MEDIUM,
    "openapi": SkillRiskLevel.MEDIUM,
    "voice": SkillRiskLevel.MEDIUM,
    "design": SkillRiskLevel.MEDIUM,
    "code": SkillRiskLevel.HIGH,
    "git": SkillRiskLevel.HIGH,
    "multiagent": SkillRiskLevel.HIGH,
    "plugin": SkillRiskLevel.HIGH,
    "docker": SkillRiskLevel.CRITICAL,
    "ssh": SkillRiskLevel.CRITICAL,
    "email": SkillRiskLevel.CRITICAL,
}

# Scope hierarchy - higher scopes include lower ones
SCOPE_HIERARCHY: dict[str, list[str]] = {
    Scope.ADMIN: [
        Scope.READ,
        Scope.WRITE,
        Scope.EXECUTE,
        Scope.CHAT,
        Scope.CHAT_STREAM,
        Scope.TOOL_CALL,
    ],
    Scope.EXECUTE: [Scope.READ, Scope.WRITE],
    Scope.WRITE: [Scope.READ],
}

# Default scopes for new users/keys
DEFAULT_SCOPES = [Scope.READ, Scope.CHAT]

# Scopes that allow all skills at a risk level
RISK_LEVEL_SCOPES: dict[SkillRiskLevel, list[str]] = {
    SkillRiskLevel.LOW: [Scope.READ],
    SkillRiskLevel.MEDIUM: [Scope.WRITE],
    SkillRiskLevel.HIGH: [Scope.EXECUTE],
    SkillRiskLevel.CRITICAL: [Scope.ADMIN],
}


class PermissionChecker:
    """Check permissions for operations."""

    def __init__(self, user_scopes: list[str]):
        """Initialize with user's scopes."""
        self.user_scopes = set(user_scopes)
        self._expand_scopes()

    def _expand_scopes(self):
        """Expand scope hierarchy."""
        expanded = set(self.user_scopes)
        for scope in self.user_scopes:
            if scope in SCOPE_HIERARCHY:
                expanded.update(SCOPE_HIERARCHY[scope])
        self.user_scopes = expanded

    def has_scope(self, scope: str) -> bool:
        """Check if user has a specific scope."""
        # Admin has all scopes
        if Scope.ADMIN in self.user_scopes:
            return True
        return scope in self.user_scopes

    def has_any_scope(self, scopes: list[str]) -> bool:
        """Check if user has any of the given scopes."""
        return any(self.has_scope(s) for s in scopes)

    def has_all_scopes(self, scopes: list[str]) -> bool:
        """Check if user has all of the given scopes."""
        return all(self.has_scope(s) for s in scopes)

    def can_use_skill(self, skill_name: str) -> bool:
        """Check if user can use a specific skill."""
        # Admin can use all skills
        if Scope.ADMIN in self.user_scopes:
            return True

        # Check skill-specific scope
        skill_scope = SKILL_SCOPES.get(skill_name)
        if skill_scope and self.has_scope(skill_scope):
            return True

        # Check risk level scopes
        risk_level = SKILL_RISK_LEVELS.get(skill_name, SkillRiskLevel.HIGH)
        required_scopes = RISK_LEVEL_SCOPES.get(risk_level, [Scope.ADMIN])
        return self.has_any_scope(required_scopes)

    def can_call_tool(self, skill_name: str, tool_name: str) -> bool:
        """Check if user can call a specific tool."""
        # Must have tool:call scope
        if not self.has_scope(Scope.TOOL_CALL) and not self.has_scope(Scope.ADMIN):
            return False
        return self.can_use_skill(skill_name)

    def can_chat(self, streaming: bool = False) -> bool:
        """Check if user can use chat endpoint."""
        if streaming:
            return self.has_scope(Scope.CHAT_STREAM) or self.has_scope(Scope.CHAT)
        return self.has_scope(Scope.CHAT)

    def get_allowed_skills(self, all_skills: list[str]) -> list[str]:
        """Get list of skills the user is allowed to use."""
        return [s for s in all_skills if self.can_use_skill(s)]

    def get_denied_skills(self, all_skills: list[str]) -> list[str]:
        """Get list of skills the user is NOT allowed to use."""
        return [s for s in all_skills if not self.can_use_skill(s)]


class PermissionPolicy(BaseModel):
    """Permission policy for an API key or user."""

    allowed_skills: Optional[list[str]] = None  # None = check scopes
    denied_skills: list[str] = []
    max_requests_per_minute: int = 60
    max_tokens_per_request: int = 4096
    allow_streaming: bool = True
    allow_tool_calls: bool = True
    require_confirmation_for: list[str] = []  # Skills that need confirmation

    def can_use_skill(self, skill_name: str, checker: PermissionChecker) -> bool:
        """Check if skill is allowed by this policy."""
        # Check explicit deny list
        if skill_name in self.denied_skills:
            return False

        # Check explicit allow list
        if self.allowed_skills is not None:
            return skill_name in self.allowed_skills

        # Fall back to scope-based check
        return checker.can_use_skill(skill_name)


def check_skill_permission(
    skill_name: str,
    user_scopes: list[str],
    policy: Optional[PermissionPolicy] = None,
) -> tuple[bool, Optional[str]]:
    """
    Check if a skill is allowed.

    Returns:
        (allowed, reason) - If not allowed, reason explains why
    """
    checker = PermissionChecker(user_scopes)

    # Check policy first if provided
    if policy:
        if skill_name in policy.denied_skills:
            return False, f"Skill '{skill_name}' is explicitly denied by policy"

        if policy.allowed_skills is not None:
            if skill_name not in policy.allowed_skills:
                return False, f"Skill '{skill_name}' is not in allowed skills list"
            return True, None

    # Check scopes
    if not checker.can_use_skill(skill_name):
        required_scope = SKILL_SCOPES.get(skill_name, "unknown")
        risk_level = SKILL_RISK_LEVELS.get(skill_name, SkillRiskLevel.HIGH)
        return False, (
            f"Missing permission for skill '{skill_name}'. "
            f"Required scope: {required_scope} or higher. "
            f"Risk level: {risk_level.value}"
        )

    return True, None


def get_scope_description(scope: str) -> str:
    """Get human-readable description of a scope."""
    descriptions = {
        Scope.READ: "Read-only access to status and listings",
        Scope.WRITE: "Create and modify files and data",
        Scope.EXECUTE: "Execute code and commands",
        Scope.ADMIN: "Full administrative access",
        Scope.CHAT: "Access to chat completions",
        Scope.CHAT_STREAM: "Access to streaming chat",
        Scope.TOOL_CALL: "Direct tool invocation",
        Scope.SKILL_PDF: "PDF and document generation",
        Scope.SKILL_CODE: "Code generation and execution",
        Scope.SKILL_SQL: "Database queries",
        Scope.SKILL_FS: "File system operations",
        Scope.SKILL_GIT: "Git operations",
        Scope.SKILL_DOCKER: "Docker container management",
        Scope.SKILL_SSH: "SSH remote connections",
        Scope.SKILL_EMAIL: "Email sending",
        Scope.SKILL_WEB: "Web requests and scraping",
        Scope.SKILL_RAG: "Semantic search and RAG",
        Scope.SKILL_VOICE: "Voice transcription and TTS",
        Scope.SKILL_DESIGN: "Image generation",
        Scope.SKILL_LOGS: "Log analysis",
        Scope.SKILL_BENCHMARK: "Performance profiling",
        Scope.SKILL_OPENAPI: "OpenAPI integration",
    }
    return descriptions.get(scope, f"Access to {scope}")
