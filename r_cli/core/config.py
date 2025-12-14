"""
Configuración central de R CLI.

Soporta múltiples backends de LLM:
- LM Studio (por defecto): http://localhost:1234/v1
- Ollama: http://localhost:11434/v1
- Custom: cualquier servidor OpenAI-compatible
"""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


class LLMConfig(BaseModel):
    """Configuración del backend LLM."""

    # Backend: auto, mlx, ollama, lm-studio, openai-compatible
    backend: str = "auto"

    # Configuración general
    model: str = "auto"  # auto = detectar mejor modelo disponible
    temperature: float = 0.7
    max_tokens: int = 4096

    # Configuración OpenAI-compatible (LM Studio, vLLM, etc.)
    base_url: str = "http://localhost:1234/v1"
    api_key: str = "not-needed"

    # Modelos especializados (opcional)
    coder_model: Optional[str] = None
    vision_model: Optional[str] = None

    # Legacy compatibility
    provider: str = "auto"  # Alias de backend


class RAGConfig(BaseModel):
    """Configuración de RAG (Retrieval Augmented Generation)."""

    enabled: bool = True
    chunk_size: int = 1000
    chunk_overlap: int = 200
    collection_name: str = "r_cli_knowledge"
    persist_directory: str = "~/.r-cli/vectordb"


class UIConfig(BaseModel):
    """Configuración de la interfaz de terminal."""

    theme: str = "ps2"  # ps2, matrix, minimal, retro
    show_thinking: bool = True  # Mostrar razonamiento del agente
    show_tool_calls: bool = True  # Mostrar llamadas a tools
    animation_speed: float = 0.05  # Velocidad de animaciones


class Config(BaseModel):
    """Configuración principal de R CLI."""

    llm: LLMConfig = LLMConfig()
    rag: RAGConfig = RAGConfig()
    ui: UIConfig = UIConfig()

    # Directorios
    home_dir: str = "~/.r-cli"
    skills_dir: str = "~/.r-cli/skills"  # Skills custom del usuario
    output_dir: str = "~/r-cli-output"  # PDFs, imágenes generadas, etc.

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        """Carga configuración desde archivo YAML o usa defaults."""

        if config_path is None:
            config_path = os.path.expanduser("~/.r-cli/config.yaml")

        path = Path(config_path)

        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
                return cls(**data) if data else cls()

        return cls()

    def save(self, config_path: Optional[str] = None) -> None:
        """Guarda configuración a archivo YAML."""

        if config_path is None:
            config_path = os.path.expanduser("~/.r-cli/config.yaml")

        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)

    def ensure_directories(self) -> None:
        """Crea los directorios necesarios si no existen."""

        for dir_attr in ["home_dir", "skills_dir", "output_dir"]:
            dir_path = Path(os.path.expanduser(getattr(self, dir_attr)))
            dir_path.mkdir(parents=True, exist_ok=True)

        # También el directorio de vectordb
        vectordb_path = Path(os.path.expanduser(self.rag.persist_directory))
        vectordb_path.mkdir(parents=True, exist_ok=True)


# Configuraciones preset para diferentes backends
PRESETS = {
    "auto": LLMConfig(
        backend="auto",
        model="auto",
    ),
    "mlx": LLMConfig(
        backend="mlx",
        model="qwen2.5-7b",
    ),
    "ollama": LLMConfig(
        backend="ollama",
        model="qwen2.5:7b",
    ),
    "lm-studio": LLMConfig(
        backend="lm-studio",
        base_url="http://localhost:1234/v1",
        model="local-model",
    ),
}


def get_default_config() -> Config:
    """Retorna configuración por defecto."""
    return Config()


def get_preset(name: str) -> LLMConfig:
    """Obtiene una configuración preset por nombre."""
    if name not in PRESETS:
        raise ValueError(f"Preset no encontrado: {name}. Disponibles: {list(PRESETS.keys())}")
    return PRESETS[name].model_copy()
