"""
Pydantic models for Distributed AI API endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    """Type of compute device."""

    APPLE_SILICON = "apple_silicon"
    NVIDIA_GPU = "nvidia_gpu"
    AMD_GPU = "amd_gpu"
    CPU_ONLY = "cpu"
    UNKNOWN = "unknown"


class NodeStatusEnum(str, Enum):
    """Status of a cluster node."""

    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    READY = "ready"
    ERROR = "error"


# Request Models


class AddNodeRequest(BaseModel):
    """Request to add a node to the cluster."""

    host: str = Field(..., description="Node hostname or IP")
    port: int = Field(8765, description="Node port")
    name: Optional[str] = Field(None, description="Friendly name for the node")


class LoadModelRequest(BaseModel):
    """Request to load a distributed model."""

    model_name: str = Field(..., description="HuggingFace model name or path")
    quantization: str = Field("4bit", description="Quantization level: 4bit or fp16")


class GenerateRequest(BaseModel):
    """Request for distributed text generation."""

    prompt: str = Field(..., description="Input prompt")
    model_name: Optional[str] = Field(None, description="Model to use (if not already loaded)")
    max_tokens: int = Field(512, ge=1, le=4096, description="Maximum tokens to generate")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: float = Field(0.9, ge=0.0, le=1.0, description="Top-p sampling")
    stream: bool = Field(False, description="Stream response")


class LayerAssignmentRequest(BaseModel):
    """Request to assign model layers manually."""

    model_name: str
    total_layers: int
    assignments: dict[str, list[int]] = Field(
        default_factory=dict,
        description="Manual layer assignments {node_id: [layer_indices]}",
    )


# Response Models


class NodeCapabilitiesResponse(BaseModel):
    """Hardware capabilities of a node."""

    device_type: DeviceType
    chip_name: str
    total_memory_gb: float
    available_memory_gb: float
    unified_memory: bool
    cpu_cores: int
    gpu_cores: int
    mlx_available: bool
    mlx_version: Optional[str]
    estimated_tflops: float


class ClusterNodeResponse(BaseModel):
    """A node in the cluster."""

    node_id: str
    name: str
    host: str
    port: int
    status: NodeStatusEnum
    last_seen: Optional[datetime]
    capabilities: NodeCapabilitiesResponse
    assigned_layers: list[int]
    current_model: Optional[str]
    inference_count: int
    avg_tokens_per_sec: float


class ClusterInfoResponse(BaseModel):
    """Cluster information summary."""

    total_nodes: int
    available_nodes: int
    total_memory_gb: float
    total_tflops: float
    current_model: Optional[str]
    nodes: list[dict[str, Any]]


class LoadModelResponse(BaseModel):
    """Response after loading a distributed model."""

    success: bool
    model: Optional[str] = None
    total_layers: Optional[int] = None
    assignments: Optional[dict[str, dict[str, Any]]] = None
    cluster_memory_gb: Optional[float] = None
    error: Optional[str] = None


class GenerateResponse(BaseModel):
    """Response from distributed generation."""

    request_id: str
    text: str
    tokens_generated: int
    time_seconds: float
    tokens_per_second: float
    model_name: str
    nodes_used: list[str]
    success: bool
    error: Optional[str] = None


class ModelRequirementsResponse(BaseModel):
    """Estimated model requirements."""

    model_name: str
    layers: int
    memory_fp16_gb: float
    memory_4bit_gb: float
    memory_per_layer_gb: float
    can_run: bool
    reason: str


class DistributedStatusResponse(BaseModel):
    """Status of the distributed inference system."""

    mlx_available: bool
    model_loaded: bool
    model_info: dict[str, Any]
    cluster: ClusterInfoResponse
    active_requests: int
