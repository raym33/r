"""
Skill de Clipboard para R CLI.

Operaciones con el portapapeles del sistema:
- Copiar texto
- Pegar texto
- Historial de clipboard
"""

import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class ClipboardSkill(Skill):
    """Skill para operaciones con el portapapeles del sistema."""

    name = "clipboard"
    description = "Clipboard del sistema: copiar, pegar y gestionar historial"

    def __init__(self, config=None):
        super().__init__(config)
        self._history: list[tuple[datetime, str]] = []
        self._max_history = 20

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="clipboard_copy",
                description="Copia texto al portapapeles del sistema",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Texto a copiar al portapapeles",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.copy,
            ),
            Tool(
                name="clipboard_paste",
                description="Obtiene el contenido actual del portapapeles",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.paste,
            ),
            Tool(
                name="clipboard_history",
                description="Muestra el historial reciente del portapapeles",
                parameters={
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Número de entradas a mostrar (default: 10)",
                        },
                    },
                },
                handler=self.history,
            ),
            Tool(
                name="clipboard_clear",
                description="Limpia el portapapeles",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.clear,
            ),
            Tool(
                name="clipboard_from_file",
                description="Copia el contenido de un archivo al portapapeles",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Ruta del archivo a copiar",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.copy_from_file,
            ),
            Tool(
                name="clipboard_to_file",
                description="Guarda el contenido del portapapeles en un archivo",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Ruta donde guardar el contenido",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.paste_to_file,
            ),
        ]

    def _get_clipboard_command(self) -> tuple[list[str], list[str]]:
        """Obtiene los comandos de clipboard según el sistema operativo."""
        system = platform.system()

        if system == "Linux":
            # Intentar xclip primero, luego xsel
            return (
                ["xclip", "-selection", "clipboard"],
                ["xclip", "-selection", "clipboard", "-o"],
            )
        elif system == "Darwin":  # macOS
            return (["pbcopy"], ["pbpaste"])
        elif system == "Windows":
            return (["clip"], ["powershell", "-command", "Get-Clipboard"])
        else:
            return ([], [])

    def _add_to_history(self, text: str) -> None:
        """Agrega texto al historial."""
        self._history.append((datetime.now(), text[:500]))  # Limitar tamaño
        if len(self._history) > self._max_history:
            self._history.pop(0)

    def copy(self, text: str) -> str:
        """Copia texto al portapapeles."""
        try:
            copy_cmd, _ = self._get_clipboard_command()

            if not copy_cmd:
                return "Error: No se pudo detectar el sistema de clipboard"

            # Ejecutar comando de copia
            process = subprocess.Popen(
                copy_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _, stderr = process.communicate(input=text.encode("utf-8"), timeout=5)

            if process.returncode == 0:
                self._add_to_history(text)
                preview = text[:50] + "..." if len(text) > 50 else text
                return f"✅ Copiado al portapapeles: {preview}"
            else:
                return f"Error: {stderr.decode()}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout copiando al portapapeles"
        except FileNotFoundError:
            return self._suggest_install()
        except Exception as e:
            return f"Error copiando al portapapeles: {e}"

    def paste(self) -> str:
        """Obtiene el contenido del portapapeles."""
        try:
            _, paste_cmd = self._get_clipboard_command()

            if not paste_cmd:
                return "Error: No se pudo detectar el sistema de clipboard"

            # Ejecutar comando de pegado
            result = subprocess.run(
                paste_cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                content = result.stdout

                if not content:
                    return "El portapapeles está vacío"

                # Limitar tamaño de salida
                if len(content) > 5000:
                    content = content[:5000] + "\n\n... (contenido truncado)"

                return f"Contenido del portapapeles:\n\n{content}"
            else:
                return f"Error: {result.stderr}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout leyendo el portapapeles"
        except FileNotFoundError:
            return self._suggest_install()
        except Exception as e:
            return f"Error leyendo el portapapeles: {e}"

    def history(self, count: int = 10) -> str:
        """Muestra el historial del portapapeles."""
        if not self._history:
            return "El historial está vacío (solo se registra durante esta sesión)"

        result = ["📋 Historial del portapapeles:\n"]
        entries = self._history[-count:]

        for i, (timestamp, text) in enumerate(reversed(entries), 1):
            time_str = timestamp.strftime("%H:%M:%S")
            preview = text[:60].replace("\n", " ")
            if len(text) > 60:
                preview += "..."
            result.append(f"{i}. [{time_str}] {preview}")

        return "\n".join(result)

    def clear(self) -> str:
        """Limpia el portapapeles."""
        try:
            # Copiar texto vacío
            return self.copy("")

        except Exception as e:
            return f"Error limpiando portapapeles: {e}"

    def copy_from_file(self, file_path: str) -> str:
        """Copia el contenido de un archivo al portapapeles."""
        try:
            path = Path(file_path).expanduser()

            if not path.exists():
                return f"Error: Archivo no encontrado: {file_path}"

            if not path.is_file():
                return f"Error: No es un archivo: {file_path}"

            # Verificar tamaño
            size = path.stat().st_size
            if size > 1_000_000:  # 1MB
                return "Error: Archivo demasiado grande para copiar al portapapeles (>1MB)"

            # Leer contenido
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()

            return self.copy(content)

        except Exception as e:
            return f"Error copiando archivo: {e}"

    def paste_to_file(self, file_path: str) -> str:
        """Guarda el contenido del portapapeles en un archivo."""
        try:
            _, paste_cmd = self._get_clipboard_command()

            if not paste_cmd:
                return "Error: No se pudo detectar el sistema de clipboard"

            # Obtener contenido
            result = subprocess.run(
                paste_cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return f"Error leyendo portapapeles: {result.stderr}"

            content = result.stdout

            if not content:
                return "El portapapeles está vacío"

            # Guardar archivo
            path = Path(file_path).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            return f"✅ Contenido guardado en: {path}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout leyendo el portapapeles"
        except FileNotFoundError:
            return self._suggest_install()
        except Exception as e:
            return f"Error guardando archivo: {e}"

    def _suggest_install(self) -> str:
        """Sugiere cómo instalar el comando de clipboard."""
        system = platform.system()

        if system == "Linux":
            return "Error: xclip no está instalado. Instálalo con:\n  sudo apt install xclip  # Debian/Ubuntu\n  sudo dnf install xclip  # Fedora\n  sudo pacman -S xclip    # Arch"
        elif system == "Darwin":
            return "Error: pbcopy/pbpaste no encontrados (deberían estar por defecto en macOS)"
        elif system == "Windows":
            return "Error: clip.exe no encontrado (debería estar por defecto en Windows)"
        else:
            return f"Error: Sistema operativo no soportado: {system}"

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        action = kwargs.get("action", "paste")

        if action == "copy":
            text = kwargs.get("text", "")
            if not text:
                return "Error: Se requiere texto para copiar"
            return self.copy(text)
        elif action == "paste":
            return self.paste()
        elif action == "history":
            return self.history(kwargs.get("count", 10))
        elif action == "clear":
            return self.clear()
        else:
            return f"Acción no reconocida: {action}"
