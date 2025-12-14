"""
Plugin Skill for R CLI.

Manage plugins: create, install, enable, disable and remove.
"""

from pathlib import Path

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool
from r_cli.core.plugins import PluginManager


class PluginSkill(Skill):
    """Skill for plugin management."""

    name = "plugin"
    description = "Manage community plugins for R CLI"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        plugins_dir = None
        if hasattr(self.config, "home_dir"):
            plugins_dir = Path(self.config.home_dir) / "plugins"
        self.manager = PluginManager(plugins_dir)

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="plugin_create",
                description="Create a new plugin from template",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Plugin name (letters, numbers, underscores only)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Plugin description",
                        },
                        "author": {
                            "type": "string",
                            "description": "Author name",
                        },
                    },
                    "required": ["name"],
                },
                handler=self.create_plugin,
            ),
            Tool(
                name="plugin_install",
                description="Install a plugin from local directory or GitHub",
                parameters={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "Local path or GitHub URL of the plugin",
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Force reinstall if already exists",
                        },
                    },
                    "required": ["source"],
                },
                handler=self.install_plugin,
            ),
            Tool(
                name="plugin_uninstall",
                description="Uninstall a plugin",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the plugin to uninstall",
                        },
                    },
                    "required": ["name"],
                },
                handler=self.uninstall_plugin,
            ),
            Tool(
                name="plugin_enable",
                description="Enable an installed plugin",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Plugin name",
                        },
                    },
                    "required": ["name"],
                },
                handler=self.enable_plugin,
            ),
            Tool(
                name="plugin_disable",
                description="Disable a plugin",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Plugin name",
                        },
                    },
                    "required": ["name"],
                },
                handler=self.disable_plugin,
            ),
            Tool(
                name="plugin_list",
                description="List all installed plugins",
                parameters={"type": "object", "properties": {}},
                handler=self.list_plugins,
            ),
            Tool(
                name="plugin_info",
                description="Show detailed plugin information",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Plugin name",
                        },
                    },
                    "required": ["name"],
                },
                handler=self.plugin_info,
            ),
            Tool(
                name="plugin_validate",
                description="Validate the structure of a plugin",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the plugin directory",
                        },
                    },
                    "required": ["path"],
                },
                handler=self.validate_plugin,
            ),
        ]

    def create_plugin(
        self,
        name: str,
        description: str = "My custom plugin",
        author: str = "",
    ) -> str:
        """Create a new plugin."""
        return self.manager.create_plugin(name, description, author)

    def install_plugin(
        self,
        source: str,
        force: bool = False,
    ) -> str:
        """Install a plugin."""
        return self.manager.install_plugin(source, force)

    def uninstall_plugin(self, name: str) -> str:
        """Uninstall a plugin."""
        return self.manager.uninstall_plugin(name)

    def enable_plugin(self, name: str) -> str:
        """Enable a plugin."""
        return self.manager.enable_plugin(name)

    def disable_plugin(self, name: str) -> str:
        """Disable a plugin."""
        return self.manager.disable_plugin(name)

    def list_plugins(self) -> str:
        """List installed plugins."""
        return self.manager.list_plugins()

    def plugin_info(self, name: str) -> str:
        """Get plugin information."""
        return self.manager.get_plugin_info(name)

    def validate_plugin(self, path: str) -> str:
        """Validate a plugin."""
        plugin_path = Path(path).expanduser()
        if not plugin_path.is_dir():
            return f"Error: '{path}' is not a valid directory"

        valid, message = self.manager.validate_plugin(plugin_path)
        return message

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "list")

        if action == "list":
            return self.list_plugins()
        elif action == "create":
            name = kwargs.get("name")
            if not name:
                return "Error: --name is required to create a plugin"
            return self.create_plugin(
                name=name,
                description=kwargs.get("description", "My plugin"),
                author=kwargs.get("author", ""),
            )
        elif action == "install":
            source = kwargs.get("source")
            if not source:
                return "Error: --source is required to install"
            return self.install_plugin(source, kwargs.get("force", False))
        elif action == "uninstall" or action == "remove":
            name = kwargs.get("name")
            if not name:
                return "Error: --name is required to uninstall"
            return self.uninstall_plugin(name)
        elif action == "enable":
            name = kwargs.get("name")
            if not name:
                return "Error: --name is required"
            return self.enable_plugin(name)
        elif action == "disable":
            name = kwargs.get("name")
            if not name:
                return "Error: --name is required"
            return self.disable_plugin(name)
        elif action == "info":
            name = kwargs.get("name")
            if not name:
                return "Error: --name is required"
            return self.plugin_info(name)
        elif action == "validate":
            path = kwargs.get("path")
            if not path:
                return "Error: --path is required"
            return self.validate_plugin(path)
        else:
            return self.list_plugins()
