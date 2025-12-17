"""
Distributed AI for R CLI.

Enables multiple machines to collaborate on AI inference,
similar to exo but using MLX for Apple Silicon optimization.

Features:
- Ring-weighted model partitioning based on available memory
- Peer-to-peer inference coordination
- MLX optimization for Apple Silicon Macs
- Support for heterogeneous clusters
"""

from r_cli.distributed.cluster import (
    ClusterNode,
    DistributedCluster,
    NodeCapabilities,
)
from r_cli.distributed.partition import (
    ModelPartition,
    PartitionStrategy,
    RingPartitioner,
)

__all__ = [
    "ClusterNode",
    "DistributedCluster",
    "ModelPartition",
    "NodeCapabilities",
    "PartitionStrategy",
    "RingPartitioner",
]
