"""Tests for r-cli-sdk Python SDK."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from r_sdk import (
    APIError,
    APIKeyInfo,
    AsyncRClient,
    AuditEvent,
    AuthError,
    AuthUser,
    ChatMessage,
    ChatResponse,
    RateLimitError,
    RClient,
    RError,
    SkillInfo,
    StatusResponse,
)
from r_sdk.types import LLMStatus, ToolCall, ToolInfo


class TestTypes:
    """Tests for SDK type definitions."""

    def test_chat_message(self):
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_tool_call(self):
        tc = ToolCall(name="test", arguments={"a": 1}, result="ok")
        assert tc.name == "test"
        assert tc.arguments == {"a": 1}
        assert tc.result == "ok"

    def test_chat_response(self):
        response = ChatResponse(
            message="Hello!",
            skill_used="chat",
            model="gpt-4",
        )
        assert response.message == "Hello!"
        assert response.skill_used == "chat"

    def test_tool_info(self):
        tool = ToolInfo(
            name="calculator",
            description="Does math",
            parameters={"type": "object"},
        )
        assert tool.name == "calculator"

    def test_skill_info(self):
        skill = SkillInfo(
            name="code",
            description="Code generation",
            version="1.0.0",
            category="development",
            enabled=True,
            tools=[],
        )
        assert skill.name == "code"
        assert skill.enabled is True

    def test_llm_status(self):
        status = LLMStatus(
            connected=True,
            provider="openai",
            model="gpt-4",
        )
        assert status.connected is True

    def test_status_response(self):
        status = StatusResponse(
            status="healthy",
            version="0.1.0",
            uptime_seconds=3600.0,
            llm=LLMStatus(connected=True),
            skills_loaded=10,
            timestamp="2024-01-01T00:00:00Z",
        )
        assert status.status == "healthy"
        assert status.skills_loaded == 10

    def test_auth_user(self):
        user = AuthUser(
            user_id="123",
            username="admin",
            scopes=["read", "write"],
            auth_type="password",
        )
        assert user.username == "admin"
        assert "read" in user.scopes

    def test_api_key_info(self):
        key = APIKeyInfo(
            key_id="key_123",
            name="My Key",
            scopes=["read"],
            created_at=datetime.now(),
        )
        assert key.key_id == "key_123"
        assert key.last_used is None

    def test_audit_event(self):
        event = AuditEvent(
            timestamp="2024-01-01T00:00:00Z",
            action="chat.request",
            severity="info",
            success=True,
            username="admin",
        )
        assert event.action == "chat.request"
        assert event.success is True


class TestExceptions:
    """Tests for SDK exceptions."""

    def test_r_error(self):
        err = RError("Something went wrong", 500)
        assert str(err) == "Something went wrong"
        assert err.status_code == 500

    def test_auth_error(self):
        err = AuthError("Unauthorized", 401)
        assert err.status_code == 401
        assert isinstance(err, RError)

    def test_rate_limit_error(self):
        err = RateLimitError("Too many requests", retry_after=60.0)
        assert err.status_code == 429
        assert err.retry_after == 60.0

    def test_api_error(self):
        err = APIError("Bad request", 400)
        assert err.status_code == 400


class TestRClient:
    """Tests for synchronous RClient."""

    @pytest.fixture
    def mock_httpx(self):
        with patch("r_sdk.client.httpx.Client") as mock:
            yield mock

    @pytest.fixture
    def client(self, mock_httpx):
        return RClient(base_url="http://localhost:8000", api_key="test-key")

    def test_init_default(self):
        client = RClient()
        assert client.base_url == "http://localhost:8000"
        assert client.timeout == 30.0

    def test_init_with_params(self):
        client = RClient(
            base_url="http://example.com/",
            api_key="my-key",
            timeout=60.0,
        )
        assert client.base_url == "http://example.com"  # Trailing slash removed
        assert client.api_key == "my-key"
        assert client.timeout == 60.0

    def test_init_with_token(self):
        client = RClient(token="jwt-token")
        assert client.token == "jwt-token"

    def test_headers_with_api_key(self, client):
        headers = client._headers()
        assert headers["X-API-Key"] == "test-key"
        assert headers["Content-Type"] == "application/json"

    def test_headers_with_token(self):
        client = RClient(token="jwt-token")
        headers = client._headers()
        assert headers["Authorization"] == "Bearer jwt-token"

    def test_context_manager(self, mock_httpx):
        with RClient() as client:
            assert client is not None
        mock_httpx.return_value.close.assert_called_once()

    def test_handle_response_401(self, client, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 401

        with pytest.raises(AuthError):
            client._handle_response(mock_response)

    def test_handle_response_403(self, client, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 403

        with pytest.raises(AuthError, match="Permission denied"):
            client._handle_response(mock_response)

    def test_handle_response_429(self, client, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "30"}

        with pytest.raises(RateLimitError) as exc_info:
            client._handle_response(mock_response)
        assert exc_info.value.retry_after == 30.0

    def test_handle_response_500(self, client, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"detail": "Server error"}

        with pytest.raises(APIError, match="Server error"):
            client._handle_response(mock_response)

    def test_login(self, client, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "new-token"}
        mock_httpx.return_value.post.return_value = mock_response

        token = client.login("admin", "password")
        assert token == "new-token"
        assert client.token == "new-token"

    def test_health(self, client, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_httpx.return_value.get.return_value = mock_response

        result = client.health()
        assert result["status"] == "ok"

    def test_status(self, client, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "version": "0.1.0",
            "uptime_seconds": 3600,
            "llm": {"connected": True, "model": "gpt-4"},
            "skills_loaded": 5,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_httpx.return_value.get.return_value = mock_response

        status = client.status()
        assert isinstance(status, StatusResponse)
        assert status.status == "healthy"
        assert status.llm.connected is True

    def test_list_skills(self, client, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "name": "code",
                "description": "Code generation",
                "version": "1.0",
                "category": "dev",
                "enabled": True,
                "tools": [],
            }
        ]
        mock_httpx.return_value.get.return_value = mock_response

        skills = client.list_skills()
        assert len(skills) == 1
        assert skills[0].name == "code"

    def test_chat(self, client, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "Hello!",
            "skill_used": "chat",
            "tools_called": [],
        }
        mock_httpx.return_value.post.return_value = mock_response

        response = client.chat("Hi")
        assert isinstance(response, ChatResponse)
        assert response.message == "Hello!"

    def test_chat_with_history(self, client, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "Your name is Alice"}
        mock_httpx.return_value.post.return_value = mock_response

        history = [
            ChatMessage(role="user", content="My name is Alice"),
            ChatMessage(role="assistant", content="Hello Alice!"),
        ]
        response = client.chat("What's my name?", history=history)
        assert "Alice" in response.message

    def test_get_audit_logs(self, client, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "action": "chat.request",
                "severity": "info",
                "success": True,
            }
        ]
        mock_httpx.return_value.get.return_value = mock_response

        logs = client.get_audit_logs(limit=10)
        assert len(logs) == 1
        assert logs[0].action == "chat.request"


class TestAsyncRClient:
    """Tests for asynchronous AsyncRClient."""

    @pytest.fixture
    def mock_httpx_async(self):
        with patch("r_sdk.client.httpx.AsyncClient") as mock:
            yield mock

    @pytest.fixture
    def async_client(self, mock_httpx_async):
        return AsyncRClient(base_url="http://localhost:8000", api_key="test-key")

    def test_init(self):
        client = AsyncRClient(api_key="my-key")
        assert client.api_key == "my-key"

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_httpx_async):
        mock_httpx_async.return_value.aclose = AsyncMock()
        async with AsyncRClient() as client:
            assert client is not None
        mock_httpx_async.return_value.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_health(self, async_client, mock_httpx_async):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_httpx_async.return_value.get = AsyncMock(return_value=mock_response)

        result = await async_client.health()
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_chat(self, async_client, mock_httpx_async):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "Hello async!",
            "skill_used": None,
        }
        mock_httpx_async.return_value.post = AsyncMock(return_value=mock_response)

        response = await async_client.chat("Hi")
        assert response.message == "Hello async!"

    @pytest.mark.asyncio
    async def test_list_skills(self, async_client, mock_httpx_async):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "name": "sql",
                "description": "SQL queries",
                "version": "1.0",
                "category": "database",
                "enabled": True,
                "tools": [
                    {"name": "query", "description": "Run query", "parameters": {}}
                ],
            }
        ]
        mock_httpx_async.return_value.get = AsyncMock(return_value=mock_response)

        skills = await async_client.list_skills()
        assert len(skills) == 1
        assert skills[0].name == "sql"
        assert len(skills[0].tools) == 1


class TestIntegration:
    """Integration-style tests (mocked but testing full flows)."""

    @pytest.fixture
    def mock_httpx(self):
        with patch("r_sdk.client.httpx.Client") as mock:
            yield mock

    def test_full_chat_flow(self, mock_httpx):
        # Setup mock responses
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.json.return_value = {"access_token": "jwt-token"}

        chat_response = MagicMock()
        chat_response.status_code = 200
        chat_response.json.return_value = {
            "message": "2 + 2 = 4",
            "skill_used": "calculator",
            "tools_called": [
                {"name": "calculate", "arguments": {"expr": "2+2"}, "result": "4"}
            ],
        }

        mock_httpx.return_value.post.side_effect = [login_response, chat_response]

        # Test flow
        client = RClient()
        client.login("admin", "password")
        response = client.chat("What is 2 + 2?")

        assert response.message == "2 + 2 = 4"
        assert response.skill_used == "calculator"
        assert len(response.tools_called) == 1
        assert response.tools_called[0].name == "calculate"

    def test_error_handling_flow(self, mock_httpx):
        # First call succeeds, second fails with rate limit
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"message": "OK"}

        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "60"}

        mock_httpx.return_value.post.side_effect = [
            success_response,
            rate_limit_response,
        ]

        client = RClient(api_key="test")

        # First call succeeds
        response = client.chat("Hello")
        assert response.message == "OK"

        # Second call hits rate limit
        with pytest.raises(RateLimitError) as exc_info:
            client.chat("Hello again")
        assert exc_info.value.retry_after == 60.0
