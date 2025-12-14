"""
Code Skill for R CLI.

Features:
- Generate code from description
- Analyze existing code
- Refactor
- Explain code
- Run Python scripts
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class CodeSkill(Skill):
    """Skill for code generation and analysis."""

    name = "code"
    description = "Generate, analyze and execute code (Python, JavaScript, etc.)"

    # Supported languages with their extensions
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
                description="Write code to a file",
                parameters={
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The code to write",
                        },
                        "filename": {
                            "type": "string",
                            "description": "Filename (e.g.: script.py)",
                        },
                        "language": {
                            "type": "string",
                            "enum": ["python", "javascript", "typescript", "bash", "sql"],
                            "description": "Programming language",
                        },
                    },
                    "required": ["code", "filename"],
                },
                handler=self.write_code,
            ),
            Tool(
                name="run_python",
                description="Execute Python code and return the result",
                parameters={
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python code to execute",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout in seconds (default: 30)",
                        },
                    },
                    "required": ["code"],
                },
                handler=self.run_python,
            ),
            Tool(
                name="analyze_code",
                description="Analyze code and provide information about it",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the code file",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.analyze_code,
            ),
            Tool(
                name="run_script",
                description="Execute an existing script",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the script to execute",
                        },
                        "args": {
                            "type": "string",
                            "description": "Arguments for the script",
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
        """Write code to a file."""
        try:
            # Determine language by extension if not specified
            if not language:
                ext = Path(filename).suffix.lower()
                for lang, info in self.LANGUAGES.items():
                    if info["ext"] == ext:
                        language = lang
                        break

            # Output path
            out_path = Path(self.output_dir) / filename
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(code)

            # Make executable if bash
            if language == "bash":
                os.chmod(out_path, 0o755)

            lines = len(code.split("\n"))
            return f"✅ Code saved: {out_path} ({lines} lines, {language or 'detected'})"

        except Exception as e:
            return f"Error writing code: {e}"

    def run_python(self, code: str, timeout: int = 30) -> str:
        """Execute Python code in an isolated environment."""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                temp_path = f.name

            try:
                # Execute
                result = subprocess.run(
                    ["python3", temp_path],
                    check=False,
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
                    output.append("\n✅ Execution successful")

                return "\n".join(output) if output else "✅ Executed (no output)"

            finally:
                # Clean up temporary file
                os.unlink(temp_path)

        except subprocess.TimeoutExpired:
            return f"⏰ Timeout: Script exceeded {timeout} seconds"
        except Exception as e:
            return f"Error executing Python: {e}"

    def analyze_code(self, file_path: str) -> str:
        """Analyze a code file."""
        try:
            path = Path(file_path)

            if not path.exists():
                return f"Error: File not found: {file_path}"

            # Read content
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()
                lines = content.split("\n")

            # Detect language
            ext = path.suffix.lower()
            language = None
            for lang, info in self.LANGUAGES.items():
                if info["ext"] == ext:
                    language = lang
                    break

            # Basic analysis
            analysis = [
                f"📊 Analysis of: {path.name}",
                "",
                f"Language: {language or 'Unknown'}",
                f"Total lines: {len(lines)}",
                f"Code lines: {len([l for l in lines if l.strip() and not l.strip().startswith('#')])}",
                f"Empty lines: {len([l for l in lines if not l.strip()])}",
                f"Size: {len(content)} bytes",
            ]

            # Language-specific analysis
            if language == "python":
                analysis.extend(self._analyze_python(content, lines))
            elif language in ["javascript", "typescript"]:
                analysis.extend(self._analyze_js(content, lines))

            return "\n".join(analysis)

        except Exception as e:
            return f"Error analyzing code: {e}"

    def _analyze_python(self, content: str, lines: list) -> list:
        """Python-specific analysis."""
        analysis = ["\n📦 Python Structure:"]

        # Imports
        imports = [l for l in lines if l.strip().startswith(("import ", "from "))]
        if imports:
            analysis.append(f"  Imports: {len(imports)}")

        # Functions
        functions = [l for l in lines if l.strip().startswith("def ")]
        if functions:
            analysis.append(f"  Functions: {len(functions)}")
            for f in functions[:5]:
                name = f.strip().split("(")[0].replace("def ", "")
                analysis.append(f"    • {name}()")

        # Classes
        classes = [l for l in lines if l.strip().startswith("class ")]
        if classes:
            analysis.append(f"  Classes: {len(classes)}")
            for c in classes[:5]:
                name = c.strip().split("(")[0].split(":")[0].replace("class ", "")
                analysis.append(f"    • {name}")

        # Comments
        comments = [l for l in lines if l.strip().startswith("#")]
        analysis.append(f"  Comments: {len(comments)}")

        # Docstrings (approximate)
        docstrings = content.count('"""') + content.count("'''")
        if docstrings:
            analysis.append(f"  Docstrings: ~{docstrings // 2}")

        return analysis

    def _analyze_js(self, content: str, lines: list) -> list:
        """JavaScript/TypeScript-specific analysis."""
        analysis = ["\n📦 JS/TS Structure:"]

        # Imports
        imports = [l for l in lines if "import " in l or "require(" in l]
        if imports:
            analysis.append(f"  Imports: {len(imports)}")

        # Functions
        functions = [
            l for l in lines if "function " in l or "=>" in l or l.strip().startswith("const ")
        ]
        analysis.append(f"  Declarations: ~{len(functions)}")

        # Exports
        exports = [l for l in lines if "export " in l]
        if exports:
            analysis.append(f"  Exports: {len(exports)}")

        return analysis

    def run_script(self, file_path: str, args: Optional[str] = None) -> str:
        """Execute an existing script."""
        try:
            path = Path(file_path)

            if not path.exists():
                return f"Error: Script not found: {file_path}"

            # Detect language
            ext = path.suffix.lower()
            language = None
            cmd = None

            for lang, info in self.LANGUAGES.items():
                if info["ext"] == ext:
                    language = lang
                    cmd = info["cmd"]
                    break

            if not cmd:
                return f"Error: I don't know how to run {ext}"

            # Build command
            command = cmd.split() + [str(path)]
            if args:
                command.extend(args.split())

            # Execute
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=path.parent,
            )

            output = []

            if result.stdout:
                output.append("📤 Output:")
                output.append(result.stdout[:2000])  # Limit output

            if result.stderr:
                output.append("⚠️ Stderr:")
                output.append(result.stderr[:1000])

            if result.returncode != 0:
                output.append(f"\n❌ Exit code: {result.returncode}")
            else:
                output.append("\n✅ Execution successful")

            return "\n".join(output) if output else "✅ Executed (no output)"

        except subprocess.TimeoutExpired:
            return "⏰ Timeout: Script exceeded 60 seconds"
        except Exception as e:
            return f"Error executing script: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
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
            return f"Unrecognized action: {action}"
