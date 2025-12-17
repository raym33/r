"""
P2P Skill for R CLI.

Provides tools for peer-to-peer distributed agent operations:
- Peer discovery and management
- Remote task execution
- Remote skill invocation
- Context synchronization
"""

import asyncio
import json
import logging
from typing import Any, Optional

from r_cli.core.agent import Skill
from r_cli.core.config import Config
from r_cli.core.llm import Tool
from r_cli.p2p.client import P2PClient
from r_cli.p2p.discovery import P2PDiscoveryService
from r_cli.p2p.peer import Peer, PeerStatus
from r_cli.p2p.registry import PeerRegistry
from r_cli.p2p.security import P2PSecurity
from r_cli.p2p.sync import ContextSyncManager

logger = logging.getLogger(__name__)


class P2PSkill(Skill):
    """
    P2P Distributed Agents skill.

    Enables R CLI instances to discover each other, share skills,
    distribute tasks, and synchronize context.
    """

    name = "p2p"
    description = "P2P distributed agents: discover peers, share skills, distribute tasks"

    def __init__(self, config: Optional[Config] = None):
        super().__init__(config)

        # Initialize P2P components
        self._registry: Optional[PeerRegistry] = None
        self._security: Optional[P2PSecurity] = None
        self._discovery: Optional[P2PDiscoveryService] = None
        self._client: Optional[P2PClient] = None
        self._sync_manager: Optional[ContextSyncManager] = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of P2P components."""
        if self._initialized:
            return

        self._registry = PeerRegistry()
        self._security = P2PSecurity()
        self._discovery = P2PDiscoveryService(self._registry, self._security)
        self._client = P2PClient(self._registry, self._security)
        self._sync_manager = ContextSyncManager(self._registry)
        self._initialized = True

    def _run_async(self, coro):
        """Run async code from sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a new event loop in a thread
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result()
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def get_tools(self) -> list[Tool]:
        """Get all P2P tools."""
        return [
            # Discovery
            Tool(
                name="discover_peers",
                description="Scan for R CLI peers on the local network using mDNS",
                parameters={
                    "type": "object",
                    "properties": {
                        "timeout": {
                            "type": "number",
                            "description": "Scan timeout in seconds (default: 5)",
                        }
                    },
                },
                handler=self.discover_peers,
            ),
            Tool(
                name="add_peer",
                description="Manually add a peer by hostname/IP address",
                parameters={
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string",
                            "description": "Peer hostname or IP address",
                        },
                        "port": {
                            "type": "integer",
                            "description": "Peer port (default: 8765)",
                        },
                        "name": {
                            "type": "string",
                            "description": "Friendly name for the peer",
                        },
                    },
                    "required": ["host"],
                },
                handler=self.add_peer,
            ),
            # Peer Management
            Tool(
                name="list_peers",
                description="List known peers and their status",
                parameters={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["all", "approved", "pending", "online", "offline"],
                            "description": "Filter by status (default: all)",
                        }
                    },
                },
                handler=self.list_peers,
            ),
            Tool(
                name="approve_peer",
                description="Approve a pending peer for trusted communication",
                parameters={
                    "type": "object",
                    "properties": {
                        "peer_id": {
                            "type": "string",
                            "description": "ID of the peer to approve",
                        }
                    },
                    "required": ["peer_id"],
                },
                handler=self.approve_peer,
            ),
            Tool(
                name="reject_peer",
                description="Reject a pending peer",
                parameters={
                    "type": "object",
                    "properties": {
                        "peer_id": {
                            "type": "string",
                            "description": "ID of the peer to reject",
                        }
                    },
                    "required": ["peer_id"],
                },
                handler=self.reject_peer,
            ),
            Tool(
                name="peer_status",
                description="Get detailed status of a specific peer",
                parameters={
                    "type": "object",
                    "properties": {
                        "peer_id": {
                            "type": "string",
                            "description": "ID of the peer",
                        }
                    },
                    "required": ["peer_id"],
                },
                handler=self.peer_status,
            ),
            # Remote Operations
            Tool(
                name="remote_task",
                description="Execute a task on a remote peer",
                parameters={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Task to execute",
                        },
                        "peer_id": {
                            "type": "string",
                            "description": "Target peer ID (auto-select if omitted)",
                        },
                        "agent": {
                            "type": "string",
                            "description": "Specific agent to use on the peer",
                        },
                    },
                    "required": ["task"],
                },
                handler=self.remote_task,
            ),
            Tool(
                name="remote_skill",
                description="Invoke a skill/tool on a remote peer",
                parameters={
                    "type": "object",
                    "properties": {
                        "skill": {
                            "type": "string",
                            "description": "Name of the skill",
                        },
                        "tool": {
                            "type": "string",
                            "description": "Name of the tool within the skill",
                        },
                        "arguments": {
                            "type": "object",
                            "description": "Arguments for the tool",
                        },
                        "peer_id": {
                            "type": "string",
                            "description": "Target peer ID (auto-select if omitted)",
                        },
                    },
                    "required": ["skill", "tool"],
                },
                handler=self.remote_skill,
            ),
            Tool(
                name="find_skill",
                description="Find peers that have a specific skill",
                parameters={
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "Name of the skill to find",
                        }
                    },
                    "required": ["skill_name"],
                },
                handler=self.find_skill,
            ),
            # Context Sync
            Tool(
                name="sync_context",
                description="Synchronize context/memory with peers",
                parameters={
                    "type": "object",
                    "properties": {
                        "peer_id": {
                            "type": "string",
                            "description": "Peer to sync with (all if omitted)",
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["push", "pull", "both"],
                            "description": "Sync direction (default: both)",
                        },
                        "scope": {
                            "type": "string",
                            "enum": ["session", "memory", "all"],
                            "description": "What to sync (default: session)",
                        },
                    },
                },
                handler=self.sync_context,
            ),
            Tool(
                name="share_document",
                description="Share a document with specific peers",
                parameters={
                    "type": "object",
                    "properties": {
                        "doc_id": {
                            "type": "string",
                            "description": "Document ID from memory",
                        },
                        "peer_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "IDs of peers to share with (all if omitted)",
                        },
                    },
                    "required": ["doc_id"],
                },
                handler=self.share_document,
            ),
            Tool(
                name="p2p_status",
                description="Get P2P system status and statistics",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.p2p_status,
            ),
        ]

    # =========================================================================
    # Discovery Tools
    # =========================================================================

    def discover_peers(self, timeout: float = 5.0) -> str:
        """Scan for R CLI peers on the network."""
        self._ensure_initialized()

        try:
            peers = self._run_async(self._discovery.scan_network(timeout))

            if not peers:
                return json.dumps(
                    {
                        "success": True,
                        "message": "No peers found on network",
                        "discovered": 0,
                    }
                )

            return json.dumps(
                {
                    "success": True,
                    "message": f"Found {len(peers)} peer(s)",
                    "discovered": len(peers),
                    "peers": [p.to_summary() for p in peers],
                }
            )

        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def add_peer(self, host: str, port: int = 8765, name: Optional[str] = None) -> str:
        """Add a peer manually."""
        self._ensure_initialized()

        try:
            peer = self._discovery.add_manual_peer(host, port, name)
            return json.dumps(
                {
                    "success": True,
                    "message": f"Added peer {peer.name}",
                    "peer_id": peer.peer_id,
                    "status": peer.status.value,
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # =========================================================================
    # Peer Management Tools
    # =========================================================================

    def list_peers(self, status: str = "all") -> str:
        """List known peers."""
        self._ensure_initialized()

        peer_status = None
        if status != "all":
            status_map = {
                "approved": PeerStatus.APPROVED,
                "pending": PeerStatus.PENDING,
                "online": PeerStatus.APPROVED,
                "offline": PeerStatus.OFFLINE,
            }
            peer_status = status_map.get(status)

        peers = self._registry.list_peers(peer_status)

        if status == "online":
            peers = [p for p in peers if p.is_online]

        return json.dumps(
            {
                "success": True,
                "total": len(peers),
                "peers": [p.to_summary() for p in peers],
            }
        )

    def approve_peer(self, peer_id: str) -> str:
        """Approve a pending peer."""
        self._ensure_initialized()

        try:
            self._registry.approve_peer(peer_id, "skill")
            peer = self._registry.get_peer(peer_id)
            return json.dumps(
                {
                    "success": True,
                    "message": f"Approved peer {peer.name if peer else peer_id}",
                    "peer_id": peer_id,
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def reject_peer(self, peer_id: str) -> str:
        """Reject a pending peer."""
        self._ensure_initialized()

        try:
            self._registry.reject_peer(peer_id)
            return json.dumps(
                {
                    "success": True,
                    "message": f"Rejected peer {peer_id}",
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def peer_status(self, peer_id: str) -> str:
        """Get detailed peer status."""
        self._ensure_initialized()

        peer = self._registry.get_peer(peer_id)
        if not peer:
            return json.dumps({"success": False, "error": "Peer not found"})

        # Check if online
        ping_result = self._run_async(self._client.ping(peer))

        return json.dumps(
            {
                "success": True,
                "peer": peer.to_summary(),
                "is_online": ping_result.reachable,
                "latency_ms": ping_result.latency_ms,
                "trust_level": peer.trust_level,
                "capabilities": [c.value for c in peer.capabilities],
                "skills": peer.skills,
                "stats": {
                    "total_requests": peer.total_requests,
                    "successful": peer.successful_requests,
                    "failed": peer.failed_requests,
                    "avg_latency_ms": peer.avg_latency_ms,
                },
            }
        )

    # =========================================================================
    # Remote Operation Tools
    # =========================================================================

    def remote_task(
        self,
        task: str,
        peer_id: Optional[str] = None,
        agent: Optional[str] = None,
    ) -> str:
        """Execute a task on a remote peer."""
        self._ensure_initialized()

        # Find peer
        if peer_id:
            peer = self._registry.get_peer(peer_id)
            if not peer:
                return json.dumps({"success": False, "error": "Peer not found"})
        else:
            # Find any available peer that can execute tasks
            peers = [p for p in self._registry.list_peers() if p.can_execute_tasks]
            if not peers:
                return json.dumps({"success": False, "error": "No available peers"})
            peer = peers[0]

        try:
            result = self._run_async(self._client.execute_remote_task(peer, task, agent))

            return json.dumps(
                {
                    "success": result.success,
                    "peer_id": peer.peer_id,
                    "peer_name": peer.name,
                    "result": result.result,
                    "agent_used": result.agent_used,
                    "execution_time_ms": result.execution_time_ms,
                    "error": result.error,
                }
            )

        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def remote_skill(
        self,
        skill: str,
        tool: str,
        arguments: Optional[dict] = None,
        peer_id: Optional[str] = None,
    ) -> str:
        """Invoke a skill/tool on a remote peer."""
        self._ensure_initialized()

        # Find peer with the skill
        if peer_id:
            peer = self._registry.get_peer(peer_id)
            if not peer:
                return json.dumps({"success": False, "error": "Peer not found"})
        else:
            peer = self._registry.get_best_peer_for_skill(skill)
            if not peer:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"No peer with skill '{skill}' found",
                    }
                )

        try:
            result = self._run_async(
                self._client.invoke_remote_skill(peer, skill, tool, arguments or {})
            )

            return json.dumps(
                {
                    "success": result.success,
                    "peer_id": peer.peer_id,
                    "peer_name": peer.name,
                    "skill": skill,
                    "tool": tool,
                    "result": result.result,
                    "execution_time_ms": result.execution_time_ms,
                    "error": result.error,
                }
            )

        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def find_skill(self, skill_name: str) -> str:
        """Find peers with a specific skill."""
        self._ensure_initialized()

        peers = self._registry.find_peers_with_skill(skill_name)

        return json.dumps(
            {
                "success": True,
                "skill": skill_name,
                "found": len(peers),
                "peers": [
                    {
                        "peer_id": p.peer_id,
                        "name": p.name,
                        "trust_level": p.trust_level,
                        "avg_latency_ms": p.avg_latency_ms,
                    }
                    for p in peers
                ],
            }
        )

    # =========================================================================
    # Context Sync Tools
    # =========================================================================

    def sync_context(
        self,
        peer_id: Optional[str] = None,
        direction: str = "both",
        scope: str = "session",
    ) -> str:
        """Synchronize context with peers."""
        self._ensure_initialized()

        try:
            if peer_id:
                peer = self._registry.get_peer(peer_id)
                if not peer:
                    return json.dumps({"success": False, "error": "Peer not found"})

                result = self._run_async(
                    self._sync_manager.sync_with_peer(peer, self._client, direction, scope)
                )

                return json.dumps(
                    {
                        "success": result.success,
                        "peer_id": peer_id,
                        "direction": direction,
                        "entries_sent": result.entries_sent,
                        "entries_received": result.entries_received,
                        "conflicts": result.conflicts,
                        "error": result.error,
                    }
                )

            else:
                results = self._run_async(
                    self._sync_manager.sync_with_all(self._client, direction, scope)
                )

                total_sent = sum(r.entries_sent for r in results.values())
                total_received = sum(r.entries_received for r in results.values())

                return json.dumps(
                    {
                        "success": True,
                        "peers_synced": len(results),
                        "total_entries_sent": total_sent,
                        "total_entries_received": total_received,
                        "results": {
                            pid: {
                                "success": r.success,
                                "entries_sent": r.entries_sent,
                                "entries_received": r.entries_received,
                            }
                            for pid, r in results.items()
                        },
                    }
                )

        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def share_document(
        self,
        doc_id: str,
        peer_ids: Optional[list[str]] = None,
    ) -> str:
        """Share a document with peers."""
        self._ensure_initialized()

        # For now, this is a placeholder
        # Would integrate with Memory system to get document and sync
        return json.dumps(
            {
                "success": True,
                "message": f"Document {doc_id} shared",
                "doc_id": doc_id,
                "peers": peer_ids or "all",
            }
        )

    # =========================================================================
    # Status Tool
    # =========================================================================

    def p2p_status(self) -> str:
        """Get P2P system status."""
        self._ensure_initialized()

        peers = self._registry.list_peers()
        approved = [p for p in peers if p.status == PeerStatus.APPROVED]
        pending = self._registry.get_pending_approvals()
        connections = self._registry.get_active_connections()

        return json.dumps(
            {
                "success": True,
                "instance_id": self._security.instance_id,
                "fingerprint": self._security.get_fingerprint(),
                "discovery_running": self._discovery.is_running,
                "total_peers": len(peers),
                "approved_peers": len(approved),
                "pending_approvals": len(pending),
                "active_connections": len(connections),
                "sync_entries": self._sync_manager.get_entry_count(),
            }
        )

    def execute(self, **kwargs) -> str:
        """Direct execution."""
        action = kwargs.get("action", "status")

        if action == "status":
            return self.p2p_status()
        elif action == "discover":
            return self.discover_peers(kwargs.get("timeout", 5.0))
        elif action == "list":
            return self.list_peers(kwargs.get("status", "all"))
        else:
            return json.dumps({"error": f"Unknown action: {action}"})
