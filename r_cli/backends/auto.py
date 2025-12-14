"""
Auto-detección de backends LLM disponibles.
"""

import platform
from typing import Optional

from r_cli.backends.base import LLMBackend
from r_cli.backends.mlx import MLXBackend
from r_cli.backends.ollama import OllamaBackend
from r_cli.backends.openai_compat import OpenAICompatBackend


def auto_detect_backend(preferred: Optional[str] = None) -> tuple[str, dict]:
    """
    Detecta automáticamente el mejor backend disponible.

    Orden de prioridad:
    1. Backend preferido (si se especifica y está disponible)
    2. MLX (en Apple Silicon)
    3. Ollama
    4. LM Studio / OpenAI-compatible

    Returns:
        tuple: (nombre_backend, config_dict)
    """
    results = {
        "mlx": {"available": False, "reason": ""},
        "ollama": {"available": False, "reason": ""},
        "lm-studio": {"available": False, "reason": ""},
    }

    # Verificar MLX (solo Apple Silicon)
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        if MLXBackend.is_mlx_installed():
            results["mlx"]["available"] = True
        else:
            results["mlx"]["reason"] = "mlx-lm no instalado (pip install mlx-lm)"
    else:
        results["mlx"]["reason"] = "Solo disponible en Apple Silicon"

    # Verificar Ollama
    ollama = OllamaBackend()
    if ollama.is_available():
        results["ollama"]["available"] = True
        results["ollama"]["models"] = ollama.list_models()
    elif OllamaBackend.is_installed():
        results["ollama"]["reason"] = "Ollama instalado pero servidor no corriendo (ollama serve)"
    else:
        results["ollama"]["reason"] = "Ollama no instalado"

    # Verificar LM Studio
    lm_studio = OpenAICompatBackend(base_url="http://localhost:1234/v1")
    if lm_studio.is_available():
        results["lm-studio"]["available"] = True
        results["lm-studio"]["models"] = lm_studio.list_models()
    else:
        results["lm-studio"]["reason"] = "LM Studio no corriendo en localhost:1234"

    # Si hay preferencia, intentar usarla
    if preferred:
        if preferred == "mlx" and results["mlx"]["available"]:
            return "mlx", {"model": "qwen2.5-7b"}
        elif preferred == "ollama" and results["ollama"]["available"]:
            models = results["ollama"].get("models", [])
            model = models[0] if models else "qwen2.5:7b"
            return "ollama", {"model": model}
        elif preferred in ("lm-studio", "openai") and results["lm-studio"]["available"]:
            return "lm-studio", {"base_url": "http://localhost:1234/v1"}

    # Auto-selección por prioridad
    # En Mac, preferir MLX por rendimiento
    if results["mlx"]["available"]:
        return "mlx", {"model": "qwen2.5-7b"}

    if results["ollama"]["available"]:
        models = results["ollama"].get("models", [])
        model = models[0] if models else "qwen2.5:7b"
        return "ollama", {"model": model}

    if results["lm-studio"]["available"]:
        return "lm-studio", {"base_url": "http://localhost:1234/v1"}

    # Ninguno disponible
    return "none", {"error": "No hay backends disponibles", "details": results}


def get_backend(
    backend_type: str,
    model: Optional[str] = None,
    **kwargs,
) -> LLMBackend:
    """
    Obtiene una instancia del backend especificado.

    Args:
        backend_type: "mlx", "ollama", "lm-studio", "openai", o "auto"
        model: Modelo a usar (opcional, usa default si no se especifica)
        **kwargs: Argumentos adicionales para el backend

    Returns:
        LLMBackend: Instancia del backend
    """
    if backend_type == "auto":
        detected, config = auto_detect_backend()
        backend_type = detected
        kwargs.update(config)
        if model:
            kwargs["model"] = model

    if backend_type == "mlx":
        return MLXBackend(model=model or "qwen2.5-7b", **kwargs)

    elif backend_type == "ollama":
        return OllamaBackend(model=model or "qwen2.5:7b", **kwargs)

    elif backend_type in ("lm-studio", "openai", "openai-compatible"):
        return OpenAICompatBackend(
            model=model or "local-model",
            base_url=kwargs.get("base_url", "http://localhost:1234/v1"),
            **kwargs,
        )

    else:
        raise ValueError(f"Backend no soportado: {backend_type}")


def print_status():
    """Imprime el estado de todos los backends."""
    from rich.console import Console
    from rich.table import Table

    console = Console()

    table = Table(title="Estado de Backends LLM")
    table.add_column("Backend", style="cyan")
    table.add_column("Estado", style="green")
    table.add_column("Modelos / Info")

    # MLX
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        if MLXBackend.is_mlx_installed():
            table.add_row("MLX", "✅ Disponible", "Apple Silicon optimizado")
        else:
            table.add_row("MLX", "⚠️ No instalado", "pip install mlx-lm")
    else:
        table.add_row("MLX", "❌ No compatible", "Requiere Apple Silicon")

    # Ollama
    ollama = OllamaBackend()
    if ollama.is_available():
        models = ollama.list_models()[:3]
        models_str = ", ".join(models) if models else "Sin modelos"
        table.add_row("Ollama", "✅ Disponible", models_str)
    elif OllamaBackend.is_installed():
        table.add_row("Ollama", "⚠️ No corriendo", "Ejecuta: ollama serve")
    else:
        table.add_row("Ollama", "❌ No instalado", "https://ollama.ai")

    # LM Studio
    lm_studio = OpenAICompatBackend(base_url="http://localhost:1234/v1")
    if lm_studio.is_available():
        models = lm_studio.list_models()[:3]
        models_str = ", ".join(models) if models else "Modelo cargado"
        table.add_row("LM Studio", "✅ Disponible", models_str)
    else:
        table.add_row("LM Studio", "❌ No corriendo", "Inicia LM Studio")

    console.print(table)

    # Recomendación
    detected, _ = auto_detect_backend()
    if detected != "none":
        console.print(f"\n[green]Recomendado:[/green] {detected}")
    else:
        console.print("\n[yellow]No hay backends disponibles. Instala Ollama o LM Studio.[/yellow]")
