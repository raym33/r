"""
Context Synchronization for R CLI P2P.

Manages context and memory synchronization between peers.
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from r_cli.p2p.peer import Peer
from r_cli.p2p.registry import PeerRegistry

logger = logging.getLogger(__name__)


class MemoryEntry(BaseModel):
    """A single memory entry for sync."""

    id: str
    content: str
    entry_type: str  # "message", "document", "task"
    timestamp: datetime
    metadata: dict = {}


class ContextExport(BaseModel):
    """Exportable context data for sync."""

    peer_id: str
    timestamp: datetime
    session_entries: list[MemoryEntry] = []
    documents: list[dict] = []  # Document references
    task_history: list[dict] = []
    checksum: str = ""

    def compute_checksum(self) -> str:
        """Compute checksum of the content."""
        data = json.dumps(
            {
                "session_entries": [e.model_dump() for e in self.session_entries],
                "documents": self.documents,
                "task_history": self.task_history,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(data.encode()).hexdigest()[:16]


class SyncState(BaseModel):
    """Sync state with a peer."""

    peer_id: str
    last_sync: Optional[datetime] = None
    last_push: Optional[datetime] = None
    last_pull: Optional[datetime] = None
    entries_synced: int = 0
    conflicts_resolved: int = 0


class SyncResult(BaseModel):
    """Result of a sync operation."""

    success: bool
    direction: str  # "push", "pull", "both"
    entries_sent: int = 0
    entries_received: int = 0
    conflicts: int = 0
    error: Optional[str] = None


class ContextSyncManager:
    """
    Manages context and memory synchronization between peers.

    Sync Types:
    1. Session context (recent conversation)
    2. Long-term memory (documents)
    3. Task history

    Strategies:
    - Push: Send our context to peer
    - Pull: Get context from peer
    - Both: Bidirectional sync with conflict resolution
    """

    def __init__(self, registry: PeerRegistry):
        self.registry = registry
        self._sync_state: dict[str, SyncState] = {}
        self._local_entries: list[MemoryEntry] = []

    # =========================================================================
    # Context Export/Import
    # =========================================================================

    def export_context(
        self,
        peer_id: str,
        include_documents: bool = True,
        include_tasks: bool = True,
        since: Optional[datetime] = None,
    ) -> ContextExport:
        """
        Export current context for sharing with a peer.

        Args:
            peer_id: The peer we're exporting for
            include_documents: Include document references
            include_tasks: Include task history
            since: Only include entries after this timestamp

        Returns:
            ContextExport ready to send to peer
        """
        entries = self._local_entries

        # Filter by timestamp if specified
        if since:
            entries = [e for e in entries if e.timestamp > since]

        export = ContextExport(
            peer_id=peer_id,
            timestamp=datetime.now(),
            session_entries=entries,
            documents=[] if not include_documents else self._get_document_refs(),
            task_history=[] if not include_tasks else self._get_task_history(),
        )

        export.checksum = export.compute_checksum()
        return export

    def import_context(
        self,
        data: ContextExport,
        merge_strategy: str = "append",
    ) -> int:
        """
        Import context from a peer.

        Args:
            data: The context data to import
            merge_strategy: How to handle existing entries
                - "append": Add new entries, keep existing
                - "replace": Replace existing with newer
                - "merge": Merge by timestamp

        Returns:
            Number of entries imported
        """
        # Verify checksum
        expected_checksum = data.compute_checksum()
        if data.checksum and data.checksum != expected_checksum:
            logger.warning(f"Checksum mismatch in context import from {data.peer_id}")

        imported = 0

        if merge_strategy == "append":
            # Simply add entries we don't have
            existing_ids = {e.id for e in self._local_entries}
            for entry in data.session_entries:
                if entry.id not in existing_ids:
                    self._local_entries.append(entry)
                    imported += 1

        elif merge_strategy == "replace":
            # Replace entries with same ID if newer
            entry_map = {e.id: e for e in self._local_entries}
            for entry in data.session_entries:
                existing = entry_map.get(entry.id)
                if not existing or entry.timestamp > existing.timestamp:
                    entry_map[entry.id] = entry
                    imported += 1
            self._local_entries = list(entry_map.values())

        elif merge_strategy == "merge":
            # Merge by timestamp, newest wins
            all_entries = self._local_entries + data.session_entries
            entry_map = {}
            for entry in sorted(all_entries, key=lambda e: e.timestamp):
                entry_map[entry.id] = entry
            imported = len(entry_map) - len(self._local_entries)
            self._local_entries = list(entry_map.values())

        # Sort by timestamp
        self._local_entries.sort(key=lambda e: e.timestamp)

        logger.info(f"Imported {imported} entries from peer {data.peer_id}")
        return imported

    def _get_document_refs(self) -> list[dict]:
        """Get document references for sync."""
        # This would integrate with the Memory system
        # For now, return empty
        return []

    def _get_task_history(self) -> list[dict]:
        """Get task history for sync."""
        # This would integrate with task tracking
        # For now, return empty
        return []

    # =========================================================================
    # Sync Operations
    # =========================================================================

    async def sync_with_peer(
        self,
        peer: Peer,
        client,  # P2PClient
        direction: str = "both",
        scope: str = "session",
    ) -> SyncResult:
        """
        Sync context with a specific peer.

        Args:
            peer: The peer to sync with
            client: P2P client for communication
            direction: "push", "pull", or "both"
            scope: "session", "memory", or "all"

        Returns:
            SyncResult with sync statistics
        """
        if not peer.can_sync_context:
            return SyncResult(
                success=False,
                direction=direction,
                error="Peer cannot sync context (insufficient trust or capability)",
            )

        # Get or create sync state
        state = self._get_sync_state(peer.peer_id)

        entries_sent = 0
        entries_received = 0
        conflicts = 0

        try:
            if direction in ("push", "both"):
                # Push our context
                export = self.export_context(
                    peer.peer_id,
                    include_documents=(scope in ("memory", "all")),
                    include_tasks=(scope == "all"),
                    since=state.last_push,
                )

                response = await client.request(
                    peer,
                    "POST",
                    "/v1/p2p/sync",
                    data={
                        "direction": "receive",
                        "data": export.model_dump(mode="json"),
                    },
                )

                if response.success:
                    entries_sent = len(export.session_entries)
                    state.last_push = datetime.now()

            if direction in ("pull", "both"):
                # Pull peer's context
                response = await client.request(
                    peer,
                    "POST",
                    "/v1/p2p/sync",
                    data={
                        "direction": "send",
                        "since": state.last_pull.isoformat() if state.last_pull else None,
                        "scope": scope,
                    },
                )

                if response.success and response.data:
                    peer_export = ContextExport(**response.data.get("data", {}))
                    entries_received = self.import_context(peer_export, merge_strategy="merge")
                    state.last_pull = datetime.now()

            # Update state
            state.last_sync = datetime.now()
            state.entries_synced += entries_sent + entries_received

            return SyncResult(
                success=True,
                direction=direction,
                entries_sent=entries_sent,
                entries_received=entries_received,
                conflicts=conflicts,
            )

        except Exception as e:
            logger.error(f"Sync with {peer.name} failed: {e}")
            return SyncResult(
                success=False,
                direction=direction,
                error=str(e),
            )

    async def sync_with_all(
        self,
        client,  # P2PClient
        direction: str = "push",
        scope: str = "session",
    ) -> dict[str, SyncResult]:
        """
        Sync with all connected peers.

        Returns dict of peer_id -> SyncResult.
        """
        import asyncio

        peers = self.registry.list_peers()
        sync_peers = [p for p in peers if p.can_sync_context]

        if not sync_peers:
            return {}

        tasks = [self.sync_with_peer(peer, client, direction, scope) for peer in sync_peers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        result_dict = {}
        for peer, result in zip(sync_peers, results):
            if isinstance(result, Exception):
                result_dict[peer.peer_id] = SyncResult(
                    success=False,
                    direction=direction,
                    error=str(result),
                )
            else:
                result_dict[peer.peer_id] = result

        return result_dict

    # =========================================================================
    # Conflict Resolution
    # =========================================================================

    def resolve_conflict(
        self,
        local: MemoryEntry,
        remote: MemoryEntry,
        strategy: str = "newer_wins",
    ) -> MemoryEntry:
        """
        Resolve a sync conflict between local and remote entries.

        Strategies:
        - "newer_wins": Keep the newer entry
        - "local_wins": Always keep local
        - "remote_wins": Always keep remote
        - "merge": Attempt to merge content
        """
        if strategy == "newer_wins":
            return local if local.timestamp > remote.timestamp else remote
        elif strategy == "local_wins":
            return local
        elif strategy == "remote_wins":
            return remote
        elif strategy == "merge":
            # Simple merge: concatenate content with separator
            merged_content = f"{local.content}\n---\n{remote.content}"
            return MemoryEntry(
                id=local.id,
                content=merged_content,
                entry_type=local.entry_type,
                timestamp=max(local.timestamp, remote.timestamp),
                metadata={**local.metadata, **remote.metadata},
            )
        else:
            return local

    # =========================================================================
    # State Management
    # =========================================================================

    def _get_sync_state(self, peer_id: str) -> SyncState:
        """Get or create sync state for a peer."""
        if peer_id not in self._sync_state:
            self._sync_state[peer_id] = SyncState(peer_id=peer_id)
        return self._sync_state[peer_id]

    def get_sync_status(self, peer_id: str) -> Optional[SyncState]:
        """Get sync status for a peer."""
        return self._sync_state.get(peer_id)

    def get_all_sync_status(self) -> dict[str, SyncState]:
        """Get sync status for all peers."""
        return self._sync_state.copy()

    # =========================================================================
    # Local Entry Management
    # =========================================================================

    def add_entry(self, entry: MemoryEntry) -> None:
        """Add a local memory entry."""
        self._local_entries.append(entry)

    def get_entries(self, since: Optional[datetime] = None) -> list[MemoryEntry]:
        """Get local entries, optionally filtered by timestamp."""
        if since:
            return [e for e in self._local_entries if e.timestamp > since]
        return self._local_entries.copy()

    def clear_entries(self) -> None:
        """Clear all local entries."""
        self._local_entries.clear()

    def get_entry_count(self) -> int:
        """Get count of local entries."""
        return len(self._local_entries)
