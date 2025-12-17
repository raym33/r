"""
Central configuration for R CLI.

Supports multiple LLM backends:
- LM Studio (default): http://localhost:1234/v1
- Ollama: http://localhost:11434/v1
- Custom: any OpenAI-compatible server
"""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


class LLMConfig(BaseModel):
    """LLM backend configuration."""

    # Backend: auto, mlx, ollama, lm-studio, openai-compatible
    backend: str = "auto"

    # General configuration
    model: str = "auto"  # auto = detect best available model
    temperature: float = 0.7
    max_tokens: int = 4096

    # OpenAI-compatible configuration (LM Studio, vLLM, etc.)
    base_url: str = "http://localhost:1234/v1"
    api_key: str = "not-needed"

    # Specialized models (optional)
    coder_model: Optional[str] = None
    vision_model: Optional[str] = None

    # Timeouts (in seconds)
    request_timeout: float = 30.0  # Timeout for LLM requests
    skill_timeout: float = 60.0  # Timeout for skill execution
    connection_timeout: float = 10.0  # Timeout for initial connection

    # Token limits
    max_context_tokens: int = 8192  # Maximum tokens in context
    token_warning_threshold: float = 0.8  # Warn at 80% of limit

    # Legacy compatibility
    provider: str = "auto"  # Alias for backend


class RAGConfig(BaseModel):
    """RAG (Retrieval Augmented Generation) configuration."""

    enabled: bool = True
    chunk_size: int = 1000
    chunk_overlap: int = 200
    collection_name: str = "r_cli_knowledge"
    persist_directory: str = "~/.r-cli/vectordb"


class UIConfig(BaseModel):
    """Terminal interface configuration."""

    theme: str = "ps2"  # ps2, matrix, minimal, retro
    show_thinking: bool = True  # Show agent reasoning
    show_tool_calls: bool = True  # Show tool calls
    animation_speed: float = 0.05  # Animation speed


class SkillsConfig(BaseModel):
    """Enabled/disabled skills configuration."""

    # Skills enabled by default (empty list = all enabled)
    enabled: list[str] = []  # If empty, all are enabled

    # Explicitly disabled skills
    disabled: list[str] = []  # List of skills to disable

    # Skills that require confirmation before execution
    require_confirmation: list[str] = []  # For example: ["ssh", "docker"]

    # Mode: "whitelist" (only enabled), "blacklist" (all except disabled), "lite" (essential only), "auto" (detect)
    mode: str = "blacklist"  # blacklist = use only 'disabled', whitelist = use only 'enabled'

    # Essential skills for lite mode (loaded when context is limited)
    LITE_SKILLS: list[str] = [
        "datetime",
        "math",
        "text",
        "json",
        "crypto",
        "fs",
        "code",
    ]

    # Standard skills for medium context (8k-16k tokens)
    STANDARD_SKILLS: list[str] = [
        "datetime", "math", "text", "json", "crypto", "fs", "code",
        "pdf", "markdown", "yaml", "csv", "regex", "archive",
        "git", "http", "sql", "translate",
    ]

    def is_skill_enabled(self, skill_name: str) -> bool:
        """Check if a skill is enabled."""
        if self.mode == "lite":
            return skill_name in self.LITE_SKILLS
        elif self.mode == "standard":
            return skill_name in self.STANDARD_SKILLS
        elif self.mode == "whitelist":
            # In whitelist mode, only explicitly enabled skills
            return skill_name in self.enabled if self.enabled else True
        else:
            # In blacklist mode, all except disabled
            return skill_name not in self.disabled

    def enable_skill(self, skill_name: str) -> None:
        """Enable a skill."""
        if skill_name in self.disabled:
            self.disabled.remove(skill_name)
        if self.mode == "whitelist" and skill_name not in self.enabled:
            self.enabled.append(skill_name)

    def disable_skill(self, skill_name: str) -> None:
        """Disable a skill."""
        if skill_name in self.enabled:
            self.enabled.remove(skill_name)
        if self.mode == "blacklist" and skill_name not in self.disabled:
            self.disabled.append(skill_name)

    def set_auto_mode(self, max_context_tokens: int) -> str:
        """Auto-detect appropriate skill mode based on context size."""
        if max_context_tokens < 8000:
            self.mode = "lite"
            return "lite"
        elif max_context_tokens < 32000:
            self.mode = "standard"
            return "standard"
        else:
            self.mode = "blacklist"
            return "full"


class Config(BaseModel):
    """Main R CLI configuration."""

    llm: LLMConfig = LLMConfig()
    rag: RAGConfig = RAGConfig()
    ui: UIConfig = UIConfig()
    skills: SkillsConfig = SkillsConfig()

    # Directories
    home_dir: str = "~/.r-cli"
    skills_dir: str = "~/.r-cli/skills"  # User's custom skills
    output_dir: str = "~/r-cli-output"  # Generated PDFs, images, etc.

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        """Load configuration from YAML file or use defaults."""

        if config_path is None:
            config_path = os.path.expanduser("~/.r-cli/config.yaml")

        path = Path(config_path)

        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
                return cls(**data) if data else cls()

        return cls()

    def save(self, config_path: Optional[str] = None) -> None:
        """Save configuration to YAML file."""

        if config_path is None:
            config_path = os.path.expanduser("~/.r-cli/config.yaml")

        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""

        for dir_attr in ["home_dir", "skills_dir", "output_dir"]:
            dir_path = Path(os.path.expanduser(getattr(self, dir_attr)))
            dir_path.mkdir(parents=True, exist_ok=True)

        # Also the vectordb directory
        vectordb_path = Path(os.path.expanduser(self.rag.persist_directory))
        vectordb_path.mkdir(parents=True, exist_ok=True)


# Preset configurations for different backends
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
    """Return default configuration."""
    return Config()


def get_preset(name: str) -> LLMConfig:
    """Get a preset configuration by name."""
    if name not in PRESETS:
        raise ValueError(f"Preset not found: {name}. Available: {list(PRESETS.keys())}")
    return PRESETS[name].model_copy()
