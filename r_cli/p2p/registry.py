"""
Peer Registry for R CLI P2P.

Manages known peers with file-based persistence.
Storage: ~/.r-cli/peers.json
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from r_cli.p2p.peer import (
    Peer,
    PeerStatus,
    PeerCapability,
    PeerConnection,
    ApprovalRequest,
)
from r_cli.p2p.exceptions import (
    PeerNotFoundError,
    PeerNotApprovedError,
    PeerLimitExceededError,
    PeerBlockedError,
)

logger = logging.getLogger(__name__)


class PeerRegistry:
    """
    Manages known peers with file-based persistence.

    Features:
    - CRUD operations for peers
    - Status management (approve, reject, block)
    - Connection tracking
    - JSON persistence to ~/.r-cli/peers.json
    - Skill-based peer lookup
    """

    DEFAULT_STORAGE_PATH = "~/.r-cli/peers.json"
    MAX_PEERS_DEFAULT = 20

    def __init__(
        self,
        storage_path: Optional[str] = None,
        max_peers: int = MAX_PEERS_DEFAULT,
    ):
        self.storage_path = Path(storage_path or self.DEFAULT_STORAGE_PATH).expanduser()
        self.max_peers = max_peers
        self.peers: dict[str, Peer] = {}
        self.connections: dict[str, PeerConnection] = {}
        self.pending_approvals: dict[str, ApprovalRequest] = {}
        self._load()

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def add_peer(self, peer: Peer) -> bool:
        """
        Add a new peer to the registry.

        Returns True if added, False if already exists.
        Raises PeerLimitExceededError if max peers reached.
        """
        if peer.peer_id in self.peers:
            logger.warning(f"Peer {peer.peer_id} already exists")
            return False

        # Check peer limit (excluding blocked/rejected)
        active_peers = [
            p
            for p in self.peers.values()
            if p.status not in (PeerStatus.BLOCKED, PeerStatus.REJECTED)
        ]
        if len(active_peers) >= self.max_peers:
            raise PeerLimitExceededError(self.max_peers)

        self.peers[peer.peer_id] = peer
        self._save()
        logger.info(f"Added peer: {peer.name} ({peer.peer_id})")
        return True

    def get_peer(self, peer_id: str) -> Optional[Peer]:
        """Get a peer by ID."""
        return self.peers.get(peer_id)

    def get_peer_or_raise(self, peer_id: str) -> Peer:
        """Get a peer by ID or raise PeerNotFoundError."""
        peer = self.get_peer(peer_id)
        if not peer:
            raise PeerNotFoundError(peer_id)
        return peer

    def update_peer(self, peer_id: str, updates: dict) -> bool:
        """
        Update peer fields.

        Returns True if updated, False if peer not found.
        """
        peer = self.get_peer(peer_id)
        if not peer:
            return False

        for key, value in updates.items():
            if hasattr(peer, key):
                setattr(peer, key, value)

        self._save()
        return True

    def remove_peer(self, peer_id: str) -> bool:
        """
        Remove a peer from the registry.

        Returns True if removed, False if not found.
        """
        if peer_id not in self.peers:
            return False

        # Also remove any connection
        if peer_id in self.connections:
            del self.connections[peer_id]

        del self.peers[peer_id]
        self._save()
        logger.info(f"Removed peer: {peer_id}")
        return True

    def list_peers(self, status: Optional[PeerStatus] = None) -> list[Peer]:
        """
        List peers, optionally filtered by status.

        Args:
            status: Filter by this status, or None for all peers
        """
        peers = list(self.peers.values())
        if status:
            peers = [p for p in peers if p.status == status]
        return sorted(peers, key=lambda p: p.name)

    # =========================================================================
    # Status Management
    # =========================================================================

    def approve_peer(self, peer_id: str, approved_by: str) -> bool:
        """
        Approve a pending peer for trusted communication.

        Sets status to APPROVED and records approval info.
        """
        peer = self.get_peer_or_raise(peer_id)

        if peer.status == PeerStatus.BLOCKED:
            raise PeerBlockedError(peer_id)

        peer.status = PeerStatus.APPROVED
        peer.approved_by = approved_by
        peer.approved_at = datetime.now()
        peer.trust_level = 50  # Start with basic trust

        # Add default capabilities
        if not peer.capabilities:
            peer.capabilities = [
                PeerCapability.TASK_EXECUTION,
                PeerCapability.SKILL_SHARING,
            ]

        # Remove from pending approvals
        self._remove_pending_approval(peer_id)

        self._save()
        logger.info(f"Approved peer: {peer.name} ({peer_id}) by {approved_by}")
        return True

    def reject_peer(self, peer_id: str) -> bool:
        """
        Reject a pending peer.

        Sets status to REJECTED.
        """
        peer = self.get_peer_or_raise(peer_id)
        peer.status = PeerStatus.REJECTED

        # Remove from pending approvals
        self._remove_pending_approval(peer_id)

        self._save()
        logger.info(f"Rejected peer: {peer.name} ({peer_id})")
        return True

    def block_peer(self, peer_id: str) -> bool:
        """
        Block a peer permanently.

        Sets status to BLOCKED.
        """
        peer = self.get_peer_or_raise(peer_id)
        peer.status = PeerStatus.BLOCKED
        peer.trust_level = 0

        # Disconnect if connected
        if peer_id in self.connections:
            del self.connections[peer_id]

        self._save()
        logger.info(f"Blocked peer: {peer.name} ({peer_id})")
        return True

    def set_offline(self, peer_id: str) -> bool:
        """Mark a peer as offline."""
        peer = self.get_peer(peer_id)
        if peer and peer.status == PeerStatus.APPROVED:
            peer.status = PeerStatus.OFFLINE
            self._save()
            return True
        return False

    def set_online(self, peer_id: str) -> bool:
        """Mark a peer as online (approved)."""
        peer = self.get_peer(peer_id)
        if peer and peer.status == PeerStatus.OFFLINE:
            peer.status = PeerStatus.APPROVED
            peer.last_seen = datetime.now()
            self._save()
            return True
        return False

    # =========================================================================
    # Connection Management
    # =========================================================================

    def connect(self, peer_id: str, session_token: str, expires_at: datetime) -> PeerConnection:
        """
        Create an active connection to a peer.

        Raises PeerNotApprovedError if peer is not approved.
        """
        peer = self.get_peer_or_raise(peer_id)

        if not peer.is_trusted:
            raise PeerNotApprovedError(peer_id)

        connection = PeerConnection(
            peer=peer,
            session_token=session_token,
            token_expires_at=expires_at,
            last_heartbeat=datetime.now(),
        )
        self.connections[peer_id] = connection
        return connection

    def disconnect(self, peer_id: str) -> bool:
        """Disconnect from a peer."""
        if peer_id in self.connections:
            del self.connections[peer_id]
            return True
        return False

    def get_connection(self, peer_id: str) -> Optional[PeerConnection]:
        """Get active connection for a peer."""
        return self.connections.get(peer_id)

    def get_active_connections(self) -> list[PeerConnection]:
        """Get all active connections."""
        return list(self.connections.values())

    def update_heartbeat(self, peer_id: str) -> bool:
        """Update the heartbeat timestamp for a connection."""
        conn = self.connections.get(peer_id)
        if conn:
            conn.last_heartbeat = datetime.now()
            conn.peer.last_seen = datetime.now()
            return True
        return False

    # =========================================================================
    # Approval Requests
    # =========================================================================

    def add_approval_request(self, request: ApprovalRequest) -> bool:
        """Add a pending approval request."""
        if request.peer.peer_id in self.pending_approvals:
            return False

        self.pending_approvals[request.peer.peer_id] = request
        return True

    def get_pending_approvals(self) -> list[ApprovalRequest]:
        """Get all pending approval requests, removing expired ones."""
        # Clean up expired requests
        now = datetime.now()
        expired = [
            peer_id
            for peer_id, req in self.pending_approvals.items()
            if req.is_expired
        ]
        for peer_id in expired:
            del self.pending_approvals[peer_id]

        return list(self.pending_approvals.values())

    def _remove_pending_approval(self, peer_id: str) -> None:
        """Remove a pending approval request."""
        if peer_id in self.pending_approvals:
            del self.pending_approvals[peer_id]

    # =========================================================================
    # Queries
    # =========================================================================

    def find_peers_with_skill(self, skill_name: str) -> list[Peer]:
        """Find all approved peers that have a specific skill."""
        return [
            peer
            for peer in self.peers.values()
            if peer.is_trusted and skill_name in peer.skills
        ]

    def get_best_peer_for_skill(self, skill_name: str) -> Optional[Peer]:
        """
        Get the best peer for a specific skill.

        Considers trust level, latency, and availability.
        """
        candidates = self.find_peers_with_skill(skill_name)
        if not candidates:
            return None

        # Score by trust level and inverse latency
        def score(peer: Peer) -> float:
            latency_factor = 1.0 / (1.0 + peer.avg_latency_ms / 1000)
            return peer.trust_level * latency_factor

        return max(candidates, key=score)

    def find_peers_with_capability(self, capability: PeerCapability) -> list[Peer]:
        """Find all approved peers with a specific capability."""
        return [
            peer
            for peer in self.peers.values()
            if peer.is_trusted and capability in peer.capabilities
        ]

    def get_online_peers(self) -> list[Peer]:
        """Get all peers that are currently online."""
        return [peer for peer in self.peers.values() if peer.is_online]

    # =========================================================================
    # Persistence
    # =========================================================================

    def _load(self) -> None:
        """Load peers from JSON file."""
        if not self.storage_path.exists():
            logger.debug(f"No peers file at {self.storage_path}")
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            for peer_data in data.get("peers", []):
                try:
                    # Convert datetime strings
                    for field in ["discovered_at", "last_seen", "approved_at"]:
                        if peer_data.get(field):
                            peer_data[field] = datetime.fromisoformat(peer_data[field])

                    peer = Peer(**peer_data)
                    self.peers[peer.peer_id] = peer
                except Exception as e:
                    logger.warning(f"Failed to load peer: {e}")

            logger.info(f"Loaded {len(self.peers)} peers from {self.storage_path}")

        except Exception as e:
            logger.error(f"Failed to load peers file: {e}")

    def _save(self) -> None:
        """Save peers to JSON file."""
        try:
            # Ensure directory exists
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            peers_data = []
            for peer in self.peers.values():
                data = peer.model_dump()
                # Convert datetime to ISO format
                for field in ["discovered_at", "last_seen", "approved_at"]:
                    if data.get(field):
                        data[field] = data[field].isoformat()
                # Convert enums to strings
                data["status"] = data["status"].value if hasattr(data["status"], "value") else data["status"]
                data["capabilities"] = [
                    c.value if hasattr(c, "value") else c for c in data.get("capabilities", [])
                ]
                peers_data.append(data)

            with open(self.storage_path, "w") as f:
                json.dump({"peers": peers_data}, f, indent=2)

            logger.debug(f"Saved {len(peers_data)} peers to {self.storage_path}")

        except Exception as e:
            logger.error(f"Failed to save peers file: {e}")

    def clear(self) -> None:
        """Clear all peers and connections."""
        self.peers.clear()
        self.connections.clear()
        self.pending_approvals.clear()
        self._save()
