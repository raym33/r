"""
Temas visuales para R CLI.

Temas disponibles:
- ps2: Inspirado en PlayStation 2 (azul, partículas)
- matrix: Verde sobre negro estilo Matrix
- minimal: Limpio y simple
- retro: Colores CRT vintage
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Theme:
    """Definición de un tema visual."""

    name: str
    primary: str  # Color principal (Rich markup)
    secondary: str  # Color secundario
    accent: str  # Color de acento
    success: str  # Color de éxito
    error: str  # Color de error
    warning: str  # Color de warning
    dim: str  # Color atenuado
    background: Optional[str] = None  # Si aplica

    # Símbolos
    prompt_symbol: str = "❯"
    thinking_symbol: str = "◉"
    success_symbol: str = "✓"
    error_symbol: str = "✗"
    bullet_symbol: str = "•"


# Temas predefinidos
THEMES = {
    "ps2": Theme(
        name="ps2",
        primary="bold blue",
        secondary="cyan",
        accent="bright_blue",
        success="green",
        error="red",
        warning="yellow",
        dim="dim white",
        prompt_symbol="▶",
        thinking_symbol="◈",
    ),
    "matrix": Theme(
        name="matrix",
        primary="bold green",
        secondary="bright_green",
        accent="green",
        success="bright_green",
        error="red",
        warning="yellow",
        dim="dim green",
        prompt_symbol="$",
        thinking_symbol="●",
    ),
    "minimal": Theme(
        name="minimal",
        primary="bold white",
        secondary="white",
        accent="cyan",
        success="green",
        error="red",
        warning="yellow",
        dim="dim",
        prompt_symbol=">",
        thinking_symbol="·",
    ),
    "retro": Theme(
        name="retro",
        primary="bold magenta",
        secondary="cyan",
        accent="yellow",
        success="green",
        error="red",
        warning="bright_yellow",
        dim="dim magenta",
        prompt_symbol="►",
        thinking_symbol="◆",
    ),
    "cyberpunk": Theme(
        name="cyberpunk",
        primary="bold bright_magenta",
        secondary="bright_cyan",
        accent="bright_yellow",
        success="bright_green",
        error="bright_red",
        warning="bright_yellow",
        dim="dim magenta",
        prompt_symbol="»",
        thinking_symbol="◎",
    ),
}


def get_theme(name: str) -> Theme:
    """Obtiene un tema por nombre."""
    return THEMES.get(name, THEMES["ps2"])


def list_themes() -> list[str]:
    """Lista los temas disponibles."""
    return list(THEMES.keys())
