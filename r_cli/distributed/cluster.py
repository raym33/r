"""
Distributed Cluster Management for R CLI.

Manages a cluster of nodes for distributed AI inference,
with automatic capability detection and topology management.
"""

import asyncio
import json
import logging
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DeviceType(str, Enum):
    """Type of compute device."""

    APPLE_SILICON = "apple_silicon"  # M1, M2, M3, M4
    NVIDIA_GPU = "nvidia_gpu"
    AMD_GPU = "amd_gpu"
    CPU_ONLY = "cpu"
    UNKNOWN = "unknown"


class NodeStatus(str, Enum):
    """Status of a cluster node."""

    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"  # Currently processing inference
    READY = "ready"  # Ready to accept work
    ERROR = "error"


class NodeCapabilities(BaseModel):
    """Hardware capabilities of a node."""

    # Device info
    device_type: DeviceType = DeviceType.UNKNOWN
    chip_name: str = ""  # e.g., "Apple M2 Pro"

    # Memory
    total_memory_gb: float = 0.0
    available_memory_gb: float = 0.0
    unified_memory: bool = False  # Apple Silicon unified memory

    # Compute
    cpu_cores: int = 0
    gpu_cores: int = 0  # Neural Engine cores for Apple Silicon

    # Software
    mlx_available: bool = False
    mlx_version: Optional[str] = None
    torch_available: bool = False

    # Performance estimate (TFLOPS)
    estimated_tflops: float = 0.0

    @classmethod
    def detect_local(cls) -> "NodeCapabilities":
        """Detect capabilities of the local machine."""
        caps = cls()

        # Detect platform
        system = platform.system()
        machine = platform.machine()

        if system == "Darwin" and machine == "arm64":
            caps.device_type = DeviceType.APPLE_SILICON
            caps.unified_memory = True
            caps._detect_apple_silicon()
        else:
            caps.device_type = DeviceType.CPU_ONLY
            caps._detect_generic()

        # Check MLX availability
        caps._check_mlx()

        return caps

    def _detect_apple_silicon(self) -> None:
        """Detect Apple Silicon capabilities."""
        try:
            # Get chip name
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
            )
            self.chip_name = result.stdout.strip()

            # Get memory info
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
            )
            total_bytes = int(result.stdout.strip())
            self.total_memory_gb = total_bytes / (1024**3)

            # Get available memory (approximate)
            import os
            self.available_memory_gb = self.total_memory_gb * 0.7  # Conservative estimate

            # Get CPU cores
            result = subprocess.run(
                ["sysctl", "-n", "hw.ncpu"],
                capture_output=True,
                text=True,
            )
            self.cpu_cores = int(result.stdout.strip())

            # Estimate GPU cores and TFLOPS based on chip
            self._estimate_apple_performance()

        except Exception as e:
            logger.warning(f"Error detecting Apple Silicon: {e}")

    def _estimate_apple_performance(self) -> None:
        """Estimate performance based on Apple Silicon chip."""
        chip = self.chip_name.lower()

        # GPU core estimates and TFLOPS for different chips
        chip_specs = {
            "m1": (8, 2.6),
            "m1 pro": (16, 5.2),
            "m1 max": (32, 10.4),
            "m1 ultra": (64, 21.0),
            "m2": (10, 3.6),
            "m2 pro": (19, 6.8),
            "m2 max": (38, 13.6),
            "m2 ultra": (76, 27.2),
            "m3": (10, 4.1),
            "m3 pro": (18, 7.4),
            "m3 max": (40, 16.4),
            "m4": (10, 4.5),
            "m4 pro": (20, 9.0),
            "m4 max": (40, 18.0),
        }

        for name, (cores, tflops) in chip_specs.items():
            if name in chip:
                self.gpu_cores = cores
                self.estimated_tflops = tflops
                break

    def _detect_generic(self) -> None:
        """Detect capabilities for non-Apple machines."""
        import os

        self.cpu_cores = os.cpu_count() or 1

        # Try to get memory
        try:
            import psutil
            mem = psutil.virtual_memory()
            self.total_memory_gb = mem.total / (1024**3)
            self.available_memory_gb = mem.available / (1024**3)
        except ImportError:
            pass

    def _check_mlx(self) -> None:
        """Check if MLX is available."""
        try:
            import mlx.core as mx
            self.mlx_available = True
            self.mlx_version = mx.__version__ if hasattr(mx, "__version__") else "unknown"
        except ImportError:
            self.mlx_available = False

        try:
            import torch
            self.torch_available = True
        except ImportError:
            self.torch_available = False

    def can_run_distributed(self) -> bool:
        """Check if this node can participate in distributed inference."""
        return self.mlx_available and self.device_type == DeviceType.APPLE_SILICON

    def memory_weight(self) -> float:
        """Get memory weight for partitioning (0-1)."""
        # Use available memory as weight
        return max(0.0, self.available_memory_gb / 100.0)  # Normalize to ~100GB max


class ClusterNode(BaseModel):
    """A node in the distributed cluster."""

    # Identity
    node_id: str
    name: str
    host: str
    port: int = 8765

    # Status
    status: NodeStatus = NodeStatus.OFFLINE
    last_seen: Optional[datetime] = None

    # Capabilities
    capabilities: NodeCapabilities = NodeCapabilities()

    # Current work
    assigned_layers: list[int] = []  # Model layers assigned to this node
    current_model: Optional[str] = None

    # Performance
    inference_count: int = 0
    avg_tokens_per_sec: float = 0.0

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def is_available(self) -> bool:
        return self.status in (NodeStatus.ONLINE, NodeStatus.READY)

    @property
    def memory_gb(self) -> float:
        return self.capabilities.available_memory_gb

    def to_summary(self) -> dict:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "host": self.host,
            "status": self.status.value,
            "chip": self.capabilities.chip_name,
            "memory_gb": round(self.capabilities.available_memory_gb, 1),
            "mlx": self.capabilities.mlx_available,
            "layers": self.assigned_layers,
        }


class DistributedCluster:
    """
    Manages a cluster of nodes for distributed AI inference.

    Similar to exo's approach:
    - Ring topology for model distribution
    - Memory-weighted layer assignment
    - Peer-to-peer coordination
    """

    def __init__(self):
        self.nodes: dict[str, ClusterNode] = {}
        self.local_node: Optional[ClusterNode] = None
        self.current_model: Optional[str] = None
        self.total_layers: int = 0
        self._initialized = False

    def initialize_local(self, node_id: str, name: str, host: str, port: int = 8765) -> ClusterNode:
        """Initialize the local node."""
        capabilities = NodeCapabilities.detect_local()

        self.local_node = ClusterNode(
            node_id=node_id,
            name=name,
            host=host,
            port=port,
            status=NodeStatus.READY,
            capabilities=capabilities,
            last_seen=datetime.now(),
        )

        self.nodes[node_id] = self.local_node
        self._initialized = True

        logger.info(f"Local node initialized: {name} ({capabilities.chip_name})")
        logger.info(f"  Memory: {capabilities.available_memory_gb:.1f} GB")
        logger.info(f"  MLX: {capabilities.mlx_available}")

        return self.local_node

    def add_node(self, node: ClusterNode) -> bool:
        """Add a remote node to the cluster."""
        if node.node_id in self.nodes:
            # Update existing node
            self.nodes[node.node_id] = node
            return False

        self.nodes[node.node_id] = node
        logger.info(f"Added node to cluster: {node.name}")
        return True

    def remove_node(self, node_id: str) -> bool:
        """Remove a node from the cluster."""
        if node_id == self.local_node.node_id if self.local_node else None:
            return False  # Can't remove local node

        if node_id in self.nodes:
            del self.nodes[node_id]
            return True
        return False

    def get_available_nodes(self) -> list[ClusterNode]:
        """Get all nodes that can participate in inference."""
        return [
            node for node in self.nodes.values()
            if node.is_available and node.capabilities.can_run_distributed()
        ]

    def get_total_memory(self) -> float:
        """Get total available memory across all nodes."""
        return sum(node.memory_gb for node in self.get_available_nodes())

    def get_total_tflops(self) -> float:
        """Get total compute power across all nodes."""
        return sum(
            node.capabilities.estimated_tflops
            for node in self.get_available_nodes()
        )

    def get_cluster_info(self) -> dict:
        """Get cluster information summary."""
        available = self.get_available_nodes()
        return {
            "total_nodes": len(self.nodes),
            "available_nodes": len(available),
            "total_memory_gb": round(self.get_total_memory(), 1),
            "total_tflops": round(self.get_total_tflops(), 1),
            "current_model": self.current_model,
            "nodes": [n.to_summary() for n in self.nodes.values()],
        }

    def assign_layers(self, model_name: str, total_layers: int) -> dict[str, list[int]]:
        """
        Assign model layers to nodes based on memory.

        Uses ring-weighted partitioning similar to exo:
        - Each node gets layers proportional to its available memory
        - Layers are assigned in order around the ring
        """
        from r_cli.distributed.partition import RingPartitioner

        nodes = self.get_available_nodes()
        if not nodes:
            raise ValueError("No available nodes in cluster")

        partitioner = RingPartitioner()
        assignments = partitioner.partition(nodes, total_layers)

        # Update nodes with assignments
        for node_id, layers in assignments.items():
            if node_id in self.nodes:
                self.nodes[node_id].assigned_layers = layers
                self.nodes[node_id].current_model = model_name

        self.current_model = model_name
        self.total_layers = total_layers

        logger.info(f"Layer assignments for {model_name} ({total_layers} layers):")
        for node_id, layers in assignments.items():
            node = self.nodes[node_id]
            logger.info(f"  {node.name}: layers {layers[0]}-{layers[-1]} ({len(layers)} layers)")

        return assignments

    def get_node_for_layer(self, layer_idx: int) -> Optional[ClusterNode]:
        """Find which node is responsible for a given layer."""
        for node in self.nodes.values():
            if layer_idx in node.assigned_layers:
                return node
        return None

    def clear_assignments(self) -> None:
        """Clear all layer assignments."""
        for node in self.nodes.values():
            node.assigned_layers = []
            node.current_model = None
        self.current_model = None
        self.total_layers = 0
