"""
Skill de JSON/YAML para R CLI.

Manipulación de datos estructurados:
- Parsear y formatear JSON/YAML
- Transformar estructuras
- Validar esquemas
- Convertir entre formatos
"""

import json
from pathlib import Path
from typing import Any, Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class JSONSkill(Skill):
    """Skill para manipulación de JSON/YAML."""

    name = "json"
    description = "JSON/YAML: parsear, formatear, transformar y validar datos"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="json_parse",
                description="Parsea y formatea JSON",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "String JSON a parsear",
                        },
                        "query": {
                            "type": "string",
                            "description": "JMESPath query para extraer datos (ej: items[0].name)",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.json_parse,
            ),
            Tool(
                name="json_format",
                description="Formatea JSON con indentación",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "JSON a formatear",
                        },
                        "indent": {
                            "type": "integer",
                            "description": "Espacios de indentación (default: 2)",
                        },
                        "sort_keys": {
                            "type": "boolean",
                            "description": "Ordenar claves alfabéticamente",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.json_format,
            ),
            Tool(
                name="json_minify",
                description="Minimiza JSON removiendo espacios",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "JSON a minimizar",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.json_minify,
            ),
            Tool(
                name="yaml_to_json",
                description="Convierte YAML a JSON",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "String YAML a convertir",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.yaml_to_json,
            ),
            Tool(
                name="json_to_yaml",
                description="Convierte JSON a YAML",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "String JSON a convertir",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.json_to_yaml,
            ),
            Tool(
                name="json_diff",
                description="Compara dos JSON y muestra diferencias",
                parameters={
                    "type": "object",
                    "properties": {
                        "json1": {
                            "type": "string",
                            "description": "Primer JSON",
                        },
                        "json2": {
                            "type": "string",
                            "description": "Segundo JSON",
                        },
                    },
                    "required": ["json1", "json2"],
                },
                handler=self.json_diff,
            ),
            Tool(
                name="json_validate",
                description="Valida JSON contra un esquema",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "JSON a validar",
                        },
                        "schema": {
                            "type": "string",
                            "description": "JSON Schema para validación",
                        },
                    },
                    "required": ["data", "schema"],
                },
                handler=self.json_validate,
            ),
            Tool(
                name="json_from_file",
                description="Lee y parsea un archivo JSON/YAML",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Ruta del archivo",
                        },
                        "query": {
                            "type": "string",
                            "description": "JMESPath query opcional",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.json_from_file,
            ),
        ]

    def json_parse(self, data: str, query: Optional[str] = None) -> str:
        """Parsea y opcionalmente consulta JSON."""
        try:
            parsed = json.loads(data)

            if query:
                try:
                    import jmespath

                    result = jmespath.search(query, parsed)
                    return json.dumps(result, indent=2, ensure_ascii=False)
                except ImportError:
                    return "Error: jmespath no instalado. Ejecuta: pip install jmespath"
                except Exception as e:
                    return f"Error en query: {e}"

            return json.dumps(parsed, indent=2, ensure_ascii=False)

        except json.JSONDecodeError as e:
            return f"Error parseando JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def json_format(
        self,
        data: str,
        indent: int = 2,
        sort_keys: bool = False,
    ) -> str:
        """Formatea JSON con indentación."""
        try:
            parsed = json.loads(data)
            return json.dumps(
                parsed,
                indent=indent,
                sort_keys=sort_keys,
                ensure_ascii=False,
            )
        except json.JSONDecodeError as e:
            return f"Error parseando JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def json_minify(self, data: str) -> str:
        """Minimiza JSON."""
        try:
            parsed = json.loads(data)
            return json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
        except json.JSONDecodeError as e:
            return f"Error parseando JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def yaml_to_json(self, data: str) -> str:
        """Convierte YAML a JSON."""
        try:
            import yaml

            parsed = yaml.safe_load(data)
            return json.dumps(parsed, indent=2, ensure_ascii=False)

        except ImportError:
            return "Error: PyYAML no instalado. Ejecuta: pip install pyyaml"
        except yaml.YAMLError as e:
            return f"Error parseando YAML: {e}"
        except Exception as e:
            return f"Error: {e}"

    def json_to_yaml(self, data: str) -> str:
        """Convierte JSON a YAML."""
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
            return "Error: PyYAML no instalado. Ejecuta: pip install pyyaml"
        except json.JSONDecodeError as e:
            return f"Error parseando JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def json_diff(self, json1: str, json2: str) -> str:
        """Compara dos JSON."""
        try:
            obj1 = json.loads(json1)
            obj2 = json.loads(json2)

            differences = self._compare_objects(obj1, obj2, "")

            if not differences:
                return "✅ Los JSON son idénticos"

            result = ["Diferencias encontradas:\n"]
            for diff in differences[:50]:  # Limitar
                result.append(f"  {diff}")

            if len(differences) > 50:
                result.append(f"\n  ... y {len(differences) - 50} diferencias más")

            return "\n".join(result)

        except json.JSONDecodeError as e:
            return f"Error parseando JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def _compare_objects(
        self,
        obj1: Any,
        obj2: Any,
        path: str,
    ) -> list[str]:
        """Compara objetos recursivamente."""
        differences = []

        if type(obj1) != type(obj2):
            differences.append(
                f"{path}: tipo diferente ({type(obj1).__name__} vs {type(obj2).__name__})"
            )
            return differences

        if isinstance(obj1, dict):
            all_keys = set(obj1.keys()) | set(obj2.keys())
            for key in all_keys:
                new_path = f"{path}.{key}" if path else key
                if key not in obj1:
                    differences.append(f"{new_path}: solo en segundo JSON")
                elif key not in obj2:
                    differences.append(f"{new_path}: solo en primer JSON")
                else:
                    differences.extend(self._compare_objects(obj1[key], obj2[key], new_path))

        elif isinstance(obj1, list):
            if len(obj1) != len(obj2):
                differences.append(f"{path}: longitud diferente ({len(obj1)} vs {len(obj2)})")
            for i, (item1, item2) in enumerate(zip(obj1, obj2)):
                differences.extend(self._compare_objects(item1, item2, f"{path}[{i}]"))

        elif obj1 != obj2:
            v1 = repr(obj1)[:50]
            v2 = repr(obj2)[:50]
            differences.append(f"{path}: {v1} != {v2}")

        return differences

    def json_validate(self, data: str, schema: str) -> str:
        """Valida JSON contra un esquema."""
        try:
            import jsonschema

            data_obj = json.loads(data)
            schema_obj = json.loads(schema)

            jsonschema.validate(data_obj, schema_obj)
            return "✅ JSON válido según el esquema"

        except ImportError:
            return "Error: jsonschema no instalado. Ejecuta: pip install jsonschema"
        except jsonschema.ValidationError as e:
            return f"❌ Validación fallida:\n  Ruta: {'.'.join(str(p) for p in e.path)}\n  Error: {e.message}"
        except jsonschema.SchemaError as e:
            return f"Error en el esquema: {e.message}"
        except json.JSONDecodeError as e:
            return f"Error parseando JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def json_from_file(self, file_path: str, query: Optional[str] = None) -> str:
        """Lee y parsea un archivo JSON/YAML."""
        try:
            path = Path(file_path).expanduser()

            if not path.exists():
                return f"Error: Archivo no encontrado: {file_path}"

            content = path.read_text(encoding="utf-8")

            # Detectar formato
            suffix = path.suffix.lower()

            if suffix in (".yaml", ".yml"):
                try:
                    import yaml

                    parsed = yaml.safe_load(content)
                except ImportError:
                    return "Error: PyYAML no instalado"
            else:
                parsed = json.loads(content)

            if query:
                try:
                    import jmespath

                    result = jmespath.search(query, parsed)
                    return json.dumps(result, indent=2, ensure_ascii=False)
                except ImportError:
                    return "Error: jmespath no instalado"
                except Exception as e:
                    return f"Error en query: {e}"

            return json.dumps(parsed, indent=2, ensure_ascii=False)

        except json.JSONDecodeError as e:
            return f"Error parseando JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
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
            return f"Acción no reconocida: {action}"
