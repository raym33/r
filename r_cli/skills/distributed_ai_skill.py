"""
Distributed AI Skill for R CLI.

Enables distributed AI inference across multiple Apple Silicon Macs,
similar to exo but using MLX for optimization.

Tools:
- cluster_status: View cluster status and nodes
- add_node: Add a node to the cluster
- remove_node: Remove a node from the cluster
- list_nodes: List all cluster nodes
- check_model: Check if cluster can run a model
- load_model: Load a model distributed across cluster
- unload_model: Unload current model
- generate: Generate text using distributed inference
- assign_layers: Manually assign model layers
- sync_p2p: Sync nodes from P2P peers
"""

import asyncio
import logging
from typing import Any, Optional

from r_cli.core.agent import Skill
from r_cli.core.config import Config
from r_cli.core.llm import Tool

logger = logging.getLogger(__name__)


class DistributedAISkill(Skill):
    """Skill for distributed AI inference on Apple Silicon."""

    name = "distributed_ai"
    description = "Distributed AI inference across multiple Apple Silicon Macs using MLX"

    def __init__(self, config: Optional[Config] = None):
        super().__init__(config)
        self._cluster = None
        self._coordinator = None

    def _run_async(self, coro):
        """Run async code from sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result()
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def _get_cluster(self):
        """Get or initialize the cluster."""
        if self._cluster is None:
            import socket
            import uuid

            from r_cli.distributed.cluster import DistributedCluster

            self._cluster = DistributedCluster()

            hostname = socket.gethostname()
            try:
                local_ip = socket.gethostbyname(hostname)
            except socket.gaierror:
                local_ip = "127.0.0.1"

            node_id = str(uuid.uuid4())[:8]
            self._cluster.initialize_local(
                node_id=node_id,
                name=hostname,
                host=local_ip,
                port=8765,
            )

        return self._cluster

    def _get_coordinator(self):
        """Get or initialize the inference coordinator."""
        if self._coordinator is None:
            from r_cli.distributed.inference import DistributedInferenceCoordinator

            self._coordinator = DistributedInferenceCoordinator(self._get_cluster())

        return self._coordinator

    def get_tools(self) -> list[Tool]:
        """Get all distributed AI tools."""
        return [
            Tool(
                name="cluster_status",
                description="Get the status of the distributed AI cluster including nodes, memory, and loaded model",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.cluster_status,
            ),
            Tool(
                name="add_node",
                description="Add a remote node to the distributed cluster",
                parameters={
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string",
                            "description": "Node hostname or IP address",
                        },
                        "port": {
                            "type": "integer",
                            "description": "Node port (default: 8765)",
                        },
                        "name": {
                            "type": "string",
                            "description": "Friendly name for the node",
                        },
                    },
                    "required": ["host"],
                },
                handler=self.add_node,
            ),
            Tool(
                name="remove_node",
                description="Remove a node from the cluster",
                parameters={
                    "type": "object",
                    "properties": {
                        "node_id": {
                            "type": "string",
                            "description": "ID of the node to remove",
                        },
                    },
                    "required": ["node_id"],
                },
                handler=self.remove_node,
            ),
            Tool(
                name="list_nodes",
                description="List all nodes in the cluster with their capabilities",
                parameters={
                    "type": "object",
                    "properties": {
                        "available_only": {
                            "type": "boolean",
                            "description": "Only show available nodes",
                        },
                    },
                },
                handler=self.list_nodes,
            ),
            Tool(
                name="check_model",
                description="Check if the cluster has enough resources to run a model",
                parameters={
                    "type": "object",
                    "properties": {
                        "model_name": {
                            "type": "string",
                            "description": "HuggingFace model name (e.g., 'mistralai/Mistral-7B-v0.1')",
                        },
                        "quantization": {
                            "type": "string",
                            "enum": ["4bit", "fp16"],
                            "description": "Quantization level (default: 4bit)",
                        },
                    },
                    "required": ["model_name"],
                },
                handler=self.check_model,
            ),
            Tool(
                name="load_model",
                description="Load a model distributed across the cluster nodes",
                parameters={
                    "type": "object",
                    "properties": {
                        "model_name": {
                            "type": "string",
                            "description": "HuggingFace model name or local path",
                        },
                        "quantization": {
                            "type": "string",
                            "enum": ["4bit", "fp16"],
                            "description": "Quantization level (default: 4bit)",
                        },
                    },
                    "required": ["model_name"],
                },
                handler=self.load_model,
            ),
            Tool(
                name="unload_model",
                description="Unload the currently loaded model to free memory",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.unload_model,
            ),
            Tool(
                name="generate",
                description="Generate text using distributed inference across the cluster",
                parameters={
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Input prompt for generation",
                        },
                        "max_tokens": {
                            "type": "integer",
                            "description": "Maximum tokens to generate (default: 512)",
                        },
                        "temperature": {
                            "type": "number",
                            "description": "Sampling temperature 0.0-2.0 (default: 0.7)",
                        },
                        "top_p": {
                            "type": "number",
                            "description": "Top-p sampling 0.0-1.0 (default: 0.9)",
                        },
                    },
                    "required": ["prompt"],
                },
                handler=self.generate,
            ),
            Tool(
                name="assign_layers",
                description="View or manually reassign model layers to nodes",
                parameters={
                    "type": "object",
                    "properties": {
                        "reassign": {
                            "type": "boolean",
                            "description": "Whether to reassign layers based on current node availability",
                        },
                    },
                },
                handler=self.assign_layers,
            ),
            Tool(
                name="sync_p2p",
                description="Sync cluster nodes from approved P2P peers",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.sync_p2p,
            ),
        ]

    def cluster_status(self, **kwargs) -> dict:
        """Get cluster status."""
        coordinator = self._get_coordinator()
        status = coordinator.get_status()

        return {
            "mlx_available": status["mlx_available"],
            "model_loaded": status["model_loaded"],
            "model_info": status["model_info"],
            "cluster": {
                "total_nodes": status["cluster"]["total_nodes"],
                "available_nodes": status["cluster"]["available_nodes"],
                "total_memory_gb": status["cluster"]["total_memory_gb"],
                "total_tflops": status["cluster"]["total_tflops"],
                "current_model": status["cluster"]["current_model"],
            },
            "active_requests": status["active_requests"],
        }

    def add_node(self, host: str, port: int = 8765, name: Optional[str] = None, **kwargs) -> dict:
        """Add a node to the cluster."""
        import uuid

        from r_cli.distributed.cluster import ClusterNode, NodeCapabilities, NodeStatus

        cluster = self._get_cluster()

        node_id = str(uuid.uuid4())[:8]
        node = ClusterNode(
            node_id=node_id,
            name=name or f"node-{node_id}",
            host=host,
            port=port,
            status=NodeStatus.OFFLINE,
            capabilities=NodeCapabilities(),
        )

        is_new = cluster.add_node(node)

        return {
            "success": True,
            "node_id": node_id,
            "name": node.name,
            "host": host,
            "port": port,
            "is_new": is_new,
            "message": f"Node '{node.name}' added to cluster",
        }

    def remove_node(self, node_id: str, **kwargs) -> dict:
        """Remove a node from the cluster."""
        cluster = self._get_cluster()

        if cluster.remove_node(node_id):
            return {"success": True, "message": f"Node {node_id} removed"}
        else:
            return {"success": False, "error": "Node not found or cannot be removed"}

    def list_nodes(self, available_only: bool = False, **kwargs) -> dict:
        """List all nodes."""
        cluster = self._get_cluster()

        if available_only:
            nodes = cluster.get_available_nodes()
        else:
            nodes = list(cluster.nodes.values())

        return {
            "total": len(nodes),
            "nodes": [node.to_summary() for node in nodes],
        }

    def check_model(self, model_name: str, quantization: str = "4bit", **kwargs) -> dict:
        """Check if cluster can run a model."""
        from r_cli.distributed.partition import can_cluster_run_model, estimate_model_requirements

        cluster = self._get_cluster()

        requirements = estimate_model_requirements(model_name)
        available_nodes = cluster.get_available_nodes()

        can_run, reason = can_cluster_run_model(available_nodes, model_name, quantization)

        return {
            "model": model_name,
            "quantization": quantization,
            "requirements": {
                "layers": requirements["layers"],
                "memory_fp16_gb": requirements["memory_fp16_gb"],
                "memory_4bit_gb": requirements["memory_4bit_gb"],
            },
            "cluster": {
                "available_nodes": len(available_nodes),
                "total_memory_gb": cluster.get_total_memory(),
            },
            "can_run": can_run,
            "reason": reason,
        }

    def load_model(self, model_name: str, quantization: str = "4bit", **kwargs) -> dict:
        """Load a distributed model."""
        coordinator = self._get_coordinator()

        async def _load():
            return await coordinator.load_distributed_model(
                model_name=model_name,
                quantization=quantization,
            )

        result = self._run_async(_load())

        if result["success"]:
            return {
                "success": True,
                "model": result["model"],
                "total_layers": result["total_layers"],
                "assignments": result["assignments"],
                "cluster_memory_gb": result["cluster_memory_gb"],
                "message": f"Model '{model_name}' loaded across {len(result['assignments'])} node(s)",
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Failed to load model"),
            }

    def unload_model(self, **kwargs) -> dict:
        """Unload the current model."""
        coordinator = self._get_coordinator()
        cluster = self._get_cluster()

        coordinator.local_engine.unload_model()
        cluster.clear_assignments()

        return {
            "success": True,
            "message": "Model unloaded",
        }

    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        **kwargs,
    ) -> dict:
        """Generate text using distributed inference."""
        coordinator = self._get_coordinator()

        async def _generate():
            return await coordinator.generate_distributed(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False,
            )

        result = self._run_async(_generate())

        if result.success:
            return {
                "success": True,
                "text": result.text,
                "tokens_generated": result.tokens_generated,
                "time_seconds": round(result.time_seconds, 2),
                "tokens_per_second": round(result.tokens_per_second, 1),
                "model": result.model_name,
                "nodes_used": result.nodes_used,
            }
        else:
            return {
                "success": False,
                "error": result.error,
            }

    def assign_layers(self, reassign: bool = False, **kwargs) -> dict:
        """View or reassign layers."""
        cluster = self._get_cluster()

        if reassign and cluster.current_model:
            from r_cli.distributed.partition import estimate_model_requirements

            requirements = estimate_model_requirements(cluster.current_model)
            assignments = cluster.assign_layers(cluster.current_model, requirements["layers"])

            return {
                "success": True,
                "model": cluster.current_model,
                "total_layers": requirements["layers"],
                "reassigned": True,
                "assignments": {
                    node_id: {"layers": layers, "count": len(layers)}
                    for node_id, layers in assignments.items()
                },
            }

        # Just return current assignments
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

    def sync_p2p(self, **kwargs) -> dict:
        """Sync nodes from P2P peers."""
        try:
            from r_cli.p2p import PeerRegistry

            registry = PeerRegistry()
            peers = registry.list_peers(status="approved")

            cluster = self._get_cluster()
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
                "total_nodes": len(cluster.nodes),
            }

        except ImportError as e:
            return {
                "success": False,
                "error": f"P2P module not available: {e}",
            }
