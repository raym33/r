"""
Skill de Captura de Pantalla para R CLI.

Permite capturar:
- Pantalla completa
- Ventana activa
- Región seleccionada
"""

import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class ScreenshotSkill(Skill):
    """Skill para capturas de pantalla."""

    name = "screenshot"
    description = "Capturas de pantalla: completa, ventana activa o región"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="take_screenshot",
                description="Captura una imagen de la pantalla",
                parameters={
                    "type": "object",
                    "properties": {
                        "output_path": {
                            "type": "string",
                            "description": "Ruta donde guardar la captura (default: auto-generada)",
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["full", "window", "region"],
                            "description": "Modo de captura: full (pantalla completa), window (ventana activa), region (selección manual)",
                        },
                        "delay": {
                            "type": "integer",
                            "description": "Segundos de espera antes de capturar (default: 0)",
                        },
                    },
                },
                handler=self.take_screenshot,
            ),
            Tool(
                name="list_screenshots",
                description="Lista las capturas de pantalla recientes",
                parameters={
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Número máximo de capturas a listar (default: 10)",
                        },
                    },
                },
                handler=self.list_screenshots,
            ),
        ]

    def _generate_filename(self) -> str:
        """Genera un nombre de archivo con timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"screenshot_{timestamp}.png"

    def _get_screenshot_dir(self) -> Path:
        """Obtiene el directorio para guardar capturas."""
        screenshot_dir = Path(self.output_dir) / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        return screenshot_dir

    def take_screenshot(
        self,
        output_path: Optional[str] = None,
        mode: str = "full",
        delay: int = 0,
    ) -> str:
        """Captura la pantalla."""
        try:
            # Determinar ruta de salida
            if output_path:
                out_path = Path(output_path).expanduser()
            else:
                out_path = self._get_screenshot_dir() / self._generate_filename()

            # Crear directorio padre si no existe
            out_path.parent.mkdir(parents=True, exist_ok=True)

            system = platform.system()

            if system == "Linux":
                return self._screenshot_linux(out_path, mode, delay)
            elif system == "Darwin":
                return self._screenshot_macos(out_path, mode, delay)
            elif system == "Windows":
                return self._screenshot_windows(out_path, mode, delay)
            else:
                return f"Sistema operativo no soportado: {system}"

        except Exception as e:
            return f"Error capturando pantalla: {e}"

    def _screenshot_linux(self, output: Path, mode: str, delay: int) -> str:
        """Captura de pantalla en Linux usando diferentes herramientas."""
        # Intentar con diferentes herramientas en orden de preferencia
        tools = ["gnome-screenshot", "scrot", "import", "spectacle"]

        for tool in tools:
            if self._command_exists(tool):
                return self._run_linux_tool(tool, output, mode, delay)

        return "Error: No se encontró ninguna herramienta de captura.\nInstala una con:\n  sudo apt install gnome-screenshot  # GNOME\n  sudo apt install scrot             # Genérico\n  sudo apt install imagemagick       # ImageMagick"

    def _run_linux_tool(self, tool: str, output: Path, mode: str, delay: int) -> str:
        """Ejecuta herramienta de captura específica en Linux."""
        try:
            if tool == "gnome-screenshot":
                cmd = ["gnome-screenshot", "-f", str(output)]
                if mode == "window":
                    cmd.append("-w")
                elif mode == "region":
                    cmd.append("-a")
                if delay > 0:
                    cmd.extend(["-d", str(delay)])

            elif tool == "scrot":
                cmd = ["scrot"]
                if delay > 0:
                    cmd.extend(["-d", str(delay)])
                if mode == "window":
                    cmd.append("-u")
                elif mode == "region":
                    cmd.append("-s")
                cmd.append(str(output))

            elif tool == "import":
                # ImageMagick
                cmd = ["import"]
                if mode == "full":
                    cmd.extend(["-window", "root"])
                elif mode == "window":
                    # Captura ventana bajo el cursor
                    pass
                # region es el comportamiento por defecto
                cmd.append(str(output))

            elif tool == "spectacle":
                # KDE Spectacle
                cmd = ["spectacle", "-b", "-o", str(output)]
                if mode == "window":
                    cmd.append("-a")
                elif mode == "region":
                    cmd.append("-r")
                if delay > 0:
                    cmd.extend(["-d", str(delay * 1000)])  # Spectacle usa ms

            else:
                return f"Herramienta no soportada: {tool}"

            result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and output.exists():
                size = output.stat().st_size / 1024
                return f"✅ Captura guardada: {output}\n   Tamaño: {size:.1f} KB"
            else:
                return f"Error: {result.stderr or 'Captura cancelada'}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout esperando la captura"
        except Exception as e:
            return f"Error ejecutando {tool}: {e}"

    def _screenshot_macos(self, output: Path, mode: str, delay: int) -> str:
        """Captura de pantalla en macOS usando screencapture."""
        try:
            cmd = ["screencapture"]

            if mode == "window":
                cmd.append("-w")  # Ventana
            elif mode == "region":
                cmd.append("-i")  # Interactivo
            # full es el comportamiento por defecto

            if delay > 0:
                cmd.extend(["-T", str(delay)])

            cmd.append(str(output))

            result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and output.exists():
                size = output.stat().st_size / 1024
                return f"✅ Captura guardada: {output}\n   Tamaño: {size:.1f} KB"
            else:
                return f"Error: {result.stderr or 'Captura cancelada'}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout esperando la captura"
        except Exception as e:
            return f"Error ejecutando screencapture: {e}"

    def _screenshot_windows(self, output: Path, mode: str, delay: int) -> str:
        """Captura de pantalla en Windows usando PowerShell o PIL."""
        try:
            # Intentar con PIL primero (más confiable)
            try:
                import time

                from PIL import ImageGrab

                if delay > 0:
                    time.sleep(delay)

                if mode == "full":
                    screenshot = ImageGrab.grab()
                    screenshot.save(str(output))
                    size = output.stat().st_size / 1024
                    return f"✅ Captura guardada: {output}\n   Tamaño: {size:.1f} KB"
                else:
                    return "Error: PIL solo soporta captura de pantalla completa en Windows"

            except ImportError:
                pass

            # Fallback a PowerShell
            if delay > 0:
                import time

                time.sleep(delay)

            # PowerShell script para captura
            ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Screen]::PrimaryScreen | ForEach-Object {{
    $bitmap = New-Object System.Drawing.Bitmap($_.Bounds.Width, $_.Bounds.Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($_.Bounds.Location, [System.Drawing.Point]::Empty, $_.Bounds.Size)
    $bitmap.Save('{output}')
}}
"""
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0 and output.exists():
                size = output.stat().st_size / 1024
                return f"✅ Captura guardada: {output}\n   Tamaño: {size:.1f} KB"
            else:
                return f"Error: {result.stderr or 'Error capturando pantalla'}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout capturando pantalla"
        except Exception as e:
            return f"Error en Windows: {e}"

    def _command_exists(self, command: str) -> bool:
        """Verifica si un comando existe en el sistema."""
        try:
            subprocess.run(
                ["which", command],
                check=False,
                capture_output=True,
                timeout=5,
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def list_screenshots(self, count: int = 10) -> str:
        """Lista las capturas de pantalla recientes."""
        try:
            screenshot_dir = self._get_screenshot_dir()

            # Buscar archivos de imagen
            patterns = ["*.png", "*.jpg", "*.jpeg"]
            files = []

            for pattern in patterns:
                files.extend(screenshot_dir.glob(pattern))

            if not files:
                return f"No hay capturas en: {screenshot_dir}"

            # Ordenar por fecha de modificación (más reciente primero)
            files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

            result = [f"📸 Capturas de pantalla recientes ({screenshot_dir}):\n"]

            for f in files[:count]:
                stat = f.stat()
                size = stat.st_size / 1024
                date = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                result.append(f"  {f.name:<30} {size:>8.1f} KB  {date}")

            if len(files) > count:
                result.append(f"\n  ... y {len(files) - count} capturas más")

            return "\n".join(result)

        except Exception as e:
            return f"Error listando capturas: {e}"

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        action = kwargs.get("action", "capture")

        if action == "capture":
            return self.take_screenshot(
                output_path=kwargs.get("output"),
                mode=kwargs.get("mode", "full"),
                delay=kwargs.get("delay", 0),
            )
        elif action == "list":
            return self.list_screenshots(kwargs.get("count", 10))
        else:
            return f"Acción no reconocida: {action}"
