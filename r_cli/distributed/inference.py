"""
Distributed Inference for R CLI.

Coordinates AI inference across multiple nodes using MLX,
implementing a pipeline-parallel approach where each node
processes a subset of model layers.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Check MLX availability
try:
    import mlx.core as mx
    from mlx_lm import load, generate, stream_generate
    from mlx_lm.utils import generate_step

    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False
    logger.debug("MLX not available - distributed inference disabled")


class InferenceStatus(str, Enum):
    """Status of an inference request."""

    PENDING = "pending"
    LOADING = "loading"
    RUNNING = "running"
    STREAMING = "streaming"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class InferenceRequest:
    """A distributed inference request."""

    request_id: str
    prompt: str
    model_name: str
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    stream: bool = False

    # Tracking
    created_at: datetime = field(default_factory=datetime.now)
    status: InferenceStatus = InferenceStatus.PENDING
    assigned_node: Optional[str] = None


@dataclass
class InferenceResult:
    """Result of an inference request."""

    request_id: str
    text: str
    tokens_generated: int
    time_seconds: float
    tokens_per_second: float
    model_name: str
    nodes_used: list[str]
    success: bool = True
    error: Optional[str] = None


class MLXInferenceEngine:
    """
    MLX-based inference engine for Apple Silicon.

    Supports:
    - Local model loading and caching
    - Text generation with streaming
    - Layer-specific inference for distributed mode
    """

    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._model_name: Optional[str] = None
        self._loaded_layers: list[int] = []

    @property
    def is_available(self) -> bool:
        return MLX_AVAILABLE

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    async def load_model(
        self,
        model_name: str,
        layers: Optional[list[int]] = None,
    ) -> bool:
        """
        Load a model (or specific layers for distributed mode).

        Args:
            model_name: HuggingFace model name or path
            layers: Specific layers to load (None = all layers)
        """
        if not MLX_AVAILABLE:
            logger.error("MLX not available")
            return False

        try:
            logger.info(f"Loading model: {model_name}")
            start = time.time()

            # Load model and tokenizer
            # Note: For distributed, we'd need to modify mlx_lm to support partial loading
            # For now, we load the full model on each node
            self._model, self._tokenizer = load(model_name)

            self._model_name = model_name
            self._loaded_layers = layers or []

            elapsed = time.time() - start
            logger.info(f"Model loaded in {elapsed:.1f}s")

            return True

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

    def unload_model(self) -> None:
        """Unload the current model to free memory."""
        self._model = None
        self._tokenizer = None
        self._model_name = None
        self._loaded_layers = []

        # Force garbage collection
        import gc
        gc.collect()

        if MLX_AVAILABLE:
            mx.metal.clear_cache()

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> InferenceResult:
        """
        Generate text from a prompt.

        Returns complete result after generation.
        """
        if not self.is_loaded:
            return InferenceResult(
                request_id="",
                text="",
                tokens_generated=0,
                time_seconds=0,
                tokens_per_second=0,
                model_name="",
                nodes_used=[],
                success=False,
                error="No model loaded",
            )

        try:
            start = time.time()

            # Generate using MLX
            response = generate(
                self._model,
                self._tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
                temp=temperature,
                top_p=top_p,
                verbose=False,
            )

            elapsed = time.time() - start

            # Count tokens (approximate)
            tokens = len(self._tokenizer.encode(response))

            return InferenceResult(
                request_id="local",
                text=response,
                tokens_generated=tokens,
                time_seconds=elapsed,
                tokens_per_second=tokens / elapsed if elapsed > 0 else 0,
                model_name=self._model_name or "",
                nodes_used=["local"],
                success=True,
            )

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return InferenceResult(
                request_id="local",
                text="",
                tokens_generated=0,
                time_seconds=0,
                tokens_per_second=0,
                model_name=self._model_name or "",
                nodes_used=["local"],
                success=False,
                error=str(e),
            )

    async def stream_generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> AsyncGenerator[str, None]:
        """
        Stream text generation token by token.

        Yields tokens as they are generated.
        """
        if not self.is_loaded:
            yield "[Error: No model loaded]"
            return

        try:
            # Use MLX streaming generation
            for response in stream_generate(
                self._model,
                self._tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
                temp=temperature,
                top_p=top_p,
            ):
                # response is a generation response object
                if hasattr(response, "text"):
                    yield response.text
                else:
                    yield str(response)

        except Exception as e:
            logger.error(f"Stream generation failed: {e}")
            yield f"[Error: {e}]"

    def get_model_info(self) -> dict:
        """Get information about the loaded model."""
        if not self.is_loaded:
            return {"loaded": False}

        return {
            "loaded": True,
            "model_name": self._model_name,
            "layers_loaded": self._loaded_layers or "all",
        }


class DistributedInferenceCoordinator:
    """
    Coordinates distributed inference across multiple nodes.

    Implements pipeline parallelism:
    1. Split model layers across nodes
    2. Forward activations through the pipeline
    3. Collect final output

    For simplicity, this initial version uses a "leader" approach
    where one node coordinates and others assist.
    """

    def __init__(self, cluster):
        self.cluster = cluster
        self.local_engine = MLXInferenceEngine()
        self._request_queue: asyncio.Queue = asyncio.Queue()
        self._active_requests: dict[str, InferenceRequest] = {}

    async def load_distributed_model(
        self,
        model_name: str,
        quantization: str = "4bit",
    ) -> dict:
        """
        Load a model distributed across the cluster.

        Each node loads its assigned layers.
        """
        from r_cli.distributed.partition import estimate_model_requirements, can_cluster_run_model

        # Check if cluster can handle the model
        available_nodes = self.cluster.get_available_nodes()
        can_run, reason = can_cluster_run_model(available_nodes, model_name, quantization)

        if not can_run:
            return {
                "success": False,
                "error": reason,
            }

        # Get model requirements
        requirements = estimate_model_requirements(model_name)
        total_layers = requirements["layers"]

        # Assign layers to nodes
        assignments = self.cluster.assign_layers(model_name, total_layers)

        # Load model on local node
        local_node = self.cluster.local_node
        if local_node and local_node.node_id in assignments:
            local_layers = assignments[local_node.node_id]
            await self.local_engine.load_model(model_name, local_layers)

        # TODO: Signal remote nodes to load their layers
        # For now, we use a simpler approach where the coordinator
        # handles generation and routes to peers as needed

        return {
            "success": True,
            "model": model_name,
            "total_layers": total_layers,
            "assignments": {
                node_id: {
                    "layers": layers,
                    "count": len(layers),
                }
                for node_id, layers in assignments.items()
            },
            "cluster_memory_gb": self.cluster.get_total_memory(),
        }

    async def generate_distributed(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> InferenceResult:
        """
        Generate text using distributed inference.

        If the model fits on a single node, uses local generation.
        Otherwise, coordinates across multiple nodes.
        """
        import uuid

        request = InferenceRequest(
            request_id=str(uuid.uuid4()),
            prompt=prompt,
            model_name=model_name or self.cluster.current_model or "",
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
        )

        self._active_requests[request.request_id] = request

        try:
            # Check if model is loaded
            if not self.local_engine.is_loaded:
                if model_name:
                    load_result = await self.load_distributed_model(model_name)
                    if not load_result["success"]:
                        return InferenceResult(
                            request_id=request.request_id,
                            text="",
                            tokens_generated=0,
                            time_seconds=0,
                            tokens_per_second=0,
                            model_name=request.model_name,
                            nodes_used=[],
                            success=False,
                            error=load_result.get("error", "Failed to load model"),
                        )
                else:
                    return InferenceResult(
                        request_id=request.request_id,
                        text="",
                        tokens_generated=0,
                        time_seconds=0,
                        tokens_per_second=0,
                        model_name="",
                        nodes_used=[],
                        success=False,
                        error="No model loaded. Specify model_name or load a model first.",
                    )

            # For now, use local generation
            # Full distributed pipeline would forward activations between nodes
            request.status = InferenceStatus.RUNNING
            result = await self.local_engine.generate(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            # Update result with request info
            result.request_id = request.request_id

            return result

        finally:
            if request.request_id in self._active_requests:
                del self._active_requests[request.request_id]

    async def stream_generate_distributed(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Stream distributed generation."""
        if not self.local_engine.is_loaded and model_name:
            await self.load_distributed_model(model_name)

        async for token in self.local_engine.stream_generate(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            yield token

    def get_status(self) -> dict:
        """Get coordinator status."""
        return {
            "mlx_available": MLX_AVAILABLE,
            "model_loaded": self.local_engine.is_loaded,
            "model_info": self.local_engine.get_model_info(),
            "cluster": self.cluster.get_cluster_info(),
            "active_requests": len(self._active_requests),
        }
