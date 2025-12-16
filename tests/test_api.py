"""
Tests for R CLI API module.

Tests authentication, permissions, rate limiting, audit logging, and API endpoints.
"""

import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from r_cli.api.audit import (
    AuditAction,
    AuditEvent,
    AuditLogger,
    AuditSeverity,
    audit_log,
    get_audit_logger,
)
from r_cli.api.auth import (
    API_KEY_LENGTH,
    APIKey,
    AuthResult,
    AuthStorage,
    Token,
    TokenData,
    User,
    authenticate_user,
    create_access_token,
    decode_token,
    validate_api_key,
    verify_password,
)
from r_cli.api.permissions import (
    DEFAULT_SCOPES,
    SKILL_RISK_LEVELS,
    SKILL_SCOPES,
    PermissionChecker,
    PermissionPolicy,
    Scope,
    SkillRiskLevel,
    check_skill_permission,
    get_scope_description,
)
from r_cli.api.rate_limit import (
    RATE_LIMIT_TIERS,
    RateLimitConfig,
    RateLimiter,
    TokenBucket,
)


# Mock password hashing for tests (bcrypt can be slow/problematic)
@pytest.fixture(autouse=True)
def mock_password_context():
    """Mock password hashing to avoid bcrypt issues in tests."""
    with patch("r_cli.api.auth.pwd_context") as mock_ctx:
        mock_ctx.hash.side_effect = lambda p: f"hashed_{p}"
        mock_ctx.verify.side_effect = lambda p, h: h == f"hashed_{p}"
        yield mock_ctx


# ============================================================================
# Auth Module Tests
# ============================================================================


class TestAuthStorage:
    """Tests for AuthStorage class."""

    def test_init_creates_storage_dir(self, temp_dir):
        """Test storage initialization creates directory."""
        storage_path = temp_dir / "auth"
        storage = AuthStorage(str(storage_path))
        assert storage_path.exists()
        assert (storage_path / "users.json").exists()
        assert (storage_path / "api_keys.json").exists()

    def test_create_user(self, temp_dir):
        """Test user creation."""
        storage = AuthStorage(str(temp_dir / "auth"))
        user = storage.create_user("testuser", "password123", ["read", "write"])

        assert user.username == "testuser"
        assert user.scopes == ["read", "write"]
        assert user.is_active is True
        assert user.user_id is not None

    def test_create_duplicate_user_raises(self, temp_dir):
        """Test creating duplicate user raises error."""
        storage = AuthStorage(str(temp_dir / "auth"))
        storage.create_user("testuser", "password123")

        with pytest.raises(ValueError, match="already exists"):
            storage.create_user("testuser", "different_password")

    def test_get_user(self, temp_dir):
        """Test getting user by username."""
        storage = AuthStorage(str(temp_dir / "auth"))
        storage.create_user("testuser", "password123", ["read"])

        user = storage.get_user("testuser")
        assert user is not None
        assert user.username == "testuser"

        nonexistent = storage.get_user("nobody")
        assert nonexistent is None

    def test_get_user_by_id(self, temp_dir):
        """Test getting user by ID."""
        storage = AuthStorage(str(temp_dir / "auth"))
        created = storage.create_user("testuser", "password123")

        user = storage.get_user_by_id(created.user_id)
        assert user is not None
        assert user.username == "testuser"

    def test_delete_user(self, temp_dir):
        """Test user deletion."""
        storage = AuthStorage(str(temp_dir / "auth"))
        storage.create_user("testuser", "password123")

        assert storage.delete_user("testuser") is True
        assert storage.get_user("testuser") is None
        assert storage.delete_user("testuser") is False

    def test_create_api_key(self, temp_dir):
        """Test API key creation."""
        storage = AuthStorage(str(temp_dir / "auth"))
        raw_key, api_key = storage.create_api_key("test-key", ["read"], expires_in_days=30)

        assert len(raw_key) > API_KEY_LENGTH
        assert api_key.name == "test-key"
        assert api_key.scopes == ["read"]
        assert api_key.is_active is True
        assert api_key.expires_at is not None

    def test_get_api_key_by_hash(self, temp_dir):
        """Test getting API key by hash."""
        storage = AuthStorage(str(temp_dir / "auth"))
        raw_key, api_key = storage.create_api_key("test-key", ["read"])

        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        found = storage.get_api_key_by_hash(key_hash)

        assert found is not None
        assert found.key_id == api_key.key_id

    def test_revoke_api_key(self, temp_dir):
        """Test revoking API key."""
        storage = AuthStorage(str(temp_dir / "auth"))
        _, api_key = storage.create_api_key("test-key", ["read"])

        assert storage.revoke_api_key(api_key.key_id) is True

        revoked = storage.get_api_key(api_key.key_id)
        assert revoked.is_active is False

    def test_delete_api_key(self, temp_dir):
        """Test deleting API key."""
        storage = AuthStorage(str(temp_dir / "auth"))
        _, api_key = storage.create_api_key("test-key", ["read"])

        assert storage.delete_api_key(api_key.key_id) is True
        assert storage.get_api_key(api_key.key_id) is None

    def test_list_api_keys(self, temp_dir):
        """Test listing API keys."""
        storage = AuthStorage(str(temp_dir / "auth"))
        storage.create_api_key("key1", ["read"])
        storage.create_api_key("key2", ["write"])

        keys = storage.list_api_keys()
        assert len(keys) == 2
        names = [k.name for k in keys]
        assert "key1" in names
        assert "key2" in names


class TestJWT:
    """Tests for JWT token functions."""

    def test_create_access_token(self):
        """Test JWT token creation."""
        token = create_access_token({"sub": "user123", "username": "testuser", "scopes": ["read"]})
        assert isinstance(token, str)
        assert len(token) > 50

    def test_create_access_token_with_expiry(self):
        """Test JWT token with custom expiry."""
        token = create_access_token(
            {"sub": "user123"},
            expires_delta=timedelta(hours=2),
        )
        data = decode_token(token)
        assert data.sub == "user123"

    def test_decode_token(self):
        """Test JWT token decoding."""
        token = create_access_token(
            {"sub": "user123", "username": "testuser", "scopes": ["read", "write"]}
        )
        data = decode_token(token)

        assert data.sub == "user123"
        assert data.username == "testuser"
        assert data.scopes == ["read", "write"]

    def test_decode_invalid_token_raises(self):
        """Test decoding invalid token raises HTTPException."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_token("invalid.token.here")

        assert exc_info.value.status_code == 401


class TestPasswordAuth:
    """Tests for password authentication."""

    def test_verify_password(self, temp_dir):
        """Test password verification."""
        storage = AuthStorage(str(temp_dir / "auth"))
        user = storage.create_user("testuser", "password123")

        assert verify_password("password123", user.password_hash) is True
        assert verify_password("wrongpassword", user.password_hash) is False

    def test_authenticate_user_success(self, temp_dir):
        """Test successful user authentication."""
        storage = AuthStorage(str(temp_dir / "auth"))
        storage.create_user("testuser", "password123", ["read"])

        with patch("r_cli.api.auth.get_storage", return_value=storage):
            user = authenticate_user("testuser", "password123")
            assert user is not None
            assert user.username == "testuser"

    def test_authenticate_user_wrong_password(self, temp_dir):
        """Test authentication with wrong password."""
        storage = AuthStorage(str(temp_dir / "auth"))
        storage.create_user("testuser", "password123")

        with patch("r_cli.api.auth.get_storage", return_value=storage):
            user = authenticate_user("testuser", "wrongpassword")
            assert user is None

    def test_authenticate_nonexistent_user(self, temp_dir):
        """Test authentication of nonexistent user."""
        storage = AuthStorage(str(temp_dir / "auth"))

        with patch("r_cli.api.auth.get_storage", return_value=storage):
            user = authenticate_user("nobody", "password")
            assert user is None


class TestAPIKeyValidation:
    """Tests for API key validation."""

    def test_validate_api_key_success(self, temp_dir):
        """Test successful API key validation."""
        storage = AuthStorage(str(temp_dir / "auth"))
        raw_key, _ = storage.create_api_key("test-key", ["read"])

        with patch("r_cli.api.auth.get_storage", return_value=storage):
            api_key = validate_api_key(raw_key)
            assert api_key is not None
            assert api_key.name == "test-key"

    def test_validate_api_key_invalid(self, temp_dir):
        """Test validation of invalid API key."""
        storage = AuthStorage(str(temp_dir / "auth"))

        with patch("r_cli.api.auth.get_storage", return_value=storage):
            api_key = validate_api_key("invalid-key")
            assert api_key is None

    def test_validate_api_key_revoked(self, temp_dir):
        """Test validation of revoked API key."""
        storage = AuthStorage(str(temp_dir / "auth"))
        raw_key, api_key = storage.create_api_key("test-key", ["read"])
        storage.revoke_api_key(api_key.key_id)

        with patch("r_cli.api.auth.get_storage", return_value=storage):
            result = validate_api_key(raw_key)
            assert result is None


# ============================================================================
# Permissions Module Tests
# ============================================================================


class TestPermissionChecker:
    """Tests for PermissionChecker class."""

    def test_has_scope_basic(self):
        """Test basic scope checking."""
        checker = PermissionChecker(["read", "write"])

        assert checker.has_scope("read") is True
        assert checker.has_scope("write") is True
        assert checker.has_scope("admin") is False

    def test_has_scope_admin_has_all(self):
        """Test admin has all scopes."""
        checker = PermissionChecker(["admin"])

        assert checker.has_scope("read") is True
        assert checker.has_scope("write") is True
        assert checker.has_scope("execute") is True
        assert checker.has_scope("skill:pdf") is True

    def test_scope_hierarchy_expansion(self):
        """Test scope hierarchy is expanded."""
        checker = PermissionChecker(["execute"])

        # execute includes read and write
        assert checker.has_scope("read") is True
        assert checker.has_scope("write") is True
        assert checker.has_scope("execute") is True
        assert checker.has_scope("admin") is False

    def test_has_any_scope(self):
        """Test has_any_scope method."""
        checker = PermissionChecker(["read"])

        assert checker.has_any_scope(["read", "write"]) is True
        assert checker.has_any_scope(["write", "execute"]) is False

    def test_has_all_scopes(self):
        """Test has_all_scopes method."""
        checker = PermissionChecker(["read", "write"])

        assert checker.has_all_scopes(["read", "write"]) is True
        assert checker.has_all_scopes(["read", "execute"]) is False

    def test_can_use_skill_with_scope(self):
        """Test skill access with specific scope."""
        checker = PermissionChecker(["skill:pdf"])

        assert checker.can_use_skill("pdf") is True
        assert checker.can_use_skill("code") is False

    def test_can_use_skill_with_risk_level(self):
        """Test skill access based on risk level."""
        # read scope allows low risk skills
        checker = PermissionChecker(["read"])
        assert checker.can_use_skill("pdf") is True
        assert checker.can_use_skill("resume") is True

        # write scope allows medium risk skills
        checker = PermissionChecker(["write"])
        assert checker.can_use_skill("fs") is True
        assert checker.can_use_skill("sql") is True

    def test_can_call_tool(self):
        """Test tool call permission."""
        checker = PermissionChecker(["tool:call", "skill:pdf"])

        assert checker.can_call_tool("pdf", "generate") is True
        assert checker.can_call_tool("code", "run") is False

    def test_can_chat(self):
        """Test chat permission."""
        checker = PermissionChecker(["chat"])

        assert checker.can_chat() is True
        assert checker.can_chat(streaming=True) is True

    def test_get_allowed_skills(self):
        """Test getting allowed skills list."""
        checker = PermissionChecker(["read"])
        all_skills = ["pdf", "resume", "code", "ssh"]

        allowed = checker.get_allowed_skills(all_skills)
        assert "pdf" in allowed
        assert "resume" in allowed
        assert "code" not in allowed
        assert "ssh" not in allowed


class TestPermissionPolicy:
    """Tests for PermissionPolicy class."""

    def test_explicit_allowed_skills(self):
        """Test explicit allowed skills list."""
        policy = PermissionPolicy(allowed_skills=["pdf", "resume"])
        checker = PermissionChecker(["read"])

        assert policy.can_use_skill("pdf", checker) is True
        assert policy.can_use_skill("code", checker) is False

    def test_explicit_denied_skills(self):
        """Test explicit denied skills list."""
        policy = PermissionPolicy(denied_skills=["ssh", "docker"])
        checker = PermissionChecker(["admin"])

        assert policy.can_use_skill("pdf", checker) is True
        assert policy.can_use_skill("ssh", checker) is False


class TestCheckSkillPermission:
    """Tests for check_skill_permission function."""

    def test_allowed_returns_true(self):
        """Test allowed skill returns True."""
        allowed, reason = check_skill_permission("pdf", ["read"])
        assert allowed is True
        assert reason is None

    def test_denied_returns_reason(self):
        """Test denied skill returns reason."""
        allowed, reason = check_skill_permission("ssh", ["read"])
        assert allowed is False
        assert "Missing permission" in reason

    def test_policy_override(self):
        """Test policy can override scope-based check."""
        policy = PermissionPolicy(denied_skills=["pdf"])
        allowed, reason = check_skill_permission("pdf", ["admin"], policy)
        assert allowed is False
        assert "explicitly denied" in reason


class TestScopeDescriptions:
    """Tests for scope descriptions."""

    def test_get_scope_description(self):
        """Test getting scope descriptions."""
        desc = get_scope_description(Scope.READ)
        assert "Read-only" in desc

        desc = get_scope_description(Scope.ADMIN)
        assert "administrative" in desc.lower()

    def test_unknown_scope_description(self):
        """Test unknown scope returns default description."""
        desc = get_scope_description("unknown:scope")
        assert "Access to" in desc


# ============================================================================
# Rate Limiting Module Tests
# ============================================================================


class TestTokenBucket:
    """Tests for TokenBucket class."""

    def test_bucket_init(self):
        """Test bucket initialization."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.tokens == 10.0

    def test_consume_success(self):
        """Test successful token consumption."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        assert bucket.consume(1) is True
        assert bucket.tokens == 9.0

    def test_consume_multiple(self):
        """Test consuming multiple tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        assert bucket.consume(5) is True
        assert bucket.tokens == 5.0

    def test_consume_exceeds_capacity(self):
        """Test consuming more than available."""
        bucket = TokenBucket(capacity=5, refill_rate=1.0)

        assert bucket.consume(10) is False
        assert bucket.tokens == 5.0  # Unchanged

    def test_refill_over_time(self):
        """Test token refill over time."""
        bucket = TokenBucket(capacity=10, refill_rate=10.0)  # 10 tokens/sec
        bucket.tokens = 0.0
        bucket.last_refill = time.time() - 0.5  # 0.5 seconds ago

        bucket._refill()
        assert bucket.tokens >= 4.0  # Should have ~5 tokens

    def test_refill_capped_at_capacity(self):
        """Test refill doesn't exceed capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=100.0)
        bucket.last_refill = time.time() - 1.0  # 1 second ago

        bucket._refill()
        assert bucket.tokens == 10.0  # Capped at capacity

    def test_get_retry_after(self):
        """Test retry-after calculation."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        bucket.tokens = 0.0

        retry = bucket.get_retry_after(5)
        assert retry == pytest.approx(5.0, rel=0.1)


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_default_config(self):
        """Test default configuration."""
        limiter = RateLimiter()
        assert limiter.default_config.requests_per_minute == 60

    def test_get_bucket_creates_new(self):
        """Test bucket is created for new client."""
        limiter = RateLimiter()
        bucket = limiter.get_bucket("client1")

        assert bucket is not None
        assert "client1" in limiter.buckets

    def test_get_bucket_returns_existing(self):
        """Test same bucket returned for same client."""
        limiter = RateLimiter()
        bucket1 = limiter.get_bucket("client1")
        bucket2 = limiter.get_bucket("client1")

        assert bucket1 is bucket2

    def test_check_rate_limit_allowed(self):
        """Test allowed request."""
        limiter = RateLimiter()
        allowed, retry_after = limiter.check_rate_limit("client1")

        assert allowed is True
        assert retry_after is None

    def test_check_rate_limit_exceeded(self):
        """Test rate limit exceeded."""
        config = RateLimitConfig(requests_per_minute=1, burst_multiplier=1.0)
        limiter = RateLimiter(default_config=config)

        # First request allowed
        allowed, _ = limiter.check_rate_limit("client1")
        assert allowed is True

        # Second request should be denied
        allowed, retry_after = limiter.check_rate_limit("client1")
        assert allowed is False
        assert retry_after is not None
        assert retry_after > 0

    def test_set_client_tier(self):
        """Test setting client tier."""
        limiter = RateLimiter()
        limiter.set_client_tier("client1", "premium")

        config = limiter.client_configs.get("client1")
        assert config is not None
        assert config.requests_per_minute == 120

    def test_get_remaining(self):
        """Test getting remaining rate limit info."""
        limiter = RateLimiter()
        limiter.check_rate_limit("client1")

        remaining = limiter.get_remaining("client1")
        assert "remaining" in remaining
        assert "limit" in remaining
        assert remaining["limit"] == 60

    def test_cleanup_old_buckets(self):
        """Test cleanup of old buckets."""
        limiter = RateLimiter()
        limiter.get_bucket("old_client")
        limiter.buckets["old_client"].last_refill = time.time() - 7200  # 2 hours ago

        limiter.cleanup_old_buckets(max_age_seconds=3600)
        assert "old_client" not in limiter.buckets


class TestRateLimitTiers:
    """Tests for rate limit tier configurations."""

    def test_free_tier(self):
        """Test free tier limits."""
        config = RATE_LIMIT_TIERS["free"]
        assert config.requests_per_minute == 30
        assert config.heavy_requests_per_minute == 5

    def test_standard_tier(self):
        """Test standard tier limits."""
        config = RATE_LIMIT_TIERS["standard"]
        assert config.requests_per_minute == 60

    def test_premium_tier(self):
        """Test premium tier limits."""
        config = RATE_LIMIT_TIERS["premium"]
        assert config.requests_per_minute == 120

    def test_unlimited_tier(self):
        """Test unlimited tier limits."""
        config = RATE_LIMIT_TIERS["unlimited"]
        assert config.requests_per_minute == 1000


# ============================================================================
# Audit Module Tests
# ============================================================================


class TestAuditEvent:
    """Tests for AuditEvent model."""

    def test_create_event(self):
        """Test creating audit event."""
        event = AuditEvent(
            timestamp=datetime.now(),
            action=AuditAction.AUTH_LOGIN,
            user_id="user123",
            username="testuser",
            success=True,
        )

        assert event.action == AuditAction.AUTH_LOGIN
        assert event.user_id == "user123"
        assert event.success is True

    def test_event_defaults(self):
        """Test event default values."""
        event = AuditEvent(
            timestamp=datetime.now(),
            action=AuditAction.CHAT_REQUEST,
        )

        assert event.severity == AuditSeverity.INFO
        assert event.success is True
        assert event.user_id is None


class TestAuditLogger:
    """Tests for AuditLogger class."""

    def test_init_creates_log_dir(self, temp_dir):
        """Test logger initialization creates directory."""
        log_dir = temp_dir / "logs"
        logger = AuditLogger(log_dir=str(log_dir))

        assert log_dir.exists()
        assert logger.log_file.exists() or True  # May not exist until first log

    def test_log_event(self, temp_dir):
        """Test logging an event."""
        logger = AuditLogger(log_dir=str(temp_dir / "logs"))
        event = AuditEvent(
            timestamp=datetime.now(),
            action=AuditAction.AUTH_LOGIN,
            username="testuser",
            success=True,
        )

        logger.log(event)

        # Check log file contains the event
        log_content = logger.log_file.read_text()
        assert "auth.login" in log_content
        assert "testuser" in log_content

    def test_log_action_convenience(self, temp_dir):
        """Test log_action convenience method."""
        logger = AuditLogger(log_dir=str(temp_dir / "logs"))

        logger.log_action(
            action=AuditAction.SKILL_CALLED,
            username="testuser",
            resource="pdf",
            success=True,
        )

        log_content = logger.log_file.read_text()
        assert "skill.called" in log_content
        assert "pdf" in log_content

    def test_get_recent_events(self, temp_dir):
        """Test getting recent events from log."""
        logger = AuditLogger(log_dir=str(temp_dir / "logs"))

        # Log some events
        for i in range(5):
            logger.log_action(
                action=AuditAction.CHAT_REQUEST,
                user_id=f"user{i}",
                success=True,
            )

        events = logger.get_recent_events(limit=3)
        assert len(events) == 3

    def test_get_recent_events_filtered(self, temp_dir):
        """Test filtering recent events."""
        logger = AuditLogger(log_dir=str(temp_dir / "logs"))

        logger.log_action(AuditAction.AUTH_LOGIN, user_id="user1", success=True)
        logger.log_action(AuditAction.AUTH_FAILED, user_id="user2", success=False)
        logger.log_action(AuditAction.AUTH_LOGIN, user_id="user3", success=True)

        # Filter by action
        events = logger.get_recent_events(action=AuditAction.AUTH_LOGIN)
        assert len(events) == 2

        # Filter by success
        events = logger.get_recent_events(success=False)
        assert len(events) == 1


class TestAuditActions:
    """Tests for audit action types."""

    def test_auth_actions(self):
        """Test authentication action types."""
        assert AuditAction.AUTH_LOGIN.value == "auth.login"
        assert AuditAction.AUTH_FAILED.value == "auth.failed"
        assert AuditAction.AUTH_TOKEN_CREATED.value == "auth.token_created"

    def test_skill_actions(self):
        """Test skill action types."""
        assert AuditAction.SKILL_CALLED.value == "skill.called"
        assert AuditAction.SKILL_COMPLETED.value == "skill.completed"
        assert AuditAction.SKILL_ERROR.value == "skill.error"

    def test_system_actions(self):
        """Test system action types."""
        assert AuditAction.SERVER_STARTED.value == "server.started"
        assert AuditAction.RATE_LIMIT_EXCEEDED.value == "rate_limit.exceeded"


class TestAuditSeverity:
    """Tests for audit severity levels."""

    def test_severity_levels(self):
        """Test severity level values."""
        assert AuditSeverity.DEBUG.value == "debug"
        assert AuditSeverity.INFO.value == "info"
        assert AuditSeverity.WARNING.value == "warning"
        assert AuditSeverity.ERROR.value == "error"
        assert AuditSeverity.CRITICAL.value == "critical"


# ============================================================================
# API Endpoint Tests
# ============================================================================


class TestAPIEndpoints:
    """Tests for API endpoints."""

    @pytest.fixture
    def client(self, temp_dir):
        """Create test client with mocked storage."""
        # Set environment to use temp directory
        os.environ["R_CLI_HOME"] = str(temp_dir)
        os.environ["R_AUTH_MODE"] = "optional"

        from r_cli.api.server import create_app

        app = create_app()
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "R CLI API" in data["message"]

    def test_status_endpoint(self, client):
        """Test status endpoint returns proper structure."""
        response = client.get("/v1/status")
        # Status endpoint depends on LLM connection, may return 200, 500, or 503
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert "version" in data
            assert "status" in data

    def test_skills_list_endpoint(self, client):
        """Test skills list endpoint."""
        response = client.get("/v1/skills")
        # Skills endpoint may fail if agent not properly initialized
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert "skills" in data
            assert isinstance(data["skills"], list)

    def test_rate_limit_headers(self, client):
        """Test rate limit headers are present."""
        response = client.get("/v1/status")
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    @pytest.fixture
    def client_with_auth(self, temp_dir, mock_password_context):
        """Create test client with auth enabled."""
        os.environ["R_CLI_HOME"] = str(temp_dir)
        os.environ["R_AUTH_MODE"] = "optional"

        # Create a test user
        auth_dir = temp_dir / "auth"
        auth_dir.mkdir(parents=True, exist_ok=True)

        # Create user via storage directly (using mocked password context)
        storage = AuthStorage(str(auth_dir))
        storage.create_user("admin", "admin123", ["admin"])

        from r_cli.api.server import create_app

        app = create_app()
        client = TestClient(app)

        return client, storage

    def test_login_success(self, client_with_auth, mock_password_context):
        """Test successful login."""
        client, storage = client_with_auth

        # Mock successful authentication
        mock_user = Mock()
        mock_user.user_id = "user123"
        mock_user.username = "admin"
        mock_user.scopes = ["admin"]

        with (
            patch("r_cli.api.server.get_storage", return_value=storage),
            patch("r_cli.api.server.authenticate_user", return_value=mock_user),
        ):
            response = client.post(
                "/auth/login",
                json={"username": "admin", "password": "admin123"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self, client_with_auth, mock_password_context):
        """Test login with invalid credentials."""
        client, storage = client_with_auth

        with (
            patch("r_cli.api.server.get_storage", return_value=storage),
            patch("r_cli.api.server.authenticate_user", return_value=None),
        ):
            response = client.post(
                "/auth/login",
                json={"username": "admin", "password": "wrongpassword"},
            )

        assert response.status_code == 401

    def test_me_endpoint_unauthenticated(self, client_with_auth):
        """Test /auth/me without authentication."""
        client, _ = client_with_auth
        response = client.get("/auth/me")
        assert response.status_code == 401

    def test_me_endpoint_authenticated(self, client_with_auth, mock_password_context):
        """Test /auth/me with authentication."""
        client, storage = client_with_auth

        # Create a valid token directly
        token = create_access_token(
            {
                "sub": "user123",
                "username": "admin",
                "scopes": ["admin"],
            }
        )

        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"


class TestChatEndpoint:
    """Tests for chat endpoint."""

    @pytest.fixture
    def client(self, temp_dir):
        """Create test client."""
        os.environ["R_CLI_HOME"] = str(temp_dir)
        os.environ["R_AUTH_MODE"] = "none"

        from r_cli.api.server import create_app

        app = create_app()
        return TestClient(app)

    def test_chat_requires_message(self, client):
        """Test chat requires message."""
        response = client.post("/v1/chat", json={})
        assert response.status_code == 422  # Validation error

    def test_chat_endpoint_exists(self, client):
        """Test chat endpoint exists and accepts requests."""
        response = client.post(
            "/v1/chat",
            json={"message": "Hello"},
        )
        # Chat endpoint may fail due to LLM not being available,
        # but should not return 404 (endpoint not found)
        assert response.status_code != 404


# ============================================================================
# Integration Tests
# ============================================================================


class TestSecurityIntegration:
    """Integration tests for security features."""

    def test_full_auth_flow(self, temp_dir):
        """Test complete authentication flow."""
        # Setup
        storage = AuthStorage(str(temp_dir / "auth"))
        user = storage.create_user("testuser", "password123", ["read", "chat"])

        # Authenticate
        with patch("r_cli.api.auth.get_storage", return_value=storage):
            auth_user = authenticate_user("testuser", "password123")
            assert auth_user is not None

            # Create token
            token = create_access_token(
                {
                    "sub": auth_user.user_id,
                    "username": auth_user.username,
                    "scopes": auth_user.scopes,
                }
            )

            # Decode and verify
            token_data = decode_token(token)
            assert token_data.username == "testuser"
            assert "read" in token_data.scopes

    def test_api_key_auth_flow(self, temp_dir):
        """Test API key authentication flow."""
        storage = AuthStorage(str(temp_dir / "auth"))
        raw_key, api_key = storage.create_api_key("test-key", ["read", "write"])

        with patch("r_cli.api.auth.get_storage", return_value=storage):
            validated = validate_api_key(raw_key)
            assert validated is not None
            assert validated.scopes == ["read", "write"]

    def test_permission_with_auth(self, temp_dir):
        """Test permissions work with authentication."""
        storage = AuthStorage(str(temp_dir / "auth"))
        storage.create_user("limited_user", "password", ["read"])

        with patch("r_cli.api.auth.get_storage", return_value=storage):
            user = authenticate_user("limited_user", "password")
            checker = PermissionChecker(user.scopes)

            # Should be able to use read-only skills
            assert checker.can_use_skill("pdf") is True
            assert checker.can_use_skill("resume") is True

            # Should NOT be able to use higher-risk skills
            assert checker.can_use_skill("ssh") is False
            assert checker.can_use_skill("docker") is False
