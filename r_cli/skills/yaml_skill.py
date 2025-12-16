"""
YAML Skill for R CLI.

YAML manipulation:
- Read and write YAML files
- Convert between YAML and JSON
- Merge YAML documents
- Validate YAML syntax
"""

import json
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class YAMLSkill(Skill):
    """Skill for YAML manipulation."""

    name = "yaml"
    description = "YAML: read, write, convert and validate YAML files"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="yaml_read",
                description="Read and parse a YAML file",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to YAML file",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.yaml_read,
            ),
            Tool(
                name="yaml_write",
                description="Write data to a YAML file",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Output file path",
                        },
                        "data": {
                            "type": "string",
                            "description": "JSON data to write as YAML",
                        },
                    },
                    "required": ["file_path", "data"],
                },
                handler=self.yaml_write,
            ),
            Tool(
                name="yaml_to_json",
                description="Convert YAML to JSON",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "YAML string",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.yaml_to_json,
            ),
            Tool(
                name="yaml_from_json",
                description="Convert JSON to YAML",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "JSON string",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.yaml_from_json,
            ),
            Tool(
                name="yaml_validate",
                description="Validate YAML syntax",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "YAML string to validate",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.yaml_validate,
            ),
            Tool(
                name="yaml_merge",
                description="Merge multiple YAML files",
                parameters={
                    "type": "object",
                    "properties": {
                        "files": {
                            "type": "string",
                            "description": "Comma-separated list of file paths",
                        },
                    },
                    "required": ["files"],
                },
                handler=self.yaml_merge,
            ),
        ]

    def _get_yaml(self):
        """Import yaml module."""
        try:
            import yaml
            return yaml
        except ImportError:
            return None

    def yaml_read(self, file_path: str) -> str:
        """Read YAML file."""
        yaml = self._get_yaml()
        if not yaml:
            return "Error: PyYAML not installed. Run: pip install pyyaml"

        try:
            path = Path(file_path).expanduser()
            if not path.exists():
                return f"Error: File not found: {file_path}"

            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            return json.dumps(data, indent=2, ensure_ascii=False)

        except yaml.YAMLError as e:
            return f"Error parsing YAML: {e}"
        except Exception as e:
            return f"Error: {e}"

    def yaml_write(self, file_path: str, data: str) -> str:
        """Write data to YAML file."""
        yaml = self._get_yaml()
        if not yaml:
            return "Error: PyYAML not installed. Run: pip install pyyaml"

        try:
            parsed = json.loads(data)
            path = Path(file_path).expanduser()

            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(parsed, f, default_flow_style=False, allow_unicode=True)

            return f"Written to {file_path}"

        except json.JSONDecodeError as e:
            return f"Error parsing JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def yaml_to_json(self, data: str) -> str:
        """Convert YAML to JSON."""
        yaml = self._get_yaml()
        if not yaml:
            return "Error: PyYAML not installed"

        try:
            parsed = yaml.safe_load(data)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except yaml.YAMLError as e:
            return f"Error: {e}"

    def yaml_from_json(self, data: str) -> str:
        """Convert JSON to YAML."""
        yaml = self._get_yaml()
        if not yaml:
            return "Error: PyYAML not installed"

        try:
            parsed = json.loads(data)
            return yaml.dump(parsed, default_flow_style=False, allow_unicode=True)
        except json.JSONDecodeError as e:
            return f"Error: {e}"

    def yaml_validate(self, data: str) -> str:
        """Validate YAML syntax."""
        yaml = self._get_yaml()
        if not yaml:
            return "Error: PyYAML not installed"

        try:
            yaml.safe_load(data)
            return "YAML is valid"
        except yaml.YAMLError as e:
            return f"Invalid YAML: {e}"

    def yaml_merge(self, files: str) -> str:
        """Merge multiple YAML files."""
        yaml = self._get_yaml()
        if not yaml:
            return "Error: PyYAML not installed"

        try:
            file_list = [f.strip() for f in files.split(",")]
            merged = {}

            for file_path in file_list:
                path = Path(file_path).expanduser()
                if not path.exists():
                    return f"Error: File not found: {file_path}"

                with open(path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                if isinstance(data, dict):
                    merged.update(data)

            return yaml.dump(merged, default_flow_style=False, allow_unicode=True)

        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "read")
        if action == "read":
            return self.yaml_read(kwargs.get("file", ""))
        elif action == "write":
            return self.yaml_write(kwargs.get("file", ""), kwargs.get("data", ""))
        return f"Unknown action: {action}"
