"""Tests for local project inspection."""

from pathlib import Path

import pytest

from r_cli.project_inspector import initialize_project, inspect_project


def test_inspect_python_document_project(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")
    (tmp_path / "README.md").write_text("# Demo\n")
    (tmp_path / "report.pdf").write_bytes(b"%PDF")

    report = inspect_project(str(tmp_path))

    assert report.stacks == ["Python"]
    assert "Documents" in report.traits
    assert "code" in report.recommended_skills
    assert "pdf" in report.recommended_skills
    assert report.files_scanned == 3


def test_inspect_detects_nested_backend_and_frontend(tmp_path: Path):
    backend = tmp_path / "backend"
    frontend = tmp_path / "frontend"
    backend.mkdir()
    frontend.mkdir()
    (backend / "requirements.txt").write_text("fastapi\n")
    (frontend / "package.json").write_text("{}\n")

    report = inspect_project(str(tmp_path))

    assert "Python" in report.stacks
    assert "JavaScript" in report.stacks


def test_inspect_ignores_dependency_directories(tmp_path: Path):
    (tmp_path / "package.json").write_text("{}\n")
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "huge.js").write_text("x\n")

    report = inspect_project(str(tmp_path))

    assert report.files_scanned == 1


def test_inspect_rejects_missing_path(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        inspect_project(str(tmp_path / "missing"))


def test_initialize_project_writes_recommended_profile(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")

    config_path, report = initialize_project(str(tmp_path))

    content = config_path.read_text()
    assert config_path.name == ".r-cli.yaml"
    assert "mode: whitelist" in content
    assert "code" in content
    assert "code" in report.recommended_skills


def test_initialize_project_does_not_overwrite_by_default(tmp_path: Path):
    (tmp_path / ".r-cli.yaml").write_text("existing: true\n")

    with pytest.raises(FileExistsError):
        initialize_project(str(tmp_path))
