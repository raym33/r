"""
JSON/YAML Skill for R CLI.

Structured data manipulation:
- Parse and format JSON/YAML
- Transform structures
- Validate schemas
- Convert between formats
"""

import json
from pathlib import Path
from typing import Any, Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class JSONSkill(Skill):
    """Skill for JSON/YAML manipulation."""

    name = "json"
    description = "JSON/YAML: parse, format, transform and validate data"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="json_parse",
                description="Parse and format JSON",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "JSON string to parse",
                        },
                        "query": {
                            "type": "string",
                            "description": "JMESPath query to extract data (e.g., items[0].name)",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.json_parse,
            ),
            Tool(
                name="json_format",
                description="Format JSON with indentation",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "JSON to format",
                        },
                        "indent": {
                            "type": "integer",
                            "description": "Indentation spaces (default: 2)",
                        },
                        "sort_keys": {
                            "type": "boolean",
                            "description": "Sort keys alphabetically",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.json_format,
            ),
            Tool(
                name="json_minify",
                description="Minify JSON by removing whitespace",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "JSON to minify",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.json_minify,
            ),
            Tool(
                name="yaml_to_json",
                description="Convert YAML to JSON",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "YAML string to convert",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.yaml_to_json,
            ),
            Tool(
                name="json_to_yaml",
                description="Convert JSON to YAML",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "JSON string to convert",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.json_to_yaml,
            ),
            Tool(
                name="json_diff",
                description="Compare two JSON objects and show differences",
                parameters={
                    "type": "object",
                    "properties": {
                        "json1": {
                            "type": "string",
                            "description": "First JSON",
                        },
                        "json2": {
                            "type": "string",
                            "description": "Second JSON",
                        },
                    },
                    "required": ["json1", "json2"],
                },
                handler=self.json_diff,
            ),
            Tool(
                name="json_validate",
                description="Validate JSON against a schema",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "JSON to validate",
                        },
                        "schema": {
                            "type": "string",
                            "description": "JSON Schema for validation",
                        },
                    },
                    "required": ["data", "schema"],
                },
                handler=self.json_validate,
            ),
            Tool(
                name="json_from_file",
                description="Read and parse a JSON/YAML file",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "File path",
                        },
                        "query": {
                            "type": "string",
                            "description": "Optional JMESPath query",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.json_from_file,
            ),
        ]

    def json_parse(self, data: str, query: Optional[str] = None) -> str:
        """Parse and optionally query JSON."""
        try:
            parsed = json.loads(data)

            if query:
                try:
                    import jmespath

                    result = jmespath.search(query, parsed)
                    return json.dumps(result, indent=2, ensure_ascii=False)
                except ImportError:
                    return "Error: jmespath not installed. Run: pip install jmespath"
                except Exception as e:
                    return f"Query error: {e}"

            return json.dumps(parsed, indent=2, ensure_ascii=False)

        except json.JSONDecodeError as e:
            return f"Error parsing JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def json_format(
        self,
        data: str,
        indent: int = 2,
        sort_keys: bool = False,
    ) -> str:
        """Format JSON with indentation."""
        try:
            parsed = json.loads(data)
            return json.dumps(
                parsed,
                indent=indent,
                sort_keys=sort_keys,
                ensure_ascii=False,
            )
        except json.JSONDecodeError as e:
            return f"Error parsing JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def json_minify(self, data: str) -> str:
        """Minify JSON."""
        try:
            parsed = json.loads(data)
            return json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
        except json.JSONDecodeError as e:
            return f"Error parsing JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def yaml_to_json(self, data: str) -> str:
        """Convert YAML to JSON."""
        try:
            import yaml

            parsed = yaml.safe_load(data)
            return json.dumps(parsed, indent=2, ensure_ascii=False)

        except ImportError:
            return "Error: PyYAML not installed. Run: pip install pyyaml"
        except yaml.YAMLError as e:
            return f"Error parsing YAML: {e}"
        except Exception as e:
            return f"Error: {e}"

    def json_to_yaml(self, data: str) -> str:
        """Convert JSON to YAML."""
        try:
            import yaml

            parsed = json.loads(data)
            return yaml.dump(
                parsed,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

        except ImportError:
            return "Error: PyYAML not installed. Run: pip install pyyaml"
        except json.JSONDecodeError as e:
            return f"Error parsing JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def json_diff(self, json1: str, json2: str) -> str:
        """Compare two JSON objects."""
        try:
            obj1 = json.loads(json1)
            obj2 = json.loads(json2)

            differences = self._compare_objects(obj1, obj2, "")

            if not differences:
                return "JSON objects are identical"

            result = ["Differences found:\n"]
            for diff in differences[:50]:  # Limit
                result.append(f"  {diff}")

            if len(differences) > 50:
                result.append(f"\n  ... and {len(differences) - 50} more differences")

            return "\n".join(result)

        except json.JSONDecodeError as e:
            return f"Error parsing JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def _compare_objects(
        self,
        obj1: Any,
        obj2: Any,
        path: str,
    ) -> list[str]:
        """Compare objects recursively."""
        differences = []

        if type(obj1) != type(obj2):
            differences.append(
                f"{path}: different type ({type(obj1).__name__} vs {type(obj2).__name__})"
            )
            return differences

        if isinstance(obj1, dict):
            all_keys = set(obj1.keys()) | set(obj2.keys())
            for key in all_keys:
                new_path = f"{path}.{key}" if path else key
                if key not in obj1:
                    differences.append(f"{new_path}: only in second JSON")
                elif key not in obj2:
                    differences.append(f"{new_path}: only in first JSON")
                else:
                    differences.extend(self._compare_objects(obj1[key], obj2[key], new_path))

        elif isinstance(obj1, list):
            if len(obj1) != len(obj2):
                differences.append(f"{path}: different length ({len(obj1)} vs {len(obj2)})")
            for i, (item1, item2) in enumerate(zip(obj1, obj2)):
                differences.extend(self._compare_objects(item1, item2, f"{path}[{i}]"))

        elif obj1 != obj2:
            v1 = repr(obj1)[:50]
            v2 = repr(obj2)[:50]
            differences.append(f"{path}: {v1} != {v2}")

        return differences

    def json_validate(self, data: str, schema: str) -> str:
        """Validate JSON against a schema."""
        try:
            import jsonschema

            data_obj = json.loads(data)
            schema_obj = json.loads(schema)

            jsonschema.validate(data_obj, schema_obj)
            return "JSON is valid according to schema"

        except ImportError:
            return "Error: jsonschema not installed. Run: pip install jsonschema"
        except jsonschema.ValidationError as e:
            return f"Validation failed:\n  Path: {'.'.join(str(p) for p in e.path)}\n  Error: {e.message}"
        except jsonschema.SchemaError as e:
            return f"Schema error: {e.message}"
        except json.JSONDecodeError as e:
            return f"Error parsing JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def json_from_file(self, file_path: str, query: Optional[str] = None) -> str:
        """Read and parse a JSON/YAML file."""
        try:
            path = Path(file_path).expanduser()

            if not path.exists():
                return f"Error: File not found: {file_path}"

            content = path.read_text(encoding="utf-8")

            # Detect format
            suffix = path.suffix.lower()

            if suffix in (".yaml", ".yml"):
                try:
                    import yaml

                    parsed = yaml.safe_load(content)
                except ImportError:
                    return "Error: PyYAML not installed"
            else:
                parsed = json.loads(content)

            if query:
                try:
                    import jmespath

                    result = jmespath.search(query, parsed)
                    return json.dumps(result, indent=2, ensure_ascii=False)
                except ImportError:
                    return "Error: jmespath not installed"
                except Exception as e:
                    return f"Query error: {e}"

            return json.dumps(parsed, indent=2, ensure_ascii=False)

        except json.JSONDecodeError as e:
            return f"Error parsing JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "parse")
        data = kwargs.get("data", "")

        if action == "parse":
            return self.json_parse(data, kwargs.get("query"))
        elif action == "format":
            return self.json_format(data, kwargs.get("indent", 2))
        elif action == "minify":
            return self.json_minify(data)
        elif action == "to_yaml":
            return self.json_to_yaml(data)
        elif action == "from_yaml":
            return self.yaml_to_json(data)
        elif action == "diff":
            return self.json_diff(kwargs.get("json1", ""), kwargs.get("json2", ""))
        elif action == "validate":
            return self.json_validate(data, kwargs.get("schema", ""))
        elif action == "file":
            return self.json_from_file(kwargs.get("file", ""))
        else:
            return f"Unrecognized action: {action}"
