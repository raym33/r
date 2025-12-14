"""
Sistema de Skills de R CLI.

Los skills son mini-programas especializados que el agente puede invocar.
Cada skill provee:
- Tools para el LLM (function calling)
- Ejecución directa desde CLI
- Prompts especializados

Skills incluidos:
- pdf: Genera documentos PDF
- latex: Genera documentos LaTeX
- resume: Resume documentos largos
- code: Genera y analiza código
- sql: Consultas SQL en lenguaje natural
- fs: Operaciones de filesystem
"""

from typing import Type
from r_cli.core.agent import Skill

# Importar todos los skills
from r_cli.skills.pdf_skill import PDFSkill
from r_cli.skills.code_skill import CodeSkill
from r_cli.skills.sql_skill import SQLSkill
from r_cli.skills.fs_skill import FilesystemSkill
from r_cli.skills.resume_skill import ResumeSkill


def get_all_skills() -> list[Type[Skill]]:
    """Retorna todas las clases de skills disponibles."""
    return [
        PDFSkill,
        CodeSkill,
        SQLSkill,
        FilesystemSkill,
        ResumeSkill,
    ]


__all__ = [
    "get_all_skills",
    "PDFSkill",
    "CodeSkill",
    "SQLSkill",
    "FilesystemSkill",
    "ResumeSkill",
]
