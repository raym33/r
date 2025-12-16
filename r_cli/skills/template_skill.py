"""
Template Skill for R CLI.

Template rendering:
- Jinja2 templates
- String formatting
- Variable substitution
"""

import json
import re
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class TemplateSkill(Skill):
    """Skill for template rendering."""

    name = "template"
    description = "Template: render Jinja2, string format, variables"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="template_render",
                description="Render a template with variables",
                parameters={
                    "type": "object",
                    "properties": {
                        "template": {
                            "type": "string",
                            "description": "Template string (Jinja2 syntax: {{ var }})",
                        },
                        "variables": {
                            "type": "object",
                            "description": "Variables to substitute",
                        },
                    },
                    "required": ["template", "variables"],
                },
                handler=self.template_render,
            ),
            Tool(
                name="template_format",
                description="Python string formatting",
                parameters={
                    "type": "object",
                    "properties": {
                        "template": {
                            "type": "string",
                            "description": "Template with {name} placeholders",
                        },
                        "variables": {
                            "type": "object",
                            "description": "Variables to substitute",
                        },
                    },
                    "required": ["template", "variables"],
                },
                handler=self.template_format,
            ),
            Tool(
                name="template_extract_vars",
                description="Extract variable names from template",
                parameters={
                    "type": "object",
                    "properties": {
                        "template": {
                            "type": "string",
                            "description": "Template string",
                        },
                    },
                    "required": ["template"],
                },
                handler=self.template_extract_vars,
            ),
            Tool(
                name="template_validate",
                description="Validate Jinja2 template syntax",
                parameters={
                    "type": "object",
                    "properties": {
                        "template": {
                            "type": "string",
                            "description": "Template to validate",
                        },
                    },
                    "required": ["template"],
                },
                handler=self.template_validate,
            ),
            Tool(
                name="template_from_file",
                description="Load and render template from file",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to template file",
                        },
                        "variables": {
                            "type": "object",
                            "description": "Variables to substitute",
                        },
                    },
                    "required": ["file_path", "variables"],
                },
                handler=self.template_from_file,
            ),
        ]

    def _use_jinja2(self):
        """Try to use Jinja2 if available."""
        try:
            from jinja2 import Environment, Template
            return Template, Environment
        except ImportError:
            return None, None

    def template_render(self, template: str, variables: dict) -> str:
        """Render template with Jinja2."""
        template_class, _env_class = self._use_jinja2()

        if template_class:
            try:
                t = template_class(template)
                return t.render(**variables)
            except Exception as e:
                return f"Template error: {e}"

        # Fallback: simple {{ var }} replacement
        try:
            result = template
            for key, value in variables.items():
                result = result.replace("{{ " + key + " }}", str(value))
                result = result.replace("{{" + key + "}}", str(value))
            return result
        except Exception as e:
            return f"Error: {e}"

    def template_format(self, template: str, variables: dict) -> str:
        """Python string formatting."""
        try:
            return template.format(**variables)
        except KeyError as e:
            return f"Missing variable: {e}"
        except Exception as e:
            return f"Error: {e}"

    def template_extract_vars(self, template: str) -> str:
        """Extract variable names from template."""
        jinja_vars = set()
        format_vars = set()

        # Jinja2 style: {{ var }} and {{ var.attr }}
        for match in re.finditer(r"\{\{\s*(\w+)(?:\.\w+)*\s*\}\}", template):
            jinja_vars.add(match.group(1))

        # Jinja2 with filters: {{ var|filter }}
        for match in re.finditer(r"\{\{\s*(\w+)\s*\|", template):
            jinja_vars.add(match.group(1))

        # Python format style: {var}
        for match in re.finditer(r"\{(\w+)\}", template):
            format_vars.add(match.group(1))

        # Jinja2 loops and conditions: {% for x in items %}
        for match in re.finditer(r"\{%\s*for\s+\w+\s+in\s+(\w+)", template):
            jinja_vars.add(match.group(1))

        for match in re.finditer(r"\{%\s*if\s+(\w+)", template):
            jinja_vars.add(match.group(1))

        return json.dumps({
            "jinja2_variables": sorted(jinja_vars),
            "format_variables": sorted(format_vars),
            "all": sorted(jinja_vars | format_vars),
        }, indent=2)

    def template_validate(self, template: str) -> str:
        """Validate Jinja2 template syntax."""
        template_class, _env_class = self._use_jinja2()

        if not template_class:
            return json.dumps({
                "valid": None,
                "error": "Jinja2 not installed. Run: pip install jinja2",
            }, indent=2)

        try:
            from jinja2 import Environment, meta

            env = Environment()
            ast = env.parse(template)

            # Get undefined variables
            variables = meta.find_undeclared_variables(ast)

            return json.dumps({
                "valid": True,
                "variables_used": sorted(variables),
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "valid": False,
                "error": str(e),
            }, indent=2)

    def template_from_file(self, file_path: str, variables: dict) -> str:
        """Load and render template from file."""
        from pathlib import Path

        path = Path(file_path).expanduser()
        if not path.exists():
            return f"File not found: {file_path}"

        try:
            template = path.read_text()
            return self.template_render(template, variables)
        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "render")
        if action == "render":
            return self.template_render(
                kwargs.get("template", ""),
                kwargs.get("variables", {}),
            )
        return f"Unknown action: {action}"
