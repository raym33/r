"""
P2P API Routes for R CLI.

FastAPI routes for peer-to-peer communication.
"""

import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from r_cli.api.p2p_models import (
    AddPeerRequest,
    AddPeerResponse,
    ApprovalRequestInfo,
    ContextSyncRequest,
    ContextSyncResponse,
    P2PSkillRequest,
    P2PSkillResponse,
    P2PStatusResponse,
    P2PTaskRequest,
    P2PTaskResponse,
    PeerAuthRequest,
    PeerAuthResponse,
    PeerChallengeRequest,
    PeerChallengeResponse,
    PeerInfoResponse,
    PeerListResponse,
    PendingApprovalsResponse,
    SkillInfoResponse,
    SkillsListResponse,
)
from r_cli.p2p.client import P2PClient
from r_cli.p2p.discovery import P2PDiscoveryService
from r_cli.p2p.exceptions import (
    PeerBlockedError,
    PeerNotFoundError,
)
from r_cli.p2p.peer import Peer, PeerStatus
from r_cli.p2p.registry import PeerRegistry
from r_cli.p2p.security import P2PSecurity
from r_cli.p2p.sync import ContextExport, ContextSyncManager

logger = logging.getLogger(__name__)

# Global P2P components (initialized in register_p2p_routes)
_registry: Optional[PeerRegistry] = None
_security: Optional[P2PSecurity] = None
_discovery: Optional[P2PDiscoveryService] = None
_client: Optional[P2PClient] = None
_sync_manager: Optional[ContextSyncManager] = None
_agent = None  # Main R CLI agent for task execution


def get_registry() -> PeerRegistry:
    """Get peer registry."""
    if not _registry:
        raise HTTPException(status_code=503, detail="P2P not initialized")
    return _registry


def get_security() -> P2PSecurity:
    """Get security manager."""
    if not _security:
        raise HTTPException(status_code=503, detail="P2P not initialized")
    return _security


async def verify_peer_token(
    authorization: Optional[str] = Header(None),
    x_peer_id: Optional[str] = Header(None),
) -> str:
    """Verify peer authentication token."""
    if not authorization or not x_peer_id:
        raise HTTPException(status_code=401, detail="Peer authentication required")

    security = get_security()
    registry = get_registry()

    # Extract token
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]

    # Get peer
    peer = registry.get_peer(x_peer_id)
    if not peer:
        raise HTTPException(status_code=401, detail="Unknown peer")

    if not peer.is_trusted:
        raise HTTPException(status_code=403, detail="Peer not approved")

    # Validate token
    peer_key = peer.public_key or ""
    payload = security.validate_peer_token(token, peer_key)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return x_peer_id


def create_p2p_router() -> APIRouter:
    """Create the P2P API router."""
    router = APIRouter(prefix="/v1/p2p", tags=["P2P"])

    # =========================================================================
    # Status
    # =========================================================================

    @router.get("/status", response_model=P2PStatusResponse)
    async def get_p2p_status():
        """Get P2P system status."""
        registry = get_registry()
        security = get_security()

        peers = registry.list_peers()
        approved = [p for p in peers if p.status == PeerStatus.APPROVED]
        pending = registry.get_pending_approvals()
        connections = registry.get_active_connections()

        return P2PStatusResponse(
            enabled=True,
            peer_id=security.instance_id,
            fingerprint=security.get_fingerprint(),
            discovery_running=_discovery.is_running if _discovery else False,
            advertising=_discovery._service_info is not None if _discovery else False,
            total_peers=len(peers),
            approved_peers=len(approved),
            pending_approvals=len(pending),
            active_connections=len(connections),
        )

    @router.get("/info")
    async def get_peer_info():
        """Get this peer's public information (no auth required)."""
        security = get_security()

        # Get skills from agent if available
        skills = []
        if _agent:
            skills = list(_agent.skills.keys())

        return {
            "peer_id": security.instance_id,
            "name": f"R-CLI-{security.instance_id[:8]}",
            "version": "1.0.0",
            "skills": skills,
            "capabilities": ["task_execution", "skill_sharing", "context_sync"],
            "status": "online",
        }

    # =========================================================================
    # Peer Management
    # =========================================================================

    @router.get("/peers", response_model=PeerListResponse)
    async def list_peers(status: Optional[str] = None):
        """List known peers."""
        registry = get_registry()

        peer_status = None
        if status:
            try:
                peer_status = PeerStatus(status)
            except ValueError:
                pass

        peers = registry.list_peers(peer_status)

        return PeerListResponse(
            peers=[
                PeerInfoResponse(
                    peer_id=p.peer_id,
                    name=p.name,
                    status=p.status.value,
                    host=p.host,
                    port=p.port,
                    skills=p.skills,
                    capabilities=[c.value for c in p.capabilities],
                    trust_level=p.trust_level,
                    last_seen=p.last_seen,
                    version=p.version,
                )
                for p in peers
            ],
            total=len(peers),
        )

    @router.post("/peers", response_model=AddPeerResponse)
    async def add_peer(request: AddPeerRequest):
        """Add a manual peer."""
        if not _discovery:
            raise HTTPException(status_code=503, detail="Discovery not initialized")

        try:
            peer = _discovery.add_manual_peer(
                host=request.host,
                port=request.port,
                name=request.name,
            )
            return AddPeerResponse(
                success=True,
                peer_id=peer.peer_id,
                message=f"Added peer {peer.name}",
            )
        except Exception as e:
            return AddPeerResponse(
                success=False,
                peer_id="",
                message=str(e),
            )

    @router.get("/peers/{peer_id}", response_model=PeerInfoResponse)
    async def get_peer(peer_id: str):
        """Get peer details."""
        registry = get_registry()
        peer = registry.get_peer(peer_id)

        if not peer:
            raise HTTPException(status_code=404, detail="Peer not found")

        return PeerInfoResponse(
            peer_id=peer.peer_id,
            name=peer.name,
            status=peer.status.value,
            host=peer.host,
            port=peer.port,
            skills=peer.skills,
            capabilities=[c.value for c in peer.capabilities],
            trust_level=peer.trust_level,
            last_seen=peer.last_seen,
            version=peer.version,
        )

    @router.delete("/peers/{peer_id}")
    async def remove_peer(peer_id: str):
        """Remove a peer."""
        registry = get_registry()

        if registry.remove_peer(peer_id):
            return {"success": True, "message": f"Removed peer {peer_id}"}
        raise HTTPException(status_code=404, detail="Peer not found")

    # =========================================================================
    # Discovery
    # =========================================================================

    @router.post("/discover")
    async def trigger_discovery(timeout: float = 5.0):
        """Trigger network discovery scan."""
        if not _discovery:
            raise HTTPException(status_code=503, detail="Discovery not initialized")

        try:
            peers = await _discovery.scan_network(timeout=timeout)
            return {
                "success": True,
                "discovered": len(peers),
                "peers": [p.to_summary() for p in peers],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Approval
    # =========================================================================

    @router.get("/pending", response_model=PendingApprovalsResponse)
    async def get_pending_approvals():
        """List pending approval requests."""
        registry = get_registry()
        requests = registry.get_pending_approvals()

        return PendingApprovalsResponse(
            requests=[
                ApprovalRequestInfo(
                    request_id=r.request_id,
                    peer_id=r.peer.peer_id,
                    peer_name=r.peer.name,
                    host=r.peer.host,
                    port=r.peer.port,
                    fingerprint=r.fingerprint,
                    discovery_method=r.discovery_method,
                    requested_at=r.requested_at,
                    expires_at=r.expires_at,
                )
                for r in requests
            ],
            total=len(requests),
        )

    @router.post("/approve/{peer_id}")
    async def approve_peer(peer_id: str, approved_by: str = "api"):
        """Approve a pending peer."""
        registry = get_registry()

        try:
            registry.approve_peer(peer_id, approved_by)
            return {"success": True, "message": f"Approved peer {peer_id}"}
        except PeerNotFoundError:
            raise HTTPException(status_code=404, detail="Peer not found")
        except PeerBlockedError:
            raise HTTPException(status_code=403, detail="Peer is blocked")

    @router.post("/reject/{peer_id}")
    async def reject_peer(peer_id: str):
        """Reject a pending peer."""
        registry = get_registry()

        try:
            registry.reject_peer(peer_id)
            return {"success": True, "message": f"Rejected peer {peer_id}"}
        except PeerNotFoundError:
            raise HTTPException(status_code=404, detail="Peer not found")

    @router.post("/block/{peer_id}")
    async def block_peer(peer_id: str):
        """Block a peer permanently."""
        registry = get_registry()

        try:
            registry.block_peer(peer_id)
            return {"success": True, "message": f"Blocked peer {peer_id}"}
        except PeerNotFoundError:
            raise HTTPException(status_code=404, detail="Peer not found")

    # =========================================================================
    # Authentication
    # =========================================================================

    @router.post("/auth/challenge", response_model=PeerChallengeResponse)
    async def auth_challenge(request: PeerChallengeRequest):
        """Generate authentication challenge for a peer."""
        security = get_security()
        registry = get_registry()

        # Check if peer exists
        peer = registry.get_peer(request.peer_id)
        if not peer:
            # Create new peer entry for unknown peer
            peer = Peer(
                peer_id=request.peer_id,
                name=f"Peer-{request.peer_id[:8]}",
                host="unknown",
                port=8765,
                status=PeerStatus.PENDING,
                public_key=request.public_key,
            )
            registry.add_peer(peer)

            # Create approval request
            approval = security.create_approval_request(peer, "network")
            registry.add_approval_request(approval)

        # Generate challenge
        challenge = security.create_challenge(request.peer_id)

        return PeerChallengeResponse(
            challenge=challenge.challenge,
            our_peer_id=security.instance_id,
            our_public_key=security.instance_key[:32],
        )

    @router.post("/auth/respond", response_model=PeerAuthResponse)
    async def auth_respond(request: PeerAuthRequest):
        """Respond to authentication challenge."""
        security = get_security()
        registry = get_registry()

        peer = registry.get_peer(request.peer_id)
        if not peer:
            return PeerAuthResponse(success=False, error="Unknown peer")

        if not peer.is_trusted:
            return PeerAuthResponse(
                success=False,
                error="Peer not approved. Approval required before authentication.",
            )

        # Verify challenge response
        peer_key = peer.public_key or request.peer_id[:32]
        if not security.verify_challenge_response(request.peer_id, request.response, peer_key):
            return PeerAuthResponse(success=False, error="Invalid challenge response")

        # Create token
        token = security.create_peer_token(request.peer_id, peer_key)

        return PeerAuthResponse(
            success=True,
            token=token.token,
            expires_at=token.expires_at,
        )

    # =========================================================================
    # Task Execution (Peer authenticated)
    # =========================================================================

    @router.post("/task", response_model=P2PTaskResponse)
    async def receive_task(
        request: P2PTaskRequest,
        peer_id: str = Depends(verify_peer_token),
    ):
        """Receive and execute a task from a peer."""
        if not _agent:
            return P2PTaskResponse(
                request_id=request.request_id,
                result="",
                success=False,
                error="Agent not available",
            )

        start_time = time.time()

        try:
            # Execute task
            result = await asyncio.to_thread(_agent.run, request.task)
            execution_time = (time.time() - start_time) * 1000

            return P2PTaskResponse(
                request_id=request.request_id,
                result=result,
                agent_used=request.agent,
                execution_time_ms=execution_time,
                success=True,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return P2PTaskResponse(
                request_id=request.request_id,
                result="",
                execution_time_ms=execution_time,
                success=False,
                error=str(e),
            )

    # =========================================================================
    # Skill Invocation (Peer authenticated)
    # =========================================================================

    @router.get("/skills", response_model=SkillsListResponse)
    async def list_skills():
        """List available skills for remote invocation."""
        if not _agent:
            return SkillsListResponse(skills=[], total=0)

        skills = []
        for name, skill in _agent.skills.items():
            tools = skill.get_tools()
            skills.append(
                SkillInfoResponse(
                    name=name,
                    description=skill.description,
                    tools=[t.name for t in tools],
                )
            )

        return SkillsListResponse(skills=skills, total=len(skills))

    @router.post("/skill", response_model=P2PSkillResponse)
    async def invoke_skill(
        request: P2PSkillRequest,
        peer_id: str = Depends(verify_peer_token),
    ):
        """Invoke a skill/tool from a peer."""
        if not _agent:
            return P2PSkillResponse(
                request_id=request.request_id,
                success=False,
                error="Agent not available",
            )

        start_time = time.time()

        try:
            # Find skill
            skill = _agent.skills.get(request.skill)
            if not skill:
                return P2PSkillResponse(
                    request_id=request.request_id,
                    success=False,
                    error=f"Skill not found: {request.skill}",
                )

            # Find tool
            tools = skill.get_tools()
            tool = next((t for t in tools if t.name == request.tool), None)
            if not tool:
                return P2PSkillResponse(
                    request_id=request.request_id,
                    success=False,
                    error=f"Tool not found: {request.tool}",
                )

            # Execute tool
            result = await asyncio.to_thread(tool.handler, **request.arguments)
            execution_time = (time.time() - start_time) * 1000

            return P2PSkillResponse(
                request_id=request.request_id,
                result=result,
                execution_time_ms=execution_time,
                success=True,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return P2PSkillResponse(
                request_id=request.request_id,
                execution_time_ms=execution_time,
                success=False,
                error=str(e),
            )

    # =========================================================================
    # Context Sync (Peer authenticated)
    # =========================================================================

    @router.post("/sync", response_model=ContextSyncResponse)
    async def sync_context(
        request: ContextSyncRequest,
        peer_id: str = Depends(verify_peer_token),
    ):
        """Sync context with a peer."""
        if not _sync_manager:
            return ContextSyncResponse(
                success=False,
                direction=request.direction,
                error="Sync not available",
            )

        try:
            if request.direction == "receive":
                # Peer is sending us data
                if not request.data:
                    return ContextSyncResponse(
                        success=False,
                        direction=request.direction,
                        error="No data provided",
                    )

                export = ContextExport(**request.data)
                entries = _sync_manager.import_context(export)

                return ContextSyncResponse(
                    success=True,
                    direction=request.direction,
                    entries_processed=entries,
                )

            else:  # direction == "send"
                # Peer wants our data
                export = _sync_manager.export_context(
                    peer_id=peer_id,
                    since=request.since,
                )

                return ContextSyncResponse(
                    success=True,
                    direction=request.direction,
                    entries_processed=len(export.session_entries),
                    data=export.model_dump(mode="json"),
                )

        except Exception as e:
            return ContextSyncResponse(
                success=False,
                direction=request.direction,
                error=str(e),
            )

    return router


def register_p2p_routes(app, agent=None, config=None):
    """
    Register P2P routes with the FastAPI app.

    Args:
        app: FastAPI application
        agent: R CLI agent for task/skill execution
        config: P2P configuration
    """
    global _registry, _security, _discovery, _client, _sync_manager, _agent

    # Initialize P2P components
    _registry = PeerRegistry()
    _security = P2PSecurity()
    _discovery = P2PDiscoveryService(_registry, _security)
    _client = P2PClient(_registry, _security)
    _sync_manager = ContextSyncManager(_registry)
    _agent = agent

    # Create and include router
    router = create_p2p_router()
    app.include_router(router)

    logger.info(f"P2P routes registered. Peer ID: {_security.instance_id[:8]}...")
