"""
P2P Client for R CLI.

HTTP client for peer-to-peer communication with authentication,
retries, and error handling.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Optional

import httpx
from pydantic import BaseModel

from r_cli.p2p.peer import Peer, PeerCapability
from r_cli.p2p.registry import PeerRegistry
from r_cli.p2p.security import P2PSecurity
from r_cli.p2p.exceptions import (
    PeerConnectionError,
    PeerTimeoutError,
    PeerAuthenticationError,
    PeerNotApprovedError,
)

logger = logging.getLogger(__name__)


class P2PResponse(BaseModel):
    """Response from a P2P request."""

    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    peer_id: str = ""


class PeerInfo(BaseModel):
    """Information about a peer."""

    peer_id: str
    name: str
    version: str
    skills: list[str]
    capabilities: list[str]
    status: str


class SkillInfo(BaseModel):
    """Information about a remote skill."""

    name: str
    description: str
    tools: list[str]


class TaskResult(BaseModel):
    """Result of a remote task execution."""

    request_id: str
    result: str
    agent_used: Optional[str] = None
    execution_time_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None


class ToolResult(BaseModel):
    """Result of a remote tool invocation."""

    request_id: str
    result: Any
    execution_time_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None


class PingResult(BaseModel):
    """Result of a ping to a peer."""

    peer_id: str
    reachable: bool
    latency_ms: float = 0.0
    error: Optional[str] = None


class P2PClient:
    """
    HTTP client for peer-to-peer communication.

    Handles:
    - Authentication with peer tokens
    - Automatic retries
    - Connection pooling
    - Error handling and circuit breaking
    """

    DEFAULT_TIMEOUT = 30.0
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0

    def __init__(
        self,
        registry: PeerRegistry,
        security: P2PSecurity,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.registry = registry
        self.security = security
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # Authentication
    # =========================================================================

    async def authenticate(self, peer: Peer) -> str:
        """
        Authenticate with a peer and get a session token.

        Uses challenge-response authentication.
        """
        if not peer.is_trusted:
            raise PeerNotApprovedError(peer.peer_id)

        client = await self._get_client()

        try:
            # Step 1: Request challenge
            response = await client.post(
                f"{peer.url}/v1/p2p/auth/challenge",
                json={
                    "peer_id": self.security.instance_id,
                    "public_key": self.security.instance_key[:32],  # Send partial key
                },
            )

            if response.status_code != 200:
                raise PeerAuthenticationError(peer.peer_id, f"Challenge failed: {response.status_code}")

            challenge_data = response.json()
            challenge = challenge_data.get("challenge")
            peer_key = challenge_data.get("our_public_key", "")[:32]

            # Store peer's key if we don't have it
            if not peer.public_key and peer_key:
                peer.public_key = peer_key

            # Step 2: Respond to challenge
            challenge_response = self.security.respond_to_challenge(challenge, peer_key)

            response = await client.post(
                f"{peer.url}/v1/p2p/auth/respond",
                json={
                    "peer_id": self.security.instance_id,
                    "challenge": challenge,
                    "response": challenge_response,
                },
            )

            if response.status_code != 200:
                raise PeerAuthenticationError(peer.peer_id, f"Auth failed: {response.status_code}")

            auth_data = response.json()
            if not auth_data.get("success"):
                raise PeerAuthenticationError(peer.peer_id, auth_data.get("error", "Unknown error"))

            token = auth_data.get("token")
            expires_at = datetime.fromisoformat(auth_data.get("expires_at"))

            # Store connection
            self.registry.connect(peer.peer_id, token, expires_at)

            logger.info(f"Authenticated with peer: {peer.name}")
            return token

        except httpx.TimeoutException:
            raise PeerTimeoutError(peer.peer_id, self.timeout)
        except httpx.ConnectError as e:
            raise PeerConnectionError(peer.peer_id, peer.host, peer.port, str(e))

    async def _get_token(self, peer: Peer) -> str:
        """Get or refresh token for peer."""
        conn = self.registry.get_connection(peer.peer_id)

        if conn and conn.is_token_valid:
            return conn.session_token or ""

        # Need to authenticate
        return await self.authenticate(peer)

    # =========================================================================
    # Core Request Method
    # =========================================================================

    async def request(
        self,
        peer: Peer,
        method: str,
        path: str,
        data: Optional[dict] = None,
        timeout: Optional[float] = None,
        require_auth: bool = True,
    ) -> P2PResponse:
        """
        Make an authenticated request to a peer.

        Args:
            peer: Target peer
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., /v1/p2p/task)
            data: Request body (for POST)
            timeout: Request timeout
            require_auth: Whether to require authentication

        Returns:
            P2PResponse with success status and data
        """
        if require_auth and not peer.is_trusted:
            raise PeerNotApprovedError(peer.peer_id)

        client = await self._get_client()
        url = f"{peer.url}{path}"
        headers = {}

        # Get auth token if required
        if require_auth:
            try:
                token = await self._get_token(peer)
                headers["Authorization"] = f"Bearer {token}"
                headers["X-Peer-ID"] = self.security.instance_id
            except Exception as e:
                return P2PResponse(
                    success=False,
                    error=f"Authentication failed: {e}",
                    peer_id=peer.peer_id,
                )

        # Make request with retries
        last_error = None
        start_time = time.time()

        for attempt in range(self.MAX_RETRIES):
            try:
                if method.upper() == "GET":
                    response = await client.get(
                        url,
                        headers=headers,
                        timeout=timeout or self.timeout,
                    )
                else:
                    response = await client.request(
                        method,
                        url,
                        headers=headers,
                        json=data,
                        timeout=timeout or self.timeout,
                    )

                latency = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    peer.update_stats(success=True, latency_ms=latency)
                    return P2PResponse(
                        success=True,
                        data=response.json(),
                        latency_ms=latency,
                        peer_id=peer.peer_id,
                    )
                elif response.status_code == 401:
                    # Token expired, re-authenticate
                    self.registry.disconnect(peer.peer_id)
                    token = await self._get_token(peer)
                    headers["Authorization"] = f"Bearer {token}"
                    continue
                else:
                    error_data = response.json() if response.content else {}
                    peer.update_stats(success=False, latency_ms=latency)
                    return P2PResponse(
                        success=False,
                        error=error_data.get("detail", f"HTTP {response.status_code}"),
                        latency_ms=latency,
                        peer_id=peer.peer_id,
                    )

            except httpx.TimeoutException:
                last_error = f"Request timed out after {timeout or self.timeout}s"
            except httpx.ConnectError as e:
                last_error = f"Connection failed: {e}"
            except Exception as e:
                last_error = str(e)

            # Wait before retry
            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))

        # All retries failed
        latency = (time.time() - start_time) * 1000
        peer.update_stats(success=False, latency_ms=latency)

        return P2PResponse(
            success=False,
            error=last_error,
            latency_ms=latency,
            peer_id=peer.peer_id,
        )

    # =========================================================================
    # High-level Operations
    # =========================================================================

    async def get_peer_info(self, peer: Peer) -> Optional[PeerInfo]:
        """Get peer's status and capabilities."""
        response = await self.request(peer, "GET", "/v1/p2p/info", require_auth=False)

        if response.success and response.data:
            return PeerInfo(**response.data)
        return None

    async def get_peer_skills(self, peer: Peer) -> list[SkillInfo]:
        """Get list of skills available on peer."""
        response = await self.request(peer, "GET", "/v1/p2p/skills")

        if response.success and response.data:
            skills = response.data.get("skills", [])
            return [SkillInfo(**s) for s in skills]
        return []

    async def execute_remote_task(
        self,
        peer: Peer,
        task: str,
        agent: Optional[str] = None,
        context: Optional[dict] = None,
        timeout: float = 120.0,
    ) -> TaskResult:
        """
        Execute a task on a remote peer.

        Args:
            peer: Target peer
            task: Task description
            agent: Specific agent to use (optional)
            context: Additional context (optional)
            timeout: Task timeout

        Returns:
            TaskResult with execution results
        """
        if not peer.can_execute_tasks:
            return TaskResult(
                request_id="",
                result="",
                success=False,
                error="Peer cannot execute tasks (insufficient trust or capability)",
            )

        import uuid

        request_id = str(uuid.uuid4())

        response = await self.request(
            peer,
            "POST",
            "/v1/p2p/task",
            data={
                "request_id": request_id,
                "task": task,
                "agent": agent,
                "context": context or {},
                "requester_id": self.security.instance_id,
            },
            timeout=timeout,
        )

        if response.success and response.data:
            return TaskResult(
                request_id=request_id,
                result=response.data.get("result", ""),
                agent_used=response.data.get("agent_used"),
                execution_time_ms=response.data.get("execution_time_ms", response.latency_ms),
                success=True,
            )
        else:
            return TaskResult(
                request_id=request_id,
                result="",
                success=False,
                error=response.error,
                execution_time_ms=response.latency_ms,
            )

    async def invoke_remote_skill(
        self,
        peer: Peer,
        skill_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float = 60.0,
    ) -> ToolResult:
        """
        Invoke a specific skill/tool on a remote peer.

        Args:
            peer: Target peer
            skill_name: Name of the skill
            tool_name: Name of the tool within the skill
            arguments: Tool arguments
            timeout: Request timeout

        Returns:
            ToolResult with tool output
        """
        if not peer.can_share_skills:
            return ToolResult(
                request_id="",
                result=None,
                success=False,
                error="Peer cannot share skills (insufficient trust or capability)",
            )

        import uuid

        request_id = str(uuid.uuid4())

        response = await self.request(
            peer,
            "POST",
            "/v1/p2p/skill",
            data={
                "request_id": request_id,
                "skill": skill_name,
                "tool": tool_name,
                "arguments": arguments,
                "requester_id": self.security.instance_id,
            },
            timeout=timeout,
        )

        if response.success and response.data:
            return ToolResult(
                request_id=request_id,
                result=response.data.get("result"),
                execution_time_ms=response.data.get("execution_time_ms", response.latency_ms),
                success=True,
            )
        else:
            return ToolResult(
                request_id=request_id,
                result=None,
                success=False,
                error=response.error,
                execution_time_ms=response.latency_ms,
            )

    # =========================================================================
    # Health Checks
    # =========================================================================

    async def ping(self, peer: Peer) -> PingResult:
        """Check if a peer is alive and measure latency."""
        start = time.time()

        try:
            client = await self._get_client()
            response = await client.get(f"{peer.url}/health", timeout=5.0)

            latency = (time.time() - start) * 1000

            if response.status_code == 200:
                peer.last_seen = datetime.now()
                return PingResult(
                    peer_id=peer.peer_id,
                    reachable=True,
                    latency_ms=latency,
                )
            else:
                return PingResult(
                    peer_id=peer.peer_id,
                    reachable=False,
                    latency_ms=latency,
                    error=f"HTTP {response.status_code}",
                )

        except Exception as e:
            latency = (time.time() - start) * 1000
            return PingResult(
                peer_id=peer.peer_id,
                reachable=False,
                latency_ms=latency,
                error=str(e),
            )

    async def health_check_all(self) -> dict[str, PingResult]:
        """Health check all approved peers concurrently."""
        peers = self.registry.list_peers()
        approved = [p for p in peers if p.is_trusted or p.status.value == "offline"]

        if not approved:
            return {}

        # Run pings concurrently
        tasks = [self.ping(peer) for peer in approved]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dict
        result_dict = {}
        for peer, result in zip(approved, results):
            if isinstance(result, Exception):
                result_dict[peer.peer_id] = PingResult(
                    peer_id=peer.peer_id,
                    reachable=False,
                    error=str(result),
                )
            else:
                result_dict[peer.peer_id] = result

            # Update peer status based on reachability
            if isinstance(result, PingResult):
                if result.reachable:
                    self.registry.set_online(peer.peer_id)
                else:
                    self.registry.set_offline(peer.peer_id)

        return result_dict
