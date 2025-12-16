"""
Env Skill for R CLI.

Environment variable utilities:
- Read/write .env files
- Manage environment variables
- Compare environments
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class EnvSkill(Skill):
    """Skill for environment variable operations."""

    name = "env"
    description = "Env: .env files, environment variables"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="env_read",
                description="Read .env file",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to .env file (default: .env)",
                        },
                    },
                },
                handler=self.env_read,
            ),
            Tool(
                name="env_write",
                description="Write/update .env file",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to .env file",
                        },
                        "variables": {
                            "type": "object",
                            "description": "Variables to set",
                        },
                    },
                    "required": ["file_path", "variables"],
                },
                handler=self.env_write,
            ),
            Tool(
                name="env_get",
                description="Get environment variable(s)",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Variable name (empty for all)",
                        },
                        "filter": {
                            "type": "string",
                            "description": "Filter pattern (e.g., 'AWS_')",
                        },
                    },
                },
                handler=self.env_get,
            ),
            Tool(
                name="env_set",
                description="Set environment variable (current session)",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Variable name",
                        },
                        "value": {
                            "type": "string",
                            "description": "Variable value",
                        },
                    },
                    "required": ["name", "value"],
                },
                handler=self.env_set,
            ),
            Tool(
                name="env_diff",
                description="Compare two .env files",
                parameters={
                    "type": "object",
                    "properties": {
                        "file1": {
                            "type": "string",
                            "description": "First .env file",
                        },
                        "file2": {
                            "type": "string",
                            "description": "Second .env file",
                        },
                    },
                    "required": ["file1", "file2"],
                },
                handler=self.env_diff,
            ),
            Tool(
                name="env_template",
                description="Generate .env.example from .env (hide values)",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_file": {
                            "type": "string",
                            "description": "Source .env file",
                        },
                        "output_file": {
                            "type": "string",
                            "description": "Output .env.example file",
                        },
                    },
                    "required": ["input_file", "output_file"],
                },
                handler=self.env_template,
            ),
            Tool(
                name="env_validate",
                description="Validate .env file against template",
                parameters={
                    "type": "object",
                    "properties": {
                        "env_file": {
                            "type": "string",
                            "description": ".env file to validate",
                        },
                        "template_file": {
                            "type": "string",
                            "description": ".env.example template",
                        },
                    },
                    "required": ["env_file", "template_file"],
                },
                handler=self.env_validate,
            ),
        ]

    def _parse_env_file(self, content: str) -> dict:
        """Parse .env file content."""
        variables = {}
        for line in content.split("\n"):
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse KEY=value
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
            if match:
                key = match.group(1)
                value = match.group(2)
                # Remove quotes if present
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                variables[key] = value
        return variables

    def env_read(self, file_path: str = ".env") -> str:
        """Read .env file."""
        path = Path(file_path).expanduser()
        if not path.exists():
            return f"File not found: {file_path}"

        try:
            content = path.read_text()
            variables = self._parse_env_file(content)

            return json.dumps({
                "file": file_path,
                "count": len(variables),
                "variables": variables,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def env_write(self, file_path: str, variables: dict) -> str:
        """Write/update .env file."""
        path = Path(file_path).expanduser()

        try:
            # Read existing if file exists
            existing = {}
            if path.exists():
                content = path.read_text()
                existing = self._parse_env_file(content)

            # Merge
            existing.update(variables)

            # Write
            lines = []
            for key, value in sorted(existing.items()):
                # Quote value if it contains spaces or special chars
                if " " in str(value) or "=" in str(value):
                    value = f'"{value}"'
                lines.append(f"{key}={value}")

            path.write_text("\n".join(lines) + "\n")

            return json.dumps({
                "file": file_path,
                "updated": list(variables.keys()),
                "total": len(existing),
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def env_get(
        self,
        name: Optional[str] = None,
        filter: Optional[str] = None,
    ) -> str:
        """Get environment variables."""
        if name:
            value = os.environ.get(name)
            if value is None:
                return f"Variable not set: {name}"
            return f"{name}={value}"

        # Get all or filtered
        variables = {}
        for key, value in os.environ.items():
            if filter and not key.startswith(filter):
                continue
            variables[key] = value

        return json.dumps({
            "count": len(variables),
            "variables": dict(sorted(variables.items())),
        }, indent=2)

    def env_set(self, name: str, value: str) -> str:
        """Set environment variable."""
        os.environ[name] = value
        return f"Set {name}={value}"

    def env_diff(self, file1: str, file2: str) -> str:
        """Compare two .env files."""
        path1 = Path(file1).expanduser()
        path2 = Path(file2).expanduser()

        if not path1.exists():
            return f"File not found: {file1}"
        if not path2.exists():
            return f"File not found: {file2}"

        try:
            vars1 = self._parse_env_file(path1.read_text())
            vars2 = self._parse_env_file(path2.read_text())

            keys1 = set(vars1.keys())
            keys2 = set(vars2.keys())

            only_in_1 = keys1 - keys2
            only_in_2 = keys2 - keys1
            common = keys1 & keys2
            different = [k for k in common if vars1[k] != vars2[k]]

            return json.dumps({
                "only_in_file1": sorted(only_in_1),
                "only_in_file2": sorted(only_in_2),
                "different_values": different,
                "same": sorted([k for k in common if vars1[k] == vars2[k]]),
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def env_template(self, input_file: str, output_file: str) -> str:
        """Generate .env.example from .env."""
        path = Path(input_file).expanduser()
        if not path.exists():
            return f"File not found: {input_file}"

        try:
            content = path.read_text()
            lines = []

            for line in content.split("\n"):
                line_stripped = line.strip()

                # Keep comments and empty lines
                if not line_stripped or line_stripped.startswith("#"):
                    lines.append(line)
                    continue

                # Replace values with placeholders
                match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line_stripped)
                if match:
                    key = match.group(1)
                    # Generate placeholder based on key
                    if "KEY" in key or "SECRET" in key or "PASSWORD" in key or "TOKEN" in key:
                        placeholder = "your-secret-here"
                    elif "URL" in key or "HOST" in key:
                        placeholder = "https://example.com"
                    elif "PORT" in key:
                        placeholder = "3000"
                    elif "EMAIL" in key:
                        placeholder = "user@example.com"
                    else:
                        placeholder = "your-value-here"
                    lines.append(f"{key}={placeholder}")
                else:
                    lines.append(line)

            output_path = Path(output_file).expanduser()
            output_path.write_text("\n".join(lines))

            return f"Generated {output_file}"

        except Exception as e:
            return f"Error: {e}"

    def env_validate(self, env_file: str, template_file: str) -> str:
        """Validate .env against template."""
        env_path = Path(env_file).expanduser()
        template_path = Path(template_file).expanduser()

        if not env_path.exists():
            return f"File not found: {env_file}"
        if not template_path.exists():
            return f"File not found: {template_file}"

        try:
            env_vars = self._parse_env_file(env_path.read_text())
            template_vars = self._parse_env_file(template_path.read_text())

            required = set(template_vars.keys())
            present = set(env_vars.keys())

            missing = required - present
            extra = present - required
            empty = [k for k in present & required if not env_vars[k]]

            valid = len(missing) == 0 and len(empty) == 0

            return json.dumps({
                "valid": valid,
                "missing": sorted(missing),
                "empty": sorted(empty),
                "extra": sorted(extra),
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "read")
        if action == "read":
            return self.env_read(kwargs.get("file", ".env"))
        elif action == "get":
            return self.env_get(kwargs.get("name"))
        return f"Unknown action: {action}"
