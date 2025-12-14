"""
Backends de LLM para R CLI.

Soporta múltiples proveedores:
- OpenAI-compatible (LM Studio, vLLM, etc.)
- Ollama (nativo)
- MLX-LM (Apple Silicon)
"""

from r_cli.backends.auto import auto_detect_backend, get_backend
from r_cli.backends.base import LLMBackend, Message, Tool, ToolCall
from r_cli.backends.mlx import MLXBackend
from r_cli.backends.ollama import OllamaBackend
from r_cli.backends.openai_compat import OpenAICompatBackend

__all__ = [
    "LLMBackend",
    "MLXBackend",
    "Message",
    "OllamaBackend",
    "OpenAICompatBackend",
    "Tool",
    "ToolCall",
    "auto_detect_backend",
    "get_backend",
]
