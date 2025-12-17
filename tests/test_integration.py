"""Integration tests for R CLI.

Tests for skill loading, API, and configuration.
"""

import tempfile
from pathlib import Path

import pytest

from r_cli.core.config import Config


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def config(temp_dir):
    """Configuration for tests."""
    cfg = Config()
    cfg.output_dir = temp_dir
    cfg.home_dir = temp_dir
    return cfg


# =============================================================================
# Skill Loading Tests
# =============================================================================


class TestSkillLoading:
    """Tests for loading and managing skills."""

    def test_load_all_skills(self, config):
        """Test loading all skills."""
        from r_cli.core.agent import Agent

        agent = Agent(config)
        agent.load_skills()

        assert len(agent.skills) > 0

    def test_skill_count(self, config):
        """Test we have the expected number of skills."""
        from r_cli.core.agent import Agent

        agent = Agent(config)
        agent.load_skills()

        # We should have 60+ skills (some may fail to load without deps)
        assert len(agent.skills) >= 60

    def test_each_skill_has_name(self, config):
        """Test each loaded skill has a name."""
        from r_cli.core.agent import Agent

        agent = Agent(config)
        agent.load_skills()

        for skill in agent.skills.values():
            assert hasattr(skill, "name")
            assert skill.name is not None
            assert len(skill.name) > 0

    def test_each_skill_has_description(self, config):
        """Test each loaded skill has a description."""
        from r_cli.core.agent import Agent

        agent = Agent(config)
        agent.load_skills()

        for skill in agent.skills.values():
            assert hasattr(skill, "description")

    def test_each_skill_has_tools(self, config):
        """Test each loaded skill provides tools."""
        from r_cli.core.agent import Agent

        agent = Agent(config)
        agent.load_skills()

        for name, skill in agent.skills.items():
            tools = skill.get_tools()
            assert len(tools) >= 1, f"Skill {name} has no tools"


# =============================================================================
# API Integration Tests
# =============================================================================


class TestAPIIntegration:
    """Tests for API server integration."""

    def test_app_creation(self):
        """Test FastAPI app can be created."""
        from r_cli.api.server import create_app

        app = create_app()
        assert app is not None

    def test_app_has_routes(self):
        """Test app has expected routes."""
        from r_cli.api.server import create_app

        app = create_app()
        routes = [route.path for route in app.routes]

        assert any("/chat" in r for r in routes)
        assert any("/skills" in r for r in routes)

    def test_openapi_schema(self):
        """Test OpenAPI schema is generated."""
        from r_cli.api.server import create_app

        app = create_app()
        schema = app.openapi()

        assert "openapi" in schema
        assert "paths" in schema
        assert "info" in schema


# =============================================================================
# Config Integration Tests
# =============================================================================


class TestConfigIntegration:
    """Tests for configuration system."""

    def test_default_config(self):
        """Test default config is valid."""
        cfg = Config()

        assert cfg is not None
        assert hasattr(cfg, "llm")
        assert hasattr(cfg, "ui")

    def test_config_llm_settings(self):
        """Test LLM config settings."""
        cfg = Config()

        assert hasattr(cfg.llm, "provider") or hasattr(cfg.llm, "backend")
        assert hasattr(cfg.llm, "base_url")
        assert hasattr(cfg.llm, "model")

    def test_config_can_be_modified(self):
        """Test config can be modified."""
        cfg = Config()
        cfg.llm.model = "test-model"

        assert cfg.llm.model == "test-model"


# =============================================================================
# Performance Tests
# =============================================================================


class TestPerformance:
    """Basic performance tests."""

    def test_skill_loading_time(self, config):
        """Test skill loading completes in reasonable time."""
        import time

        from r_cli.core.agent import Agent

        start = time.time()
        agent = Agent(config)
        agent.load_skills()
        elapsed = time.time() - start

        # Should load in under 5 seconds
        assert elapsed < 5.0

    def test_tool_count(self, config):
        """Test total tool count."""
        from r_cli.core.agent import Agent

        agent = Agent(config)
        agent.load_skills()

        total_tools = 0
        for skill in agent.skills.values():
            total_tools += len(skill.get_tools())

        # Should have many tools available
        assert total_tools >= 100
