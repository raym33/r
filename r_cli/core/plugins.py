"""
Plugin System for R CLI.

Allows the community to create and share custom skills.

Plugin structure:
~/.r-cli/plugins/
├── my_plugin/
│   ├── plugin.yaml       # Plugin metadata
│   ├── __init__.py       # Entry point
│   ├── skill.py          # Skill implementation
│   └── requirements.txt  # Optional dependencies

plugin.yaml format:
```yaml
name: my_plugin
version: 1.0.0
description: My custom plugin
author: Your Name
skills:
  - MyCustomSkill
dependencies:
  - requests>=2.28.0
```
"""

import hashlib
import importlib.util
import logging
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yaml

from r_cli.core.agent import Skill

logger = logging.getLogger(__name__)

# Regex to validate GitHub URLs
GITHUB_URL_PATTERN = re.compile(r"^https?://github\.com/[\w\-\.]+/[\w\-\.]+/?$")


class PluginStatus(Enum):
    """Plugin status."""

    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    OUTDATED = "outdated"


@dataclass
class PluginMetadata:
    """Plugin metadata."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    homepage: str = ""
    license: str = "MIT"
    skills: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    min_r_cli_version: str = "0.1.0"
    tags: list[str] = field(default_factory=list)

    # Internal fields
    path: Optional[Path] = None
    status: PluginStatus = PluginStatus.INSTALLED
    installed_at: str = ""
    checksum: str = ""


@dataclass
class PluginRegistry:
    """Registry of installed plugins."""

    plugins: dict[str, PluginMetadata] = field(default_factory=dict)
    last_updated: str = ""


class PluginManager:
    """Plugin manager for R CLI."""

    PLUGIN_YAML = "plugin.yaml"
    REGISTRY_FILE = "registry.yaml"

    # Template for creating new plugins
    PLUGIN_TEMPLATE = {
        "plugin.yaml": """name: {name}
version: 1.0.0
description: {description}
author: {author}
skills:
  - {skill_class}
dependencies: []
tags: []
""",
        "__init__.py": '''"""
{name} - Plugin for R CLI.

{description}
"""

from .skill import {skill_class}

__all__ = ["{skill_class}"]
''',
        "skill.py": '''"""
Main skill for plugin {name}.
"""

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class {skill_class}(Skill):
    """
    {description}

    Usage example:
        r {name} --help
    """

    name = "{name}"
    description = "{description}"

    def get_tools(self) -> list[Tool]:
        """Define available tools."""
        return [
            Tool(
                name="{name}_action",
                description="Main plugin action",
                parameters={{
                    "type": "object",
                    "properties": {{
                        "input": {{
                            "type": "string",
                            "description": "Input to process",
                        }},
                    }},
                    "required": ["input"],
                }},
                handler=self.main_action,
            ),
        ]

    def main_action(self, input: str) -> str:
        """Main plugin action."""
        # TODO: Implement logic here
        return f"Processed: {{input}}"

    def execute(self, **kwargs) -> str:
        """Direct execution from CLI."""
        input_text = kwargs.get("input", "")
        if not input_text:
            return f"Plugin {{self.name}} loaded successfully. Use --input to process."
        return self.main_action(input_text)
''',
        "requirements.txt": """# Plugin dependencies
# Example: requests>=2.28.0
""",
        "README.md": """# {name}

{description}

## Installation

```bash
r plugin install {name}
```

## Usage

```bash
r {name} --input "your input"
```

## Author

{author}
""",
    }

    def __init__(self, plugins_dir: Optional[Path] = None):
        """Initialize the plugin manager."""
        self.plugins_dir = plugins_dir or Path.home() / ".r-cli" / "plugins"
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

        self.registry_path = self.plugins_dir / self.REGISTRY_FILE
        self.registry = self._load_registry()
        self._loaded_skills: dict[str, type[Skill]] = {}

    def _load_registry(self) -> PluginRegistry:
        """Load the plugin registry."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path) as f:
                    data = yaml.safe_load(f) or {}
                    plugins = {}
                    for name, meta in data.get("plugins", {}).items():
                        plugins[name] = PluginMetadata(**meta)
                    return PluginRegistry(
                        plugins=plugins,
                        last_updated=data.get("last_updated", ""),
                    )
            except Exception as e:
                logger.warning(f"Failed to load plugin registry from {self.registry_path}: {e}")
        return PluginRegistry()

    def _save_registry(self):
        """Save the plugin registry."""
        data = {
            "plugins": {
                name: {
                    "name": meta.name,
                    "version": meta.version,
                    "description": meta.description,
                    "author": meta.author,
                    "homepage": meta.homepage,
                    "license": meta.license,
                    "skills": meta.skills,
                    "dependencies": meta.dependencies,
                    "tags": meta.tags,
                    "path": str(meta.path) if meta.path else None,
                    "status": meta.status.value,
                    "installed_at": meta.installed_at,
                    "checksum": meta.checksum,
                }
                for name, meta in self.registry.plugins.items()
            },
            "last_updated": datetime.now().isoformat(),
        }
        with open(self.registry_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def create_plugin(
        self,
        name: str,
        description: str = "My custom plugin",
        author: str = "",
    ) -> str:
        """Create a new plugin from template."""
        # Validate name
        if not name.isidentifier():
            return f"Error: Invalid plugin name '{name}'. Use only letters, numbers and underscores."

        plugin_dir = self.plugins_dir / name
        if plugin_dir.exists():
            return f"Error: Plugin '{name}' already exists at {plugin_dir}"

        try:
            # Create directory
            plugin_dir.mkdir(parents=True)

            # Generate class name
            skill_class = "".join(word.capitalize() for word in name.split("_")) + "Skill"

            # Create files from template
            for filename, template in self.PLUGIN_TEMPLATE.items():
                content = template.format(
                    name=name,
                    description=description,
                    author=author,
                    skill_class=skill_class,
                )
                (plugin_dir / filename).write_text(content)

            # Register plugin
            metadata = PluginMetadata(
                name=name,
                version="1.0.0",
                description=description,
                author=author,
                skills=[skill_class],
                path=plugin_dir,
                status=PluginStatus.INSTALLED,
                installed_at=datetime.now().isoformat(),
            )
            self.registry.plugins[name] = metadata
            self._save_registry()

            return f"""Plugin '{name}' created successfully at:
{plugin_dir}

Files created:
  - plugin.yaml (metadata)
  - __init__.py (entry point)
  - skill.py (implementation)
  - requirements.txt (dependencies)
  - README.md (documentation)

Next steps:
1. Edit skill.py to implement your logic
2. Add dependencies to requirements.txt
3. Test with: r {name} --input "test"
"""

        except Exception as e:
            # Cleanup on failure
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)
            return f"Error creating plugin: {e}"

    def install_plugin(
        self,
        source: str,
        force: bool = False,
    ) -> str:
        """Install a plugin from local directory or URL."""
        try:
            source_path = Path(source).expanduser()

            # If it's a local directory
            if source_path.is_dir():
                return self._install_from_directory(source_path, force)

            # If it's a GitHub URL
            if source.startswith("https://github.com/") or source.startswith("github.com/"):
                return self._install_from_github(source, force)

            # If it's just a name, look in plugins directory
            local_path = self.plugins_dir / source
            if local_path.is_dir():
                return self._install_from_directory(local_path, force)

            return f"Error: Plugin not found '{source}'"

        except Exception as e:
            return f"Error installing plugin: {e}"

    def _install_from_directory(self, source: Path, force: bool = False) -> str:
        """Install plugin from local directory."""
        # Verify plugin.yaml
        plugin_yaml = source / self.PLUGIN_YAML
        if not plugin_yaml.exists():
            return f"Error: {self.PLUGIN_YAML} not found in {source}"

        # Read metadata
        with open(plugin_yaml) as f:
            meta_dict = yaml.safe_load(f)

        name = meta_dict.get("name")
        if not name:
            return "Error: plugin.yaml must contain 'name'"

        # Check if already exists
        if name in self.registry.plugins and not force:
            return f"Plugin '{name}' is already installed. Use --force to reinstall."

        # Copy to plugins directory if not there
        dest_path = self.plugins_dir / name
        if source != dest_path:
            try:
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                shutil.copytree(source, dest_path)
            except PermissionError:
                return f"Error: No permission to write to {dest_path}"
            except OSError as e:
                return f"Error copying plugin files: {e}"

        # Install dependencies
        req_file = dest_path / "requirements.txt"
        if req_file.exists():
            deps_result = self._install_dependencies(req_file)
            if "Error" in deps_result:
                return deps_result

        # Calculate checksum
        checksum = self._calculate_checksum(dest_path)

        # Register
        metadata = PluginMetadata(
            name=name,
            version=meta_dict.get("version", "1.0.0"),
            description=meta_dict.get("description", ""),
            author=meta_dict.get("author", ""),
            homepage=meta_dict.get("homepage", ""),
            license=meta_dict.get("license", "MIT"),
            skills=meta_dict.get("skills", []),
            dependencies=meta_dict.get("dependencies", []),
            tags=meta_dict.get("tags", []),
            path=dest_path,
            status=PluginStatus.ENABLED,
            installed_at=datetime.now().isoformat(),
            checksum=checksum,
        )
        self.registry.plugins[name] = metadata
        self._save_registry()

        return f"Plugin '{name}' v{metadata.version} installed successfully."

    def _install_from_github(self, url: str, force: bool = False) -> str:
        """Install plugin from GitHub."""
        try:
            # Normalize URL
            if not url.startswith("https://"):
                url = "https://" + url

            # Validate GitHub URL for security
            if not GITHUB_URL_PATTERN.match(url.rstrip("/")):
                return (
                    f"Error: Invalid URL. Only GitHub URLs are allowed.\n"
                    f"Format: https://github.com/user/repository\n"
                    f"Received URL: {url}"
                )

            # Verify URL doesn't contain dangerous characters
            parsed = urlparse(url)
            if any(char in parsed.path for char in [";", "&", "|", "`", "$", "(", ")"]):
                return "Error: URL contains disallowed characters."

            # Extract repo name
            parts = url.rstrip("/").split("/")
            repo_name = parts[-1].replace(".git", "")

            # Validate repo name
            if not repo_name or not re.match(r"^[\w\-\.]+$", repo_name):
                return f"Error: Invalid repository name: {repo_name}"

            # Clone to temporary directory
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                clone_path = Path(tmpdir) / repo_name

                result = subprocess.run(
                    ["git", "clone", "--depth", "1", url, str(clone_path)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,  # 2 minute timeout
                )

                if result.returncode != 0:
                    return f"Error cloning repository: {result.stderr}"

                return self._install_from_directory(clone_path, force)

        except subprocess.TimeoutExpired:
            return "Error: Timeout cloning repository (>2 minutes)"
        except FileNotFoundError:
            return "Error: Git is not installed. Install git to clone from GitHub."
        except Exception as e:
            return f"Error installing from GitHub: {e}"

    def _install_dependencies(self, req_file: Path) -> str:
        """Install plugin dependencies."""
        try:
            # Read requirements
            deps = [
                line.strip()
                for line in req_file.read_text().splitlines()
                if line.strip() and not line.startswith("#")
            ]

            if not deps:
                return "OK"

            # Install with pip
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet"] + deps,
                check=False,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return f"Error installing dependencies: {result.stderr}"

            return "OK"

        except Exception as e:
            return f"Error: {e}"

    def _calculate_checksum(self, plugin_dir: Path) -> str:
        """Calculate plugin checksum."""
        hasher = hashlib.sha256()
        for file in sorted(plugin_dir.rglob("*.py")):
            hasher.update(file.read_bytes())
        return hasher.hexdigest()[:16]

    def uninstall_plugin(self, name: str) -> str:
        """Uninstall a plugin."""
        if name not in self.registry.plugins:
            return f"Plugin '{name}' is not installed."

        metadata = self.registry.plugins[name]

        # Delete directory
        if metadata.path and metadata.path.exists():
            try:
                shutil.rmtree(metadata.path)
            except PermissionError:
                return f"Error: No permission to delete {metadata.path}"
            except OSError as e:
                return f"Error deleting plugin files: {e}"

        # Remove from registry
        del self.registry.plugins[name]
        try:
            self._save_registry()
        except OSError as e:
            return f"Error saving registry: {e}"

        # Remove from loaded skills
        if name in self._loaded_skills:
            del self._loaded_skills[name]

        return f"Plugin '{name}' uninstalled successfully."

    def enable_plugin(self, name: str) -> str:
        """Enable a plugin."""
        if name not in self.registry.plugins:
            return f"Plugin '{name}' is not installed."

        self.registry.plugins[name].status = PluginStatus.ENABLED
        self._save_registry()
        return f"Plugin '{name}' enabled."

    def disable_plugin(self, name: str) -> str:
        """Disable a plugin."""
        if name not in self.registry.plugins:
            return f"Plugin '{name}' is not installed."

        self.registry.plugins[name].status = PluginStatus.DISABLED
        self._save_registry()
        return f"Plugin '{name}' disabled."

    def list_plugins(self) -> str:
        """List all installed plugins."""
        if not self.registry.plugins:
            return "No plugins installed.\n\nTo create one: r plugin create my_plugin"

        result = ["Installed plugins:\n"]

        for name, meta in sorted(self.registry.plugins.items()):
            status_icon = {
                PluginStatus.ENABLED: "[+]",
                PluginStatus.DISABLED: "[-]",
                PluginStatus.ERROR: "[!]",
                PluginStatus.OUTDATED: "[~]",
            }.get(meta.status, "[?]")

            result.append(f"  {status_icon} {name} v{meta.version}")
            result.append(f"      {meta.description}")
            if meta.skills:
                result.append(f"      Skills: {', '.join(meta.skills)}")
            if meta.author:
                result.append(f"      Author: {meta.author}")
            result.append("")

        result.append("Commands:")
        result.append("  r plugin create <name>    - Create new plugin")
        result.append("  r plugin install <path>   - Install plugin")
        result.append("  r plugin enable <name>    - Enable plugin")
        result.append("  r plugin disable <name>   - Disable plugin")
        result.append("  r plugin remove <name>    - Uninstall plugin")

        return "\n".join(result)

    def get_plugin_info(self, name: str) -> str:
        """Get detailed information about a plugin."""
        if name not in self.registry.plugins:
            return f"Plugin '{name}' is not installed."

        meta = self.registry.plugins[name]

        result = [
            f"Plugin: {meta.name}",
            f"Version: {meta.version}",
            f"Status: {meta.status.value}",
            f"Description: {meta.description}",
            f"Author: {meta.author}",
            f"License: {meta.license}",
            f"Skills: {', '.join(meta.skills)}",
            f"Dependencies: {', '.join(meta.dependencies) or 'none'}",
            f"Tags: {', '.join(meta.tags) or 'none'}",
            f"Installed: {meta.installed_at}",
            f"Path: {meta.path}",
            f"Checksum: {meta.checksum}",
        ]

        if meta.homepage:
            result.append(f"Homepage: {meta.homepage}")

        return "\n".join(result)

    def load_plugin_skills(self) -> dict[str, type[Skill]]:
        """Load skills from all enabled plugins."""
        loaded = {}

        for name, meta in self.registry.plugins.items():
            if meta.status != PluginStatus.ENABLED:
                continue

            if not meta.path or not meta.path.exists():
                meta.status = PluginStatus.ERROR
                continue

            try:
                # Add to path if not there
                plugin_path = str(meta.path)
                if plugin_path not in sys.path:
                    sys.path.insert(0, str(meta.path.parent))

                # Import module
                spec = importlib.util.spec_from_file_location(
                    name,
                    meta.path / "__init__.py",
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)

                # Load skills
                for skill_name in meta.skills:
                    if hasattr(module, skill_name):
                        skill_class = getattr(module, skill_name)
                        if isinstance(skill_class, type) and issubclass(skill_class, Skill):
                            loaded[name] = skill_class
                            self._loaded_skills[name] = skill_class

            except Exception as e:
                meta.status = PluginStatus.ERROR
                print(f"Error loading plugin '{name}': {e}")

        self._save_registry()
        return loaded

    def get_loaded_skills(self) -> dict[str, type[Skill]]:
        """Return already loaded skills."""
        if not self._loaded_skills:
            self.load_plugin_skills()
        return self._loaded_skills

    def validate_plugin(self, plugin_dir: Path) -> tuple[bool, str]:
        """Validate plugin structure."""
        errors = []

        # Verify plugin.yaml
        plugin_yaml = plugin_dir / self.PLUGIN_YAML
        if not plugin_yaml.exists():
            errors.append(f"Missing {self.PLUGIN_YAML}")
        else:
            try:
                with open(plugin_yaml) as f:
                    meta = yaml.safe_load(f)
                if not meta.get("name"):
                    errors.append("plugin.yaml: missing 'name'")
                if not meta.get("version"):
                    errors.append("plugin.yaml: missing 'version'")
                if not meta.get("skills"):
                    errors.append("plugin.yaml: missing 'skills'")
            except Exception as e:
                errors.append(f"plugin.yaml invalid: {e}")

        # Verify __init__.py
        init_file = plugin_dir / "__init__.py"
        if not init_file.exists():
            errors.append("Missing __init__.py")

        # Verify skill.py
        skill_file = plugin_dir / "skill.py"
        if not skill_file.exists():
            errors.append("Missing skill.py")

        if errors:
            return False, "Validation errors:\n" + "\n".join(f"  - {e}" for e in errors)

        return True, "Valid plugin"
