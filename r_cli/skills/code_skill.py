"""
Skill de generación y análisis de código para R CLI.

Funcionalidades:
- Generar código desde descripción
- Analizar código existente
- Refactorizar
- Explicar código
- Ejecutar scripts Python
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class CodeSkill(Skill):
    """Skill para generación y análisis de código."""

    name = "code"
    description = "Genera, analiza y ejecuta código (Python, JavaScript, etc.)"

    # Lenguajes soportados con sus extensiones
    LANGUAGES = {
        "python": {"ext": ".py", "cmd": "python3", "comment": "#"},
        "javascript": {"ext": ".js", "cmd": "node", "comment": "//"},
        "typescript": {"ext": ".ts", "cmd": "npx ts-node", "comment": "//"},
        "bash": {"ext": ".sh", "cmd": "bash", "comment": "#"},
        "sql": {"ext": ".sql", "cmd": None, "comment": "--"},
    }

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="write_code",
                description="Escribe código a un archivo",
                parameters={
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "El código a escribir",
                        },
                        "filename": {
                            "type": "string",
                            "description": "Nombre del archivo (ej: script.py)",
                        },
                        "language": {
                            "type": "string",
                            "enum": ["python", "javascript", "typescript", "bash", "sql"],
                            "description": "Lenguaje de programación",
                        },
                    },
                    "required": ["code", "filename"],
                },
                handler=self.write_code,
            ),
            Tool(
                name="run_python",
                description="Ejecuta código Python y retorna el resultado",
                parameters={
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Código Python a ejecutar",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout en segundos (default: 30)",
                        },
                    },
                    "required": ["code"],
                },
                handler=self.run_python,
            ),
            Tool(
                name="analyze_code",
                description="Analiza código y proporciona información sobre él",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Ruta al archivo de código",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.analyze_code,
            ),
            Tool(
                name="run_script",
                description="Ejecuta un script existente",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Ruta al script a ejecutar",
                        },
                        "args": {
                            "type": "string",
                            "description": "Argumentos para el script",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.run_script,
            ),
        ]

    def write_code(
        self,
        code: str,
        filename: str,
        language: Optional[str] = None,
    ) -> str:
        """Escribe código a un archivo."""
        try:
            # Determinar lenguaje por extensión si no se especifica
            if not language:
                ext = Path(filename).suffix.lower()
                for lang, info in self.LANGUAGES.items():
                    if info["ext"] == ext:
                        language = lang
                        break

            # Ruta de salida
            out_path = Path(self.output_dir) / filename
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Escribir archivo
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(code)

            # Hacer ejecutable si es bash
            if language == "bash":
                os.chmod(out_path, 0o755)

            lines = len(code.split("\n"))
            return f"✅ Código guardado: {out_path} ({lines} líneas, {language or 'detectado'})"

        except Exception as e:
            return f"Error escribiendo código: {e}"

    def run_python(self, code: str, timeout: int = 30) -> str:
        """Ejecuta código Python en un entorno aislado."""
        try:
            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                temp_path = f.name

            try:
                # Ejecutar
                result = subprocess.run(
                    ["python3", temp_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=self.output_dir,
                )

                output = []

                if result.stdout:
                    output.append("📤 Output:")
                    output.append(result.stdout)

                if result.stderr:
                    output.append("⚠️ Stderr:")
                    output.append(result.stderr)

                if result.returncode != 0:
                    output.append(f"\n❌ Exit code: {result.returncode}")
                else:
                    output.append("\n✅ Ejecución exitosa")

                return "\n".join(output) if output else "✅ Ejecutado (sin output)"

            finally:
                # Limpiar archivo temporal
                os.unlink(temp_path)

        except subprocess.TimeoutExpired:
            return f"⏰ Timeout: El script excedió {timeout} segundos"
        except Exception as e:
            return f"Error ejecutando Python: {e}"

    def analyze_code(self, file_path: str) -> str:
        """Analiza un archivo de código."""
        try:
            path = Path(file_path)

            if not path.exists():
                return f"Error: Archivo no encontrado: {file_path}"

            # Leer contenido
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                lines = content.split("\n")

            # Detectar lenguaje
            ext = path.suffix.lower()
            language = None
            for lang, info in self.LANGUAGES.items():
                if info["ext"] == ext:
                    language = lang
                    break

            # Análisis básico
            analysis = [
                f"📊 Análisis de: {path.name}",
                f"",
                f"Lenguaje: {language or 'Desconocido'}",
                f"Líneas totales: {len(lines)}",
                f"Líneas de código: {len([l for l in lines if l.strip() and not l.strip().startswith('#')])}",
                f"Líneas vacías: {len([l for l in lines if not l.strip()])}",
                f"Tamaño: {len(content)} bytes",
            ]

            # Análisis específico por lenguaje
            if language == "python":
                analysis.extend(self._analyze_python(content, lines))
            elif language in ["javascript", "typescript"]:
                analysis.extend(self._analyze_js(content, lines))

            return "\n".join(analysis)

        except Exception as e:
            return f"Error analizando código: {e}"

    def _analyze_python(self, content: str, lines: list) -> list:
        """Análisis específico de Python."""
        analysis = ["\n📦 Estructura Python:"]

        # Imports
        imports = [l for l in lines if l.strip().startswith(("import ", "from "))]
        if imports:
            analysis.append(f"  Imports: {len(imports)}")

        # Funciones
        functions = [l for l in lines if l.strip().startswith("def ")]
        if functions:
            analysis.append(f"  Funciones: {len(functions)}")
            for f in functions[:5]:
                name = f.strip().split("(")[0].replace("def ", "")
                analysis.append(f"    • {name}()")

        # Clases
        classes = [l for l in lines if l.strip().startswith("class ")]
        if classes:
            analysis.append(f"  Clases: {len(classes)}")
            for c in classes[:5]:
                name = c.strip().split("(")[0].split(":")[0].replace("class ", "")
                analysis.append(f"    • {name}")

        # Comentarios
        comments = [l for l in lines if l.strip().startswith("#")]
        analysis.append(f"  Comentarios: {len(comments)}")

        # Docstrings (aproximado)
        docstrings = content.count('"""') + content.count("'''")
        if docstrings:
            analysis.append(f"  Docstrings: ~{docstrings // 2}")

        return analysis

    def _analyze_js(self, content: str, lines: list) -> list:
        """Análisis específico de JavaScript/TypeScript."""
        analysis = ["\n📦 Estructura JS/TS:"]

        # Imports
        imports = [l for l in lines if "import " in l or "require(" in l]
        if imports:
            analysis.append(f"  Imports: {len(imports)}")

        # Funciones
        functions = [
            l
            for l in lines
            if "function " in l or "=>" in l or l.strip().startswith("const ")
        ]
        analysis.append(f"  Declaraciones: ~{len(functions)}")

        # Exports
        exports = [l for l in lines if "export " in l]
        if exports:
            analysis.append(f"  Exports: {len(exports)}")

        return analysis

    def run_script(self, file_path: str, args: Optional[str] = None) -> str:
        """Ejecuta un script existente."""
        try:
            path = Path(file_path)

            if not path.exists():
                return f"Error: Script no encontrado: {file_path}"

            # Detectar lenguaje
            ext = path.suffix.lower()
            language = None
            cmd = None

            for lang, info in self.LANGUAGES.items():
                if info["ext"] == ext:
                    language = lang
                    cmd = info["cmd"]
                    break

            if not cmd:
                return f"Error: No sé cómo ejecutar archivos {ext}"

            # Construir comando
            command = cmd.split() + [str(path)]
            if args:
                command.extend(args.split())

            # Ejecutar
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=path.parent,
            )

            output = []

            if result.stdout:
                output.append("📤 Output:")
                output.append(result.stdout[:2000])  # Limitar output

            if result.stderr:
                output.append("⚠️ Stderr:")
                output.append(result.stderr[:1000])

            if result.returncode != 0:
                output.append(f"\n❌ Exit code: {result.returncode}")
            else:
                output.append("\n✅ Ejecución exitosa")

            return "\n".join(output) if output else "✅ Ejecutado (sin output)"

        except subprocess.TimeoutExpired:
            return "⏰ Timeout: El script excedió 60 segundos"
        except Exception as e:
            return f"Error ejecutando script: {e}"

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        action = kwargs.get("action", "write")

        if action == "write":
            return self.write_code(
                code=kwargs.get("code", ""),
                filename=kwargs.get("filename", "script.py"),
                language=kwargs.get("language"),
            )
        elif action == "run":
            return self.run_python(kwargs.get("code", ""))
        elif action == "analyze":
            return self.analyze_code(kwargs.get("file_path", ""))
        else:
            return f"Acción no reconocida: {action}"
