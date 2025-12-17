"""
P2P Distributed Agents for R CLI.

Enables multiple R CLI instances to discover each other,
share skills, distribute tasks, and synchronize context.
"""

from r_cli.p2p.exceptions import (
    P2PError,
    PeerAuthenticationError,
    PeerConnectionError,
    PeerNotApprovedError,
    PeerNotFoundError,
    PeerTimeoutError,
    SyncConflictError,
)
from r_cli.p2p.peer import Peer, PeerCapability, PeerConnection, PeerStatus
from r_cli.p2p.registry import PeerRegistry
from r_cli.p2p.security import P2PSecurity

__all__ = [
    "P2PError",
    "P2PSecurity",
    "Peer",
    "PeerAuthenticationError",
    "PeerCapability",
    "PeerConnection",
    "PeerConnectionError",
    "PeerNotApprovedError",
    "PeerNotFoundError",
    "PeerRegistry",
    "PeerStatus",
    "PeerTimeoutError",
    "SyncConflictError",
]
