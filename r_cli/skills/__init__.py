"""
R CLI Skills System.

Skills are specialized mini-programs the agent can invoke.
Each skill provides:
- Tools for the LLM (function calling)
- Direct CLI execution
- Specialized prompts

Included skills:
- pdf: Generate PDF documents
- latex: Generate and compile LaTeX documents
- ocr: Extract text from images and scanned PDFs
- resume: Summarize long documents
- code: Generate and analyze code
- sql: Natural language SQL queries
- fs: Filesystem operations
- voice: Transcription with Whisper and TTS with Piper
- design: Image generation with Stable Diffusion
- calendar: Local calendar management with SQLite
- multiagent: Multi-agent orchestration
- plugin: Community plugin system
- rag: Semantic search with local embeddings
- web: Web scraping with BeautifulSoup
- git: Git operations
- clipboard: System clipboard management
- archive: ZIP, TAR, TAR.GZ compression/extraction
- screenshot: Screen captures
- email: Email sending via SMTP
- translate: Text translation between languages
- docker: Docker container management
- ssh: SSH connections and file transfer
- http: HTTP/REST client
- json: JSON/YAML manipulation
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from r_cli.core.agent import Skill
    from r_cli.skills.archive_skill import ArchiveSkill
    from r_cli.skills.calendar_skill import CalendarSkill
    from r_cli.skills.clipboard_skill import ClipboardSkill
    from r_cli.skills.code_skill import CodeSkill
    from r_cli.skills.design_skill import DesignSkill
    from r_cli.skills.docker_skill import DockerSkill
    from r_cli.skills.email_skill import EmailSkill
    from r_cli.skills.fs_skill import FilesystemSkill
    from r_cli.skills.git_skill import GitSkill
    from r_cli.skills.http_skill import HTTPSkill
    from r_cli.skills.json_skill import JSONSkill
    from r_cli.skills.latex_skill import LaTeXSkill
    from r_cli.skills.multiagent_skill import MultiAgentSkill
    from r_cli.skills.ocr_skill import OCRSkill
    from r_cli.skills.pdf_skill import PDFSkill
    from r_cli.skills.plugin_skill import PluginSkill
    from r_cli.skills.rag_skill import RAGSkill
    from r_cli.skills.resume_skill import ResumeSkill
    from r_cli.skills.screenshot_skill import ScreenshotSkill
    from r_cli.skills.sql_skill import SQLSkill
    from r_cli.skills.ssh_skill import SSHSkill
    from r_cli.skills.translate_skill import TranslateSkill
    from r_cli.skills.voice_skill import VoiceSkill
    from r_cli.skills.web_skill import WebSkill

# Registry: class_name -> (module_name, class_name)
_SKILL_REGISTRY: dict[str, tuple[str, str]] = {
    "ArchiveSkill": ("r_cli.skills.archive_skill", "ArchiveSkill"),
    "CalendarSkill": ("r_cli.skills.calendar_skill", "CalendarSkill"),
    "ClipboardSkill": ("r_cli.skills.clipboard_skill", "ClipboardSkill"),
    "CodeSkill": ("r_cli.skills.code_skill", "CodeSkill"),
    "DesignSkill": ("r_cli.skills.design_skill", "DesignSkill"),
    "DockerSkill": ("r_cli.skills.docker_skill", "DockerSkill"),
    "EmailSkill": ("r_cli.skills.email_skill", "EmailSkill"),
    "FilesystemSkill": ("r_cli.skills.fs_skill", "FilesystemSkill"),
    "GitSkill": ("r_cli.skills.git_skill", "GitSkill"),
    "HTTPSkill": ("r_cli.skills.http_skill", "HTTPSkill"),
    "JSONSkill": ("r_cli.skills.json_skill", "JSONSkill"),
    "LaTeXSkill": ("r_cli.skills.latex_skill", "LaTeXSkill"),
    "MultiAgentSkill": ("r_cli.skills.multiagent_skill", "MultiAgentSkill"),
    "OCRSkill": ("r_cli.skills.ocr_skill", "OCRSkill"),
    "PDFSkill": ("r_cli.skills.pdf_skill", "PDFSkill"),
    "PluginSkill": ("r_cli.skills.plugin_skill", "PluginSkill"),
    "RAGSkill": ("r_cli.skills.rag_skill", "RAGSkill"),
    "ResumeSkill": ("r_cli.skills.resume_skill", "ResumeSkill"),
    "ScreenshotSkill": ("r_cli.skills.screenshot_skill", "ScreenshotSkill"),
    "SQLSkill": ("r_cli.skills.sql_skill", "SQLSkill"),
    "SSHSkill": ("r_cli.skills.ssh_skill", "SSHSkill"),
    "TranslateSkill": ("r_cli.skills.translate_skill", "TranslateSkill"),
    "VoiceSkill": ("r_cli.skills.voice_skill", "VoiceSkill"),
    "WebSkill": ("r_cli.skills.web_skill", "WebSkill"),
}

# Cache for loaded skill classes
_LOADED_SKILLS: dict[str, type] = {}


def _load_skill(name: str) -> type:
    """Load a skill class by name (lazy loading)."""
    if name in _LOADED_SKILLS:
        return _LOADED_SKILLS[name]

    if name not in _SKILL_REGISTRY:
        raise AttributeError(f"Skill not found: {name}")

    module_path, class_name = _SKILL_REGISTRY[name]
    module = import_module(module_path)
    skill_class = getattr(module, class_name)
    _LOADED_SKILLS[name] = skill_class
    return skill_class


def __getattr__(name: str) -> Any:
    """Lazy loading of skill classes when accessed as module attributes."""
    if name in _SKILL_REGISTRY:
        return _load_skill(name)
    raise AttributeError(f"module 'r_cli.skills' has no attribute '{name}'")


def get_all_skills() -> list[type["Skill"]]:
    """Return all available skill classes (lazy loaded)."""
    return [_load_skill(name) for name in _SKILL_REGISTRY]


__all__ = [
    "ArchiveSkill",
    "CalendarSkill",
    "ClipboardSkill",
    "CodeSkill",
    "DesignSkill",
    "DockerSkill",
    "EmailSkill",
    "FilesystemSkill",
    "GitSkill",
    "HTTPSkill",
    "JSONSkill",
    "LaTeXSkill",
    "MultiAgentSkill",
    "OCRSkill",
    "PDFSkill",
    "PluginSkill",
    "RAGSkill",
    "ResumeSkill",
    "SQLSkill",
    "SSHSkill",
    "ScreenshotSkill",
    "TranslateSkill",
    "VoiceSkill",
    "WebSkill",
    "get_all_skills",
]
