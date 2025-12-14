"""
Sistema de Skills de R CLI.

Los skills son mini-programas especializados que el agente puede invocar.
Cada skill provee:
- Tools para el LLM (function calling)
- Ejecución directa desde CLI
- Prompts especializados

Skills incluidos:
- pdf: Genera documentos PDF
- latex: Genera y compila documentos LaTeX
- ocr: Extrae texto de imágenes y PDFs escaneados
- resume: Resume documentos largos
- code: Genera y analiza código
- sql: Consultas SQL en lenguaje natural
- fs: Operaciones de filesystem
- voice: Transcripción con Whisper y TTS con Piper
- design: Generación de imágenes con Stable Diffusion
- calendar: Gestión de calendario local con SQLite
- multiagent: Orquestación de múltiples agentes especializados
- plugin: Sistema de plugins para la comunidad
- rag: Búsqueda semántica con embeddings locales
- web: Web scraping con BeautifulSoup
- git: Operaciones Git
- clipboard: Gestión del portapapeles del sistema
- archive: Compresión/extracción ZIP, TAR, TAR.GZ
- screenshot: Capturas de pantalla
"""

from typing import Type
from r_cli.core.agent import Skill

# Importar todos los skills
from r_cli.skills.pdf_skill import PDFSkill
from r_cli.skills.code_skill import CodeSkill
from r_cli.skills.sql_skill import SQLSkill
from r_cli.skills.fs_skill import FilesystemSkill
from r_cli.skills.resume_skill import ResumeSkill
from r_cli.skills.latex_skill import LaTeXSkill
from r_cli.skills.ocr_skill import OCRSkill
from r_cli.skills.voice_skill import VoiceSkill
from r_cli.skills.design_skill import DesignSkill
from r_cli.skills.calendar_skill import CalendarSkill
from r_cli.skills.multiagent_skill import MultiAgentSkill
from r_cli.skills.plugin_skill import PluginSkill
from r_cli.skills.rag_skill import RAGSkill
from r_cli.skills.web_skill import WebSkill
from r_cli.skills.git_skill import GitSkill
from r_cli.skills.clipboard_skill import ClipboardSkill
from r_cli.skills.archive_skill import ArchiveSkill
from r_cli.skills.screenshot_skill import ScreenshotSkill


def get_all_skills() -> list[Type[Skill]]:
    """Retorna todas las clases de skills disponibles."""
    return [
        PDFSkill,
        CodeSkill,
        SQLSkill,
        FilesystemSkill,
        ResumeSkill,
        LaTeXSkill,
        OCRSkill,
        VoiceSkill,
        DesignSkill,
        CalendarSkill,
        MultiAgentSkill,
        PluginSkill,
        RAGSkill,
        WebSkill,
        GitSkill,
        ClipboardSkill,
        ArchiveSkill,
        ScreenshotSkill,
    ]


__all__ = [
    "get_all_skills",
    "PDFSkill",
    "CodeSkill",
    "SQLSkill",
    "FilesystemSkill",
    "ResumeSkill",
    "LaTeXSkill",
    "OCRSkill",
    "VoiceSkill",
    "DesignSkill",
    "CalendarSkill",
    "MultiAgentSkill",
    "PluginSkill",
    "RAGSkill",
    "WebSkill",
    "GitSkill",
    "ClipboardSkill",
    "ArchiveSkill",
    "ScreenshotSkill",
]
