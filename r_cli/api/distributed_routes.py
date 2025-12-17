"""
API Routes for Distributed AI Inference.

Provides endpoints for:
- Cluster management
- Model loading and distribution
- Distributed text generation
"""

import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from r_cli.api.distributed_models import (
    AddNodeRequest,
    ClusterInfoResponse,
    DistributedStatusResponse,
    GenerateRequest,
    GenerateResponse,
    LoadModelRequest,
    LoadModelResponse,
    ModelRequirementsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/distributed", tags=["distributed"])

# Global instances (initialized lazily)
_cluster = None
_coordinator = None


def get_cluster():
    """Get or initialize the distributed cluster."""
    global _cluster
    if _cluster is None:
        from r_cli.distributed.cluster import DistributedCluster

        _cluster = DistributedCluster()

        # Initialize local node
        import socket

        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        node_id = str(uuid.uuid4())[:8]

        _cluster.initialize_local(
            node_id=node_id,
            name=hostname,
            host=local_ip,
            port=8765,
        )

    return _cluster


def get_coordinator():
    """Get or initialize the inference coordinator."""
    global _coordinator
    if _coordinator is None:
        from r_cli.distributed.inference import DistributedInferenceCoordinator

        _coordinator = DistributedInferenceCoordinator(get_cluster())

    return _coordinator


# ==================== Cluster Management ====================


@router.get("/status", response_model=DistributedStatusResponse)
async def get_distributed_status():
    """Get status of the distributed inference system."""
    coordinator = get_coordinator()
    status = coordinator.get_status()

    return DistributedStatusResponse(
        mlx_available=status["mlx_available"],
        model_loaded=status["model_loaded"],
        model_info=status["model_info"],
        cluster=ClusterInfoResponse(**status["cluster"]),
        active_requests=status["active_requests"],
    )


@router.get("/cluster", response_model=ClusterInfoResponse)
async def get_cluster_info():
    """Get cluster information."""
    cluster = get_cluster()
    return ClusterInfoResponse(**cluster.get_cluster_info())


@router.get("/nodes")
async def list_nodes():
    """List all nodes in the cluster."""
    cluster = get_cluster()
    return {"nodes": [node.to_summary() for node in cluster.nodes.values()]}


@router.get("/nodes/{node_id}")
async def get_node(node_id: str):
    """Get details for a specific node."""
    cluster = get_cluster()
    if node_id not in cluster.nodes:
        raise HTTPException(status_code=404, detail="Node not found")

    node = cluster.nodes[node_id]
    return node.to_summary()


@router.post("/nodes")
async def add_node(request: AddNodeRequest):
    """Add a remote node to the cluster."""
    from r_cli.distributed.cluster import ClusterNode, NodeCapabilities, NodeStatus

    cluster = get_cluster()

    # Create node (capabilities will be discovered later)
    node_id = str(uuid.uuid4())[:8]
    node = ClusterNode(
        node_id=node_id,
        name=request.name or f"node-{node_id}",
        host=request.host,
        port=request.port,
        status=NodeStatus.OFFLINE,  # Will be updated when we connect
        capabilities=NodeCapabilities(),
    )

    # TODO: Actually connect to the node and get its capabilities
    # For now, we just add it to the cluster

    cluster.add_node(node)

    return {
        "success": True,
        "node_id": node_id,
        "message": f"Node added: {node.name}",
    }


@router.delete("/nodes/{node_id}")
async def remove_node(node_id: str):
    """Remove a node from the cluster."""
    cluster = get_cluster()

    if cluster.remove_node(node_id):
        return {"success": True, "message": "Node removed"}
    else:
        raise HTTPException(status_code=404, detail="Node not found or cannot be removed")


# ==================== Model Management ====================


@router.get("/models/requirements")
async def get_model_requirements(model_name: str = Query(..., description="Model name to check")):
    """Get estimated requirements for a model."""
    from r_cli.distributed.partition import can_cluster_run_model, estimate_model_requirements

    cluster = get_cluster()

    requirements = estimate_model_requirements(model_name)
    available_nodes = cluster.get_available_nodes()

    can_run, reason = can_cluster_run_model(available_nodes, model_name)

    return ModelRequirementsResponse(
        model_name=model_name,
        layers=requirements["layers"],
        memory_fp16_gb=requirements["memory_fp16_gb"],
        memory_4bit_gb=requirements["memory_4bit_gb"],
        memory_per_layer_gb=requirements["memory_per_layer_gb"],
        can_run=can_run,
        reason=reason,
    )


@router.post("/models/load", response_model=LoadModelResponse)
async def load_model(request: LoadModelRequest):
    """Load a model distributed across the cluster."""
    coordinator = get_coordinator()

    result = await coordinator.load_distributed_model(
        model_name=request.model_name,
        quantization=request.quantization,
    )

    if result["success"]:
        return LoadModelResponse(
            success=True,
            model=result["model"],
            total_layers=result["total_layers"],
            assignments=result["assignments"],
            cluster_memory_gb=result["cluster_memory_gb"],
        )
    else:
        return LoadModelResponse(
            success=False,
            error=result.get("error", "Failed to load model"),
        )


@router.post("/models/unload")
async def unload_model():
    """Unload the current model."""
    coordinator = get_coordinator()
    cluster = get_cluster()

    coordinator.local_engine.unload_model()
    cluster.clear_assignments()

    return {"success": True, "message": "Model unloaded"}


@router.get("/models/info")
async def get_model_info():
    """Get information about the currently loaded model."""
    coordinator = get_coordinator()
    return coordinator.local_engine.get_model_info()


# ==================== Inference ====================


@router.post("/generate", response_model=GenerateResponse)
async def generate_text(request: GenerateRequest):
    """Generate text using distributed inference."""
    coordinator = get_coordinator()

    if request.stream:
        # Return streaming response
        async def stream_tokens() -> AsyncGenerator[str, None]:
            async for token in coordinator.stream_generate_distributed(
                prompt=request.prompt,
                model_name=request.model_name,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            ):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            stream_tokens(),
            media_type="text/event-stream",
        )

    # Non-streaming response
    result = await coordinator.generate_distributed(
        prompt=request.prompt,
        model_name=request.model_name,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        stream=False,
    )

    return GenerateResponse(
        request_id=result.request_id,
        text=result.text,
        tokens_generated=result.tokens_generated,
        time_seconds=result.time_seconds,
        tokens_per_second=result.tokens_per_second,
        model_name=result.model_name,
        nodes_used=result.nodes_used,
        success=result.success,
        error=result.error,
    )


@router.post("/generate/stream")
async def generate_text_stream(request: GenerateRequest):
    """Stream text generation (Server-Sent Events)."""
    coordinator = get_coordinator()

    async def stream_tokens() -> AsyncGenerator[str, None]:
        async for token in coordinator.stream_generate_distributed(
            prompt=request.prompt,
            model_name=request.model_name,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        ):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_tokens(),
        media_type="text/event-stream",
    )


# ==================== Layer Management ====================


@router.get("/layers")
async def get_layer_assignments():
    """Get current layer assignments."""
    cluster = get_cluster()

    assignments = {}
    for node in cluster.nodes.values():
        if node.assigned_layers:
            assignments[node.node_id] = {
                "name": node.name,
                "layers": node.assigned_layers,
                "count": len(node.assigned_layers),
            }

    return {
        "model": cluster.current_model,
        "total_layers": cluster.total_layers,
        "assignments": assignments,
    }


@router.post("/layers/reassign")
async def reassign_layers(model_name: str = Query(None), total_layers: int = Query(None)):
    """Reassign layers based on current cluster state."""
    cluster = get_cluster()

    if not model_name:
        model_name = cluster.current_model

    if not model_name:
        raise HTTPException(status_code=400, detail="No model specified")

    if not total_layers:
        from r_cli.distributed.partition import estimate_model_requirements

        requirements = estimate_model_requirements(model_name)
        total_layers = requirements["layers"]

    assignments = cluster.assign_layers(model_name, total_layers)

    return {
        "success": True,
        "model": model_name,
        "total_layers": total_layers,
        "assignments": {
            node_id: {"layers": layers, "count": len(layers)}
            for node_id, layers in assignments.items()
        },
    }


# ==================== P2P Integration ====================


@router.post("/discover")
async def discover_nodes():
    """Discover nodes using P2P system."""
    try:
        from r_cli.p2p import PeerRegistry

        registry = PeerRegistry()
        peers = registry.list_peers(status="approved")

        cluster = get_cluster()
        added = 0

        for peer in peers:
            if peer.peer_id not in cluster.nodes:
                from r_cli.distributed.cluster import ClusterNode, NodeCapabilities, NodeStatus

                node = ClusterNode(
                    node_id=peer.peer_id,
                    name=peer.name,
                    host=peer.host,
                    port=peer.port,
                    status=NodeStatus.OFFLINE,
                    capabilities=NodeCapabilities(),
                )
                cluster.add_node(node)
                added += 1

        return {
            "success": True,
            "peers_found": len(peers),
            "nodes_added": added,
        }

    except ImportError:
        return {
            "success": False,
            "error": "P2P module not available",
        }


@router.post("/sync-from-p2p")
async def sync_nodes_from_p2p():
    """Sync cluster nodes from P2P approved peers."""
    return await discover_nodes()
