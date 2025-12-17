"""
P2P API Models for R CLI.

Pydantic models for P2P request/response handling.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

# =============================================================================
# Peer Management
# =============================================================================


class PeerInfoResponse(BaseModel):
    """Basic peer information."""

    peer_id: str
    name: str
    status: str
    host: str
    port: int
    skills: list[str] = []
    capabilities: list[str] = []
    trust_level: int = 0
    last_seen: Optional[datetime] = None
    version: Optional[str] = None


class PeerListResponse(BaseModel):
    """List of peers."""

    peers: list[PeerInfoResponse]
    total: int


class AddPeerRequest(BaseModel):
    """Request to add a manual peer."""

    host: str
    port: int = 8765
    name: Optional[str] = None


class AddPeerResponse(BaseModel):
    """Response after adding a peer."""

    success: bool
    peer_id: str
    message: str


class ApprovalRequestInfo(BaseModel):
    """Pending approval request info."""

    request_id: str
    peer_id: str
    peer_name: str
    host: str
    port: int
    fingerprint: str
    discovery_method: str
    requested_at: datetime
    expires_at: datetime


class PendingApprovalsResponse(BaseModel):
    """List of pending approval requests."""

    requests: list[ApprovalRequestInfo]
    total: int


# =============================================================================
# Authentication
# =============================================================================


class PeerChallengeRequest(BaseModel):
    """Request for authentication challenge."""

    peer_id: str
    public_key: str


class PeerChallengeResponse(BaseModel):
    """Response with authentication challenge."""

    challenge: str
    our_peer_id: str
    our_public_key: str


class PeerAuthRequest(BaseModel):
    """Authentication response with signed challenge."""

    peer_id: str
    challenge: str
    response: str


class PeerAuthResponse(BaseModel):
    """Authentication result."""

    success: bool
    token: Optional[str] = None
    expires_at: Optional[datetime] = None
    error: Optional[str] = None


# =============================================================================
# Task Execution
# =============================================================================


class P2PTaskRequest(BaseModel):
    """Request to execute a task on this peer."""

    request_id: str
    task: str
    agent: Optional[str] = None
    context: dict = {}
    requester_id: str


class P2PTaskResponse(BaseModel):
    """Response from task execution."""

    request_id: str
    result: str
    agent_used: Optional[str] = None
    execution_time_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None


# =============================================================================
# Skill Invocation
# =============================================================================


class P2PSkillRequest(BaseModel):
    """Request to invoke a skill on this peer."""

    request_id: str
    skill: str
    tool: str
    arguments: dict[str, Any] = {}
    requester_id: str


class P2PSkillResponse(BaseModel):
    """Response from skill invocation."""

    request_id: str
    result: Any = None
    execution_time_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None


class SkillInfoResponse(BaseModel):
    """Information about a skill."""

    name: str
    description: str
    tools: list[str]


class SkillsListResponse(BaseModel):
    """List of available skills."""

    skills: list[SkillInfoResponse]
    total: int


# =============================================================================
# Context Sync
# =============================================================================


class ContextSyncRequest(BaseModel):
    """Request for context synchronization."""

    direction: str  # "send" (peer wants our data) or "receive" (peer sending data)
    scope: str = "session"  # "session", "memory", "all"
    since: Optional[datetime] = None  # For incremental sync
    data: Optional[dict] = None  # Context data if direction="receive"


class ContextSyncResponse(BaseModel):
    """Response from context sync."""

    success: bool
    direction: str
    entries_processed: int = 0
    data: Optional[dict] = None  # Context data if direction="send"
    error: Optional[str] = None


# =============================================================================
# Status
# =============================================================================


class P2PStatusResponse(BaseModel):
    """P2P system status."""

    enabled: bool
    peer_id: str
    fingerprint: str
    discovery_running: bool
    advertising: bool
    total_peers: int
    approved_peers: int
    pending_approvals: int
    active_connections: int
