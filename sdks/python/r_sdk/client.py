"""R CLI API Client."""

from __future__ import annotations

import httpx
from typing import Any, Iterator

from .types import (
    ChatMessage,
    ChatResponse,
    SkillInfo,
    StatusResponse,
    AuthUser,
    APIKeyInfo,
    AuditEvent,
    LLMStatus,
    ToolInfo,
    ToolCall,
)
from .exceptions import RError, AuthError, RateLimitError, APIError


class RClient:
    """Synchronous client for R CLI API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize R CLI client.

        Args:
            base_url: Base URL of the R CLI API server
            api_key: API key for authentication
            token: JWT token for authentication (alternative to api_key)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.token = token
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def _headers(self) -> dict[str, str]:
        """Get request headers with auth."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        elif self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _handle_response(self, response: httpx.Response) -> Any:
        """Handle API response and raise appropriate exceptions."""
        if response.status_code == 401:
            raise AuthError("Authentication required", 401)
        if response.status_code == 403:
            raise AuthError("Permission denied", 403)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                "Rate limit exceeded",
                retry_after=float(retry_after) if retry_after else None,
            )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise APIError(str(detail), response.status_code)
        return response.json()

    def close(self) -> None:
        """Close the client."""
        self._client.close()

    def __enter__(self) -> "RClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # Auth methods

    def login(self, username: str, password: str) -> str:
        """
        Login with username and password.

        Returns:
            JWT access token
        """
        response = self._client.post(
            f"{self.base_url}/auth/token",
            data={"username": username, "password": password},
        )
        data = self._handle_response(response)
        self.token = data["access_token"]
        return self.token

    def get_me(self) -> AuthUser:
        """Get current authenticated user info."""
        response = self._client.get(
            f"{self.base_url}/auth/me",
            headers=self._headers(),
        )
        data = self._handle_response(response)
        return AuthUser(
            user_id=data["user_id"],
            username=data["username"],
            scopes=data["scopes"],
            auth_type=data["auth_type"],
        )

    # Status methods

    def health(self) -> dict[str, str]:
        """Check server health."""
        response = self._client.get(f"{self.base_url}/health")
        return self._handle_response(response)

    def status(self) -> StatusResponse:
        """Get detailed server status."""
        response = self._client.get(
            f"{self.base_url}/v1/status",
            headers=self._headers(),
        )
        data = self._handle_response(response)
        return StatusResponse(
            status=data["status"],
            version=data["version"],
            uptime_seconds=data["uptime_seconds"],
            llm=LLMStatus(
                connected=data["llm"]["connected"],
                provider=data["llm"].get("provider"),
                model=data["llm"].get("model"),
                base_url=data["llm"].get("base_url"),
            ),
            skills_loaded=data["skills_loaded"],
            timestamp=data["timestamp"],
        )

    # Skills methods

    def list_skills(self) -> list[SkillInfo]:
        """List all available skills."""
        response = self._client.get(
            f"{self.base_url}/v1/skills",
            headers=self._headers(),
        )
        data = self._handle_response(response)
        return [
            SkillInfo(
                name=s["name"],
                description=s["description"],
                version=s["version"],
                category=s["category"],
                enabled=s["enabled"],
                tools=[
                    ToolInfo(
                        name=t["name"],
                        description=t["description"],
                        parameters=t["parameters"],
                    )
                    for t in s.get("tools", [])
                ],
            )
            for s in data
        ]

    def get_skill(self, name: str) -> SkillInfo:
        """Get a specific skill by name."""
        response = self._client.get(
            f"{self.base_url}/v1/skills/{name}",
            headers=self._headers(),
        )
        data = self._handle_response(response)
        return SkillInfo(
            name=data["name"],
            description=data["description"],
            version=data["version"],
            category=data["category"],
            enabled=data["enabled"],
            tools=[
                ToolInfo(
                    name=t["name"],
                    description=t["description"],
                    parameters=t["parameters"],
                )
                for t in data.get("tools", [])
            ],
        )

    # Chat methods

    def chat(
        self,
        message: str,
        history: list[ChatMessage] | None = None,
        skill: str | None = None,
        stream: bool = False,
    ) -> ChatResponse | Iterator[str]:
        """
        Send a chat message.

        Args:
            message: The user message
            history: Optional conversation history
            skill: Optional skill to use (auto-detected if not specified)
            stream: Whether to stream the response

        Returns:
            ChatResponse or iterator of chunks if streaming
        """
        messages = []
        if history:
            messages.extend([{"role": m.role, "content": m.content} for m in history])
        messages.append({"role": "user", "content": message})

        payload: dict[str, Any] = {"messages": messages}
        if skill:
            payload["skill"] = skill
        if stream:
            payload["stream"] = True

        if stream:
            return self._stream_chat(payload)

        response = self._client.post(
            f"{self.base_url}/v1/chat",
            headers=self._headers(),
            json=payload,
        )
        data = self._handle_response(response)
        return ChatResponse(
            message=data["message"],
            skill_used=data.get("skill_used"),
            tools_called=[
                ToolCall(
                    name=t["name"],
                    arguments=t.get("arguments", {}),
                    result=t.get("result"),
                )
                for t in data.get("tools_called", [])
            ]
            if data.get("tools_called")
            else None,
            model=data.get("model"),
            usage=data.get("usage"),
        )

    def _stream_chat(self, payload: dict[str, Any]) -> Iterator[str]:
        """Stream chat response."""
        with self._client.stream(
            "POST",
            f"{self.base_url}/v1/chat",
            headers=self._headers(),
            json=payload,
        ) as response:
            if response.status_code >= 400:
                self._handle_response(response)
            for line in response.iter_lines():
                if line.startswith("data: "):
                    chunk = line[6:]
                    if chunk != "[DONE]":
                        yield chunk

    # API Keys methods

    def list_api_keys(self) -> list[APIKeyInfo]:
        """List all API keys for current user."""
        response = self._client.get(
            f"{self.base_url}/auth/api-keys",
            headers=self._headers(),
        )
        data = self._handle_response(response)
        from datetime import datetime

        return [
            APIKeyInfo(
                key_id=k["key_id"],
                name=k["name"],
                scopes=k["scopes"],
                created_at=datetime.fromisoformat(k["created_at"].replace("Z", "+00:00")),
                last_used=datetime.fromisoformat(k["last_used"].replace("Z", "+00:00"))
                if k.get("last_used")
                else None,
            )
            for k in data
        ]

    def create_api_key(
        self, name: str, scopes: list[str] | None = None
    ) -> tuple[str, APIKeyInfo]:
        """
        Create a new API key.

        Returns:
            Tuple of (key_value, key_info). The key value is only shown once!
        """
        params = {"name": name}
        if scopes:
            params["scopes"] = ",".join(scopes)

        response = self._client.post(
            f"{self.base_url}/auth/api-keys",
            headers=self._headers(),
            params=params,
        )
        data = self._handle_response(response)
        from datetime import datetime

        key_info = APIKeyInfo(
            key_id=data["key_id"],
            name=data["name"],
            scopes=data["scopes"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
        )
        return data["key"], key_info

    def delete_api_key(self, key_id: str) -> None:
        """Delete an API key."""
        response = self._client.delete(
            f"{self.base_url}/auth/api-keys/{key_id}",
            headers=self._headers(),
        )
        self._handle_response(response)

    # Audit logs

    def get_audit_logs(
        self,
        limit: int = 50,
        action: str | None = None,
        success: bool | None = None,
    ) -> list[AuditEvent]:
        """Get audit logs (requires admin scope)."""
        params: dict[str, Any] = {"limit": limit}
        if action:
            params["action"] = action
        if success is not None:
            params["success"] = success

        response = self._client.get(
            f"{self.base_url}/v1/audit/logs",
            headers=self._headers(),
            params=params,
        )
        data = self._handle_response(response)
        return [
            AuditEvent(
                timestamp=e["timestamp"],
                action=e["action"],
                severity=e["severity"],
                success=e["success"],
                username=e.get("username"),
                resource=e.get("resource"),
                client_ip=e.get("client_ip"),
                auth_type=e.get("auth_type"),
                duration_ms=e.get("duration_ms"),
                error_message=e.get("error_message"),
            )
            for e in data
        ]


class AsyncRClient:
    """Asynchronous client for R CLI API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize async R CLI client.

        Args:
            base_url: Base URL of the R CLI API server
            api_key: API key for authentication
            token: JWT token for authentication (alternative to api_key)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.token = token
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    def _headers(self) -> dict[str, str]:
        """Get request headers with auth."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        elif self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _handle_response(self, response: httpx.Response) -> Any:
        """Handle API response and raise appropriate exceptions."""
        if response.status_code == 401:
            raise AuthError("Authentication required", 401)
        if response.status_code == 403:
            raise AuthError("Permission denied", 403)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                "Rate limit exceeded",
                retry_after=float(retry_after) if retry_after else None,
            )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise APIError(str(detail), response.status_code)
        return response.json()

    async def close(self) -> None:
        """Close the client."""
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncRClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # Auth methods

    async def login(self, username: str, password: str) -> str:
        """Login with username and password."""
        response = await self._client.post(
            f"{self.base_url}/auth/token",
            data={"username": username, "password": password},
        )
        data = self._handle_response(response)
        self.token = data["access_token"]
        return self.token

    async def get_me(self) -> AuthUser:
        """Get current authenticated user info."""
        response = await self._client.get(
            f"{self.base_url}/auth/me",
            headers=self._headers(),
        )
        data = self._handle_response(response)
        return AuthUser(
            user_id=data["user_id"],
            username=data["username"],
            scopes=data["scopes"],
            auth_type=data["auth_type"],
        )

    # Status methods

    async def health(self) -> dict[str, str]:
        """Check server health."""
        response = await self._client.get(f"{self.base_url}/health")
        return self._handle_response(response)

    async def status(self) -> StatusResponse:
        """Get detailed server status."""
        response = await self._client.get(
            f"{self.base_url}/v1/status",
            headers=self._headers(),
        )
        data = self._handle_response(response)
        return StatusResponse(
            status=data["status"],
            version=data["version"],
            uptime_seconds=data["uptime_seconds"],
            llm=LLMStatus(
                connected=data["llm"]["connected"],
                provider=data["llm"].get("provider"),
                model=data["llm"].get("model"),
                base_url=data["llm"].get("base_url"),
            ),
            skills_loaded=data["skills_loaded"],
            timestamp=data["timestamp"],
        )

    # Skills methods

    async def list_skills(self) -> list[SkillInfo]:
        """List all available skills."""
        response = await self._client.get(
            f"{self.base_url}/v1/skills",
            headers=self._headers(),
        )
        data = self._handle_response(response)
        return [
            SkillInfo(
                name=s["name"],
                description=s["description"],
                version=s["version"],
                category=s["category"],
                enabled=s["enabled"],
                tools=[
                    ToolInfo(
                        name=t["name"],
                        description=t["description"],
                        parameters=t["parameters"],
                    )
                    for t in s.get("tools", [])
                ],
            )
            for s in data
        ]

    async def get_skill(self, name: str) -> SkillInfo:
        """Get a specific skill by name."""
        response = await self._client.get(
            f"{self.base_url}/v1/skills/{name}",
            headers=self._headers(),
        )
        data = self._handle_response(response)
        return SkillInfo(
            name=data["name"],
            description=data["description"],
            version=data["version"],
            category=data["category"],
            enabled=data["enabled"],
            tools=[
                ToolInfo(
                    name=t["name"],
                    description=t["description"],
                    parameters=t["parameters"],
                )
                for t in data.get("tools", [])
            ],
        )

    # Chat methods

    async def chat(
        self,
        message: str,
        history: list[ChatMessage] | None = None,
        skill: str | None = None,
    ) -> ChatResponse:
        """Send a chat message."""
        messages = []
        if history:
            messages.extend([{"role": m.role, "content": m.content} for m in history])
        messages.append({"role": "user", "content": message})

        payload: dict[str, Any] = {"messages": messages}
        if skill:
            payload["skill"] = skill

        response = await self._client.post(
            f"{self.base_url}/v1/chat",
            headers=self._headers(),
            json=payload,
        )
        data = self._handle_response(response)
        return ChatResponse(
            message=data["message"],
            skill_used=data.get("skill_used"),
            tools_called=[
                ToolCall(
                    name=t["name"],
                    arguments=t.get("arguments", {}),
                    result=t.get("result"),
                )
                for t in data.get("tools_called", [])
            ]
            if data.get("tools_called")
            else None,
            model=data.get("model"),
            usage=data.get("usage"),
        )

    # API Keys methods

    async def list_api_keys(self) -> list[APIKeyInfo]:
        """List all API keys for current user."""
        response = await self._client.get(
            f"{self.base_url}/auth/api-keys",
            headers=self._headers(),
        )
        data = self._handle_response(response)
        from datetime import datetime

        return [
            APIKeyInfo(
                key_id=k["key_id"],
                name=k["name"],
                scopes=k["scopes"],
                created_at=datetime.fromisoformat(k["created_at"].replace("Z", "+00:00")),
                last_used=datetime.fromisoformat(k["last_used"].replace("Z", "+00:00"))
                if k.get("last_used")
                else None,
            )
            for k in data
        ]

    async def create_api_key(
        self, name: str, scopes: list[str] | None = None
    ) -> tuple[str, APIKeyInfo]:
        """Create a new API key."""
        params = {"name": name}
        if scopes:
            params["scopes"] = ",".join(scopes)

        response = await self._client.post(
            f"{self.base_url}/auth/api-keys",
            headers=self._headers(),
            params=params,
        )
        data = self._handle_response(response)
        from datetime import datetime

        key_info = APIKeyInfo(
            key_id=data["key_id"],
            name=data["name"],
            scopes=data["scopes"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
        )
        return data["key"], key_info

    async def delete_api_key(self, key_id: str) -> None:
        """Delete an API key."""
        response = await self._client.delete(
            f"{self.base_url}/auth/api-keys/{key_id}",
            headers=self._headers(),
        )
        self._handle_response(response)

    # Audit logs

    async def get_audit_logs(
        self,
        limit: int = 50,
        action: str | None = None,
        success: bool | None = None,
    ) -> list[AuditEvent]:
        """Get audit logs (requires admin scope)."""
        params: dict[str, Any] = {"limit": limit}
        if action:
            params["action"] = action
        if success is not None:
            params["success"] = success

        response = await self._client.get(
            f"{self.base_url}/v1/audit/logs",
            headers=self._headers(),
            params=params,
        )
        data = self._handle_response(response)
        return [
            AuditEvent(
                timestamp=e["timestamp"],
                action=e["action"],
                severity=e["severity"],
                success=e["success"],
                username=e.get("username"),
                resource=e.get("resource"),
                client_ip=e.get("client_ip"),
                auth_type=e.get("auth_type"),
                duration_ms=e.get("duration_ms"),
                error_message=e.get("error_message"),
            )
            for e in data
        ]
