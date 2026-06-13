"""Fast, local project inspection for R CLI."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

IGNORED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "vendor",
}

STACK_MARKERS = {
    "Python": [
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "backend/requirements.txt",
        "backend/pyproject.toml",
    ],
    "JavaScript": ["package.json", "frontend/package.json", "site/package.json"],
    "Rust": ["Cargo.toml"],
    "Go": ["go.mod"],
    "Docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
}

SKILL_RULES = {
    "Python": ["code", "git", "benchmark"],
    "JavaScript": ["code", "git", "web"],
    "Rust": ["code", "git", "benchmark"],
    "Go": ["code", "git", "benchmark"],
    "Docker": ["docker", "network", "logs"],
    "Documents": ["pdf", "pdftools", "markdown", "msoffice", "ocr"],
    "Data": ["csv", "sql", "json", "yaml"],
    "Web app": ["web", "http", "openapi", "screenshot"],
    "AI service": ["rag", "benchmark", "metrics", "openapi"],
    "System service": ["system", "logs", "cron", "network"],
}


@dataclass
class ProjectReport:
    """Structured project inspection result."""

    path: str
    name: str
    stacks: list[str]
    traits: list[str]
    files_scanned: int
    extensions: dict[str, int]
    recommended_skills: list[str]
    suggested_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _detect_stacks(path: Path) -> list[str]:
    stacks = []
    for stack, markers in STACK_MARKERS.items():
        if any((path / marker).exists() for marker in markers):
            stacks.append(stack)
    return stacks


def _scan_files(path: Path, limit: int = 20_000) -> tuple[int, Counter[str], set[str]]:
    count = 0
    extensions: Counter[str] = Counter()
    names: set[str] = set()

    for root, directories, files in os.walk(path):
        directories[:] = [item for item in directories if item not in IGNORED_DIRECTORIES]
        for filename in files:
            count += 1
            names.add(filename.lower())
            suffix = Path(filename).suffix.lower() or "[no extension]"
            extensions[suffix] += 1
            if count >= limit:
                return count, extensions, names
    return count, extensions, names


def _detect_traits(path: Path, extensions: Counter[str], names: set[str]) -> list[str]:
    traits = []
    if any(extensions[ext] for ext in (".md", ".pdf", ".doc", ".docx", ".tex")):
        traits.append("Documents")
    if any(extensions[ext] for ext in (".csv", ".tsv", ".xlsx", ".xls", ".duckdb", ".db")):
        traits.append("Data")
    if "package.json" in names and any(
        (path / directory).exists() for directory in ("app", "src", "frontend", "site")
    ):
        traits.append("Web app")
    if any(name in names for name in ("ollama", "agent-card.json")) or any(
        token in name for name in names for token in ("rag", "agent", "embedding")
    ):
        traits.append("AI service")
    if any(name.endswith((".service", ".plist")) for name in names) or "systemd" in names:
        traits.append("System service")
    return traits


def inspect_project(path_value: str = ".") -> ProjectReport:
    """Inspect a local project without reading file contents."""
    path = Path(path_value).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Project path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Project path is not a directory: {path}")

    stacks = _detect_stacks(path)
    files_scanned, extension_counts, names = _scan_files(path)
    traits = _detect_traits(path, extension_counts, names)

    recommended = []
    for category in [*stacks, *traits]:
        for skill in SKILL_RULES.get(category, []):
            if skill not in recommended:
                recommended.append(skill)

    commands = ["r doctor", f"r tool git git_info --arg path={path}"]
    if "Documents" in traits:
        commands.append(f"r tool fs list_directory --arg path={path}")
    if "Docker" in stacks:
        commands.append("r tool docker docker_ps")
    if "AI service" in traits:
        commands.append("r skills --search rag")

    top_extensions = dict(extension_counts.most_common(12))
    return ProjectReport(
        path=str(path),
        name=path.name,
        stacks=stacks,
        traits=traits,
        files_scanned=files_scanned,
        extensions=top_extensions,
        recommended_skills=recommended,
        suggested_commands=commands,
    )


def initialize_project(path_value: str = ".", force: bool = False) -> tuple[Path, ProjectReport]:
    """Create a project-local R CLI profile from inspection results."""
    report = inspect_project(path_value)
    config_path = Path(report.path) / ".r-cli.yaml"
    if config_path.exists() and not force:
        raise FileExistsError(f"Configuration already exists: {config_path}")

    config = {
        "llm": {"backend": "auto", "model": "auto"},
        "skills": {
            "mode": "whitelist",
            "enabled": report.recommended_skills,
        },
    }
    config_path.write_text(
        yaml.safe_dump(config, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return config_path, report
