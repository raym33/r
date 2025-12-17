"""
Model Partitioning for Distributed Inference.

Implements ring-weighted partitioning similar to exo,
distributing model layers across nodes based on available memory.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from r_cli.distributed.cluster import ClusterNode

logger = logging.getLogger(__name__)


class PartitionStrategy(str, Enum):
    """Strategy for partitioning model layers."""

    RING_MEMORY = "ring_memory"  # Memory-weighted ring (like exo)
    EQUAL = "equal"  # Equal layers per node
    PERFORMANCE = "performance"  # Based on TFLOPS
    SINGLE = "single"  # All on one node


@dataclass
class ModelPartition:
    """A partition of model layers assigned to a node."""

    node_id: str
    start_layer: int
    end_layer: int  # Exclusive
    memory_required_gb: float

    @property
    def num_layers(self) -> int:
        return self.end_layer - self.start_layer

    @property
    def layer_indices(self) -> list[int]:
        return list(range(self.start_layer, self.end_layer))


class Partitioner(ABC):
    """Base class for model partitioners."""

    @abstractmethod
    def partition(
        self,
        nodes: list["ClusterNode"],
        total_layers: int,
        memory_per_layer_gb: float = 0.5,
    ) -> dict[str, list[int]]:
        """
        Partition model layers across nodes.

        Args:
            nodes: Available cluster nodes
            total_layers: Total number of model layers
            memory_per_layer_gb: Estimated memory per layer

        Returns:
            Dict mapping node_id to list of layer indices
        """


class RingPartitioner(Partitioner):
    """
    Ring-weighted partitioner similar to exo.

    Distributes layers proportionally based on available memory,
    creating a ring topology where each node processes consecutive layers.
    """

    def partition(
        self,
        nodes: list["ClusterNode"],
        total_layers: int,
        memory_per_layer_gb: float = 0.5,
    ) -> dict[str, list[int]]:
        """
        Partition using memory-weighted ring strategy.

        Each node gets a proportion of layers based on its
        available memory relative to total cluster memory.
        """
        if not nodes:
            raise ValueError("No nodes available for partitioning")

        if len(nodes) == 1:
            # Single node gets all layers
            return {nodes[0].node_id: list(range(total_layers))}

        # Calculate memory weights
        total_memory = sum(n.memory_gb for n in nodes)
        if total_memory == 0:
            # Equal distribution if no memory info
            return self._equal_partition(nodes, total_layers)

        # Sort nodes by memory (largest first for better distribution)
        sorted_nodes = sorted(nodes, key=lambda n: n.memory_gb, reverse=True)

        assignments: dict[str, list[int]] = {}
        current_layer = 0

        for i, node in enumerate(sorted_nodes):
            # Calculate proportion of layers for this node
            weight = node.memory_gb / total_memory

            if i == len(sorted_nodes) - 1:
                # Last node gets remaining layers
                num_layers = total_layers - current_layer
            else:
                num_layers = max(1, int(total_layers * weight))

            # Ensure we don't exceed total
            num_layers = min(num_layers, total_layers - current_layer)

            if num_layers > 0:
                layer_indices = list(range(current_layer, current_layer + num_layers))
                assignments[node.node_id] = layer_indices
                current_layer += num_layers

            if current_layer >= total_layers:
                break

        # Ensure all layers are assigned
        if current_layer < total_layers:
            # Give remaining to the node with most memory
            remaining = list(range(current_layer, total_layers))
            largest_node = sorted_nodes[0].node_id
            if largest_node in assignments:
                assignments[largest_node].extend(remaining)
            else:
                assignments[largest_node] = remaining

        return assignments

    def _equal_partition(
        self,
        nodes: list["ClusterNode"],
        total_layers: int,
    ) -> dict[str, list[int]]:
        """Fallback to equal distribution."""
        assignments: dict[str, list[int]] = {}
        layers_per_node = total_layers // len(nodes)
        remainder = total_layers % len(nodes)

        current_layer = 0
        for i, node in enumerate(nodes):
            # Add one extra layer to first 'remainder' nodes
            num_layers = layers_per_node + (1 if i < remainder else 0)
            layer_indices = list(range(current_layer, current_layer + num_layers))
            assignments[node.node_id] = layer_indices
            current_layer += num_layers

        return assignments


class PerformancePartitioner(Partitioner):
    """
    Partitioner based on compute performance (TFLOPS).

    Useful when memory is similar but compute differs.
    """

    def partition(
        self,
        nodes: list["ClusterNode"],
        total_layers: int,
        memory_per_layer_gb: float = 0.5,
    ) -> dict[str, list[int]]:
        if not nodes:
            raise ValueError("No nodes available")

        total_tflops = sum(n.capabilities.estimated_tflops for n in nodes)
        if total_tflops == 0:
            # Fallback to equal
            return RingPartitioner()._equal_partition(nodes, total_layers)

        sorted_nodes = sorted(
            nodes,
            key=lambda n: n.capabilities.estimated_tflops,
            reverse=True,
        )

        assignments: dict[str, list[int]] = {}
        current_layer = 0

        for i, node in enumerate(sorted_nodes):
            weight = node.capabilities.estimated_tflops / total_tflops

            if i == len(sorted_nodes) - 1:
                num_layers = total_layers - current_layer
            else:
                num_layers = max(1, int(total_layers * weight))

            num_layers = min(num_layers, total_layers - current_layer)

            if num_layers > 0:
                assignments[node.node_id] = list(range(current_layer, current_layer + num_layers))
                current_layer += num_layers

        return assignments


def estimate_model_requirements(model_name: str) -> dict:
    """
    Estimate memory and layer requirements for a model.

    Common model estimates (approximate):
    - 7B model: ~32 layers, ~14GB at fp16, ~4GB at 4-bit
    - 13B model: ~40 layers, ~26GB at fp16, ~7GB at 4-bit
    - 70B model: ~80 layers, ~140GB at fp16, ~35GB at 4-bit
    """
    model_lower = model_name.lower()

    # Default estimates
    estimates = {
        "layers": 32,
        "memory_fp16_gb": 14,
        "memory_4bit_gb": 4,
        "memory_per_layer_gb": 0.45,
    }

    # Adjust based on model size indicators
    if "70b" in model_lower or "72b" in model_lower:
        estimates = {
            "layers": 80,
            "memory_fp16_gb": 140,
            "memory_4bit_gb": 35,
            "memory_per_layer_gb": 0.44,
        }
    elif "34b" in model_lower or "33b" in model_lower:
        estimates = {
            "layers": 60,
            "memory_fp16_gb": 68,
            "memory_4bit_gb": 17,
            "memory_per_layer_gb": 0.28,
        }
    elif "13b" in model_lower or "14b" in model_lower:
        estimates = {
            "layers": 40,
            "memory_fp16_gb": 26,
            "memory_4bit_gb": 7,
            "memory_per_layer_gb": 0.18,
        }
    elif "8b" in model_lower:
        estimates = {
            "layers": 32,
            "memory_fp16_gb": 16,
            "memory_4bit_gb": 4,
            "memory_per_layer_gb": 0.13,
        }
    elif "7b" in model_lower:
        estimates = {
            "layers": 32,
            "memory_fp16_gb": 14,
            "memory_4bit_gb": 4,
            "memory_per_layer_gb": 0.13,
        }
    elif "3b" in model_lower:
        estimates = {
            "layers": 26,
            "memory_fp16_gb": 6,
            "memory_4bit_gb": 2,
            "memory_per_layer_gb": 0.08,
        }
    elif "1b" in model_lower or "1.5b" in model_lower:
        estimates = {
            "layers": 22,
            "memory_fp16_gb": 3,
            "memory_4bit_gb": 1,
            "memory_per_layer_gb": 0.05,
        }

    return estimates


def can_cluster_run_model(
    nodes: list["ClusterNode"],
    model_name: str,
    quantization: str = "4bit",
) -> tuple[bool, str]:
    """
    Check if the cluster can run a model.

    Returns (can_run, reason).
    """
    if not nodes:
        return False, "No available nodes"

    estimates = estimate_model_requirements(model_name)

    # Get required memory based on quantization
    if quantization == "4bit":
        required_gb = estimates["memory_4bit_gb"]
    else:
        required_gb = estimates["memory_fp16_gb"]

    # Calculate total cluster memory
    total_memory = sum(n.memory_gb for n in nodes)

    # Need some overhead (1.2x)
    required_with_overhead = required_gb * 1.2

    if total_memory >= required_with_overhead:
        return True, f"Cluster has {total_memory:.1f}GB, model needs ~{required_gb}GB"
    else:
        return (
            False,
            f"Insufficient memory: {total_memory:.1f}GB < {required_with_overhead:.1f}GB needed",
        )
