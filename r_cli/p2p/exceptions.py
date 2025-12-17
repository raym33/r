"""
P2P Exceptions for R CLI.
"""


class P2PError(Exception):
    """Base P2P exception."""


class PeerNotFoundError(P2PError):
    """Peer not found in registry."""

    def __init__(self, peer_id: str):
        self.peer_id = peer_id
        super().__init__(f"Peer not found: {peer_id}")


class PeerNotApprovedError(P2PError):
    """Peer has not been approved for communication."""

    def __init__(self, peer_id: str):
        self.peer_id = peer_id
        super().__init__(f"Peer not approved: {peer_id}")


class PeerAuthenticationError(P2PError):
    """Failed to authenticate with peer."""

    def __init__(self, peer_id: str, reason: str = ""):
        self.peer_id = peer_id
        self.reason = reason
        msg = f"Authentication failed with peer {peer_id}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class PeerConnectionError(P2PError):
    """Failed to connect to peer."""

    def __init__(self, peer_id: str, host: str, port: int, reason: str = ""):
        self.peer_id = peer_id
        self.host = host
        self.port = port
        self.reason = reason
        msg = f"Connection failed to peer {peer_id} ({host}:{port})"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class PeerTimeoutError(P2PError):
    """Peer request timed out."""

    def __init__(self, peer_id: str, timeout: float):
        self.peer_id = peer_id
        self.timeout = timeout
        super().__init__(f"Request to peer {peer_id} timed out after {timeout}s")


class SyncConflictError(P2PError):
    """Context synchronization conflict."""

    def __init__(self, peer_id: str, conflicts: list):
        self.peer_id = peer_id
        self.conflicts = conflicts
        super().__init__(f"Sync conflict with peer {peer_id}: {len(conflicts)} conflicts")


class PeerLimitExceededError(P2PError):
    """Maximum number of peers exceeded."""

    def __init__(self, max_peers: int):
        self.max_peers = max_peers
        super().__init__(f"Maximum peers exceeded: {max_peers}")


class PeerBlockedError(P2PError):
    """Peer is blocked."""

    def __init__(self, peer_id: str):
        self.peer_id = peer_id
        super().__init__(f"Peer is blocked: {peer_id}")
