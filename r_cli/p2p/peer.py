"""
Peer Model for R CLI P2P.

Defines the Peer data model and related types for
distributed agent communication.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PeerStatus(str, Enum):
    """Peer connection status."""

    DISCOVERED = "discovered"  # Found via mDNS, not yet contacted
    PENDING = "pending"  # Awaiting user approval
    APPROVED = "approved"  # Trusted and can communicate
    REJECTED = "rejected"  # User rejected this peer
    OFFLINE = "offline"  # Approved but currently unreachable
    BLOCKED = "blocked"  # Permanently blocked


class PeerCapability(str, Enum):
    """Capabilities a peer can offer."""

    TASK_EXECUTION = "task_execution"  # Can execute tasks
    SKILL_SHARING = "skill_sharing"  # Shares skills remotely
    CONTEXT_SYNC = "context_sync"  # Can sync context/memory
    REMOTE_AGENT = "remote_agent"  # Full agent access


class Peer(BaseModel):
    """
    Represents a remote R CLI peer.

    Contains all information needed to identify, authenticate,
    and communicate with another R CLI instance.
    """

    # Identity
    peer_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(default="Unknown Peer")
    host: str
    port: int = 8765

    # Status
    status: PeerStatus = PeerStatus.DISCOVERED

    # Discovery metadata
    discovered_at: datetime = Field(default_factory=datetime.now)
    discovered_via: str = "manual"  # "mdns" or "manual"
    last_seen: Optional[datetime] = None
    last_error: Optional[str] = None

    # Security
    public_key: Optional[str] = None  # PEM-encoded public key
    fingerprint: Optional[str] = None  # Key fingerprint for display
    trust_level: int = 0  # 0-100, increases with successful interactions

    # Approval
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    # Capabilities
    capabilities: list[PeerCapability] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)  # Remote skill names
    version: Optional[str] = None  # R CLI version

    # Connection stats
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: float = 0.0
    total_requests: int = 0

    @property
    def url(self) -> str:
        """Get the base URL for this peer."""
        return f"http://{self.host}:{self.port}"

    @property
    def is_trusted(self) -> bool:
        """Check if peer is approved and can be communicated with."""
        return self.status == PeerStatus.APPROVED

    @property
    def is_online(self) -> bool:
        """Check if peer appears to be online."""
        return self.status in (PeerStatus.APPROVED, PeerStatus.PENDING)

    @property
    def can_execute_tasks(self) -> bool:
        """Check if peer can execute tasks."""
        return (
            self.is_trusted
            and PeerCapability.TASK_EXECUTION in self.capabilities
            and self.trust_level >= 50
        )

    @property
    def can_share_skills(self) -> bool:
        """Check if peer can share skills."""
        return (
            self.is_trusted
            and PeerCapability.SKILL_SHARING in self.capabilities
            and self.trust_level >= 50
        )

    @property
    def can_sync_context(self) -> bool:
        """Check if peer can sync context."""
        return (
            self.is_trusted
            and PeerCapability.CONTEXT_SYNC in self.capabilities
            and self.trust_level >= 75
        )

    def update_stats(self, success: bool, latency_ms: float) -> None:
        """Update connection statistics after a request."""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
            # Increase trust on success (max 100)
            if self.trust_level < 100:
                self.trust_level = min(100, self.trust_level + 1)
        else:
            self.failed_requests += 1
            # Decrease trust on failure (min 0)
            if self.trust_level > 0:
                self.trust_level = max(0, self.trust_level - 5)

        # Update average latency (exponential moving average)
        if self.avg_latency_ms == 0:
            self.avg_latency_ms = latency_ms
        else:
            self.avg_latency_ms = 0.9 * self.avg_latency_ms + 0.1 * latency_ms

        self.last_seen = datetime.now()

    def to_summary(self) -> dict:
        """Get a summary of the peer for display."""
        return {
            "peer_id": self.peer_id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "status": self.status.value,
            "trust_level": self.trust_level,
            "skills": self.skills,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


class PeerConnection(BaseModel):
    """Active connection to a peer."""

    peer: Peer
    connected_at: datetime = Field(default_factory=datetime.now)
    session_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None

    @property
    def is_token_valid(self) -> bool:
        """Check if the session token is still valid."""
        if not self.session_token or not self.token_expires_at:
            return False
        return datetime.now() < self.token_expires_at


class ApprovalRequest(BaseModel):
    """Peer approval request for user review."""

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    peer: Peer
    requested_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime
    fingerprint: str  # Key fingerprint for verification
    discovery_method: str  # "mdns" or "manual"
    message: Optional[str] = None  # Optional message from requesting peer

    @property
    def is_expired(self) -> bool:
        """Check if the approval request has expired."""
        return datetime.now() > self.expires_at
