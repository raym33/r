"""
P2P Distributed Agents for R CLI.

Enables multiple R CLI instances to discover each other,
share skills, distribute tasks, and synchronize context.
"""

from r_cli.p2p.peer import Peer, PeerStatus, PeerCapability, PeerConnection
from r_cli.p2p.registry import PeerRegistry
from r_cli.p2p.security import P2PSecurity
from r_cli.p2p.exceptions import (
    P2PError,
    PeerNotFoundError,
    PeerNotApprovedError,
    PeerAuthenticationError,
    PeerConnectionError,
    PeerTimeoutError,
    SyncConflictError,
)

__all__ = [
    # Peer models
    "Peer",
    "PeerStatus",
    "PeerCapability",
    "PeerConnection",
    # Core components
    "PeerRegistry",
    "P2PSecurity",
    # Exceptions
    "P2PError",
    "PeerNotFoundError",
    "PeerNotApprovedError",
    "PeerAuthenticationError",
    "PeerConnectionError",
    "PeerTimeoutError",
    "SyncConflictError",
]
