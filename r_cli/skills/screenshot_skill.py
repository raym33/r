"""
Screenshot Capture Skill for R CLI.

Allows capturing:
- Full screen
- Active window
- Selected region
"""

import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class ScreenshotSkill(Skill):
    """Skill for screen captures."""

    name = "screenshot"
    description = "Screenshots: full screen, active window or region"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="take_screenshot",
                description="Capture an image of the screen",
                parameters={
                    "type": "object",
                    "properties": {
                        "output_path": {
                            "type": "string",
                            "description": "Path to save the capture (default: auto-generated)",
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["full", "window", "region"],
                            "description": "Capture mode: full (full screen), window (active window), region (manual selection)",
                        },
                        "delay": {
                            "type": "integer",
                            "description": "Seconds to wait before capturing (default: 0)",
                        },
                    },
                },
                handler=self.take_screenshot,
            ),
            Tool(
                name="list_screenshots",
                description="List recent screenshots",
                parameters={
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Maximum number of screenshots to list (default: 10)",
                        },
                    },
                },
                handler=self.list_screenshots,
            ),
        ]

    def _generate_filename(self) -> str:
        """Generate a filename with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"screenshot_{timestamp}.png"

    def _get_screenshot_dir(self) -> Path:
        """Get the directory for saving screenshots."""
        screenshot_dir = Path(self.output_dir) / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        return screenshot_dir

    def take_screenshot(
        self,
        output_path: Optional[str] = None,
        mode: str = "full",
        delay: int = 0,
    ) -> str:
        """Capture the screen."""
        try:
            # Determine output path
            if output_path:
                out_path = Path(output_path).expanduser()
            else:
                out_path = self._get_screenshot_dir() / self._generate_filename()

            # Create parent directory if it doesn't exist
            out_path.parent.mkdir(parents=True, exist_ok=True)

            system = platform.system()

            if system == "Linux":
                return self._screenshot_linux(out_path, mode, delay)
            elif system == "Darwin":
                return self._screenshot_macos(out_path, mode, delay)
            elif system == "Windows":
                return self._screenshot_windows(out_path, mode, delay)
            else:
                return f"Unsupported operating system: {system}"

        except Exception as e:
            return f"Error capturing screen: {e}"

    def _screenshot_linux(self, output: Path, mode: str, delay: int) -> str:
        """Screenshot on Linux using different tools."""
        # Try different tools in order of preference
        tools = ["gnome-screenshot", "scrot", "import", "spectacle"]

        for tool in tools:
            if self._command_exists(tool):
                return self._run_linux_tool(tool, output, mode, delay)

        return "Error: No screenshot tool found.\nInstall one with:\n  sudo apt install gnome-screenshot  # GNOME\n  sudo apt install scrot             # Generic\n  sudo apt install imagemagick       # ImageMagick"

    def _run_linux_tool(self, tool: str, output: Path, mode: str, delay: int) -> str:
        """Run specific screenshot tool on Linux."""
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
                    # Capture window under cursor
                    pass
                # region is the default behavior
                cmd.append(str(output))

            elif tool == "spectacle":
                # KDE Spectacle
                cmd = ["spectacle", "-b", "-o", str(output)]
                if mode == "window":
                    cmd.append("-a")
                elif mode == "region":
                    cmd.append("-r")
                if delay > 0:
                    cmd.extend(["-d", str(delay * 1000)])  # Spectacle uses ms

            else:
                return f"Unsupported tool: {tool}"

            result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and output.exists():
                size = output.stat().st_size / 1024
                return f"Screenshot saved: {output}\n   Size: {size:.1f} KB"
            else:
                return f"Error: {result.stderr or 'Capture cancelled'}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout waiting for capture"
        except Exception as e:
            return f"Error running {tool}: {e}"

    def _screenshot_macos(self, output: Path, mode: str, delay: int) -> str:
        """Screenshot on macOS using screencapture."""
        try:
            cmd = ["screencapture"]

            if mode == "window":
                cmd.append("-w")  # Window
            elif mode == "region":
                cmd.append("-i")  # Interactive
            # full is the default behavior

            if delay > 0:
                cmd.extend(["-T", str(delay)])

            cmd.append(str(output))

            result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and output.exists():
                size = output.stat().st_size / 1024
                return f"Screenshot saved: {output}\n   Size: {size:.1f} KB"
            else:
                return f"Error: {result.stderr or 'Capture cancelled'}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout waiting for capture"
        except Exception as e:
            return f"Error running screencapture: {e}"

    def _screenshot_windows(self, output: Path, mode: str, delay: int) -> str:
        """Screenshot on Windows using PowerShell or PIL."""
        try:
            # Try PIL first (more reliable)
            try:
                import time

                from PIL import ImageGrab

                if delay > 0:
                    time.sleep(delay)

                if mode == "full":
                    screenshot = ImageGrab.grab()
                    screenshot.save(str(output))
                    size = output.stat().st_size / 1024
                    return f"Screenshot saved: {output}\n   Size: {size:.1f} KB"
                else:
                    return "Error: PIL only supports full screen capture on Windows"

            except ImportError:
                pass

            # Fallback to PowerShell
            if delay > 0:
                import time

                time.sleep(delay)

            # PowerShell script for capture
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
                return f"Screenshot saved: {output}\n   Size: {size:.1f} KB"
            else:
                return f"Error: {result.stderr or 'Error capturing screen'}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout capturing screen"
        except Exception as e:
            return f"Error on Windows: {e}"

    def _command_exists(self, command: str) -> bool:
        """Check if a command exists on the system."""
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
        """List recent screenshots."""
        try:
            screenshot_dir = self._get_screenshot_dir()

            # Search for image files
            patterns = ["*.png", "*.jpg", "*.jpeg"]
            files = []

            for pattern in patterns:
                files.extend(screenshot_dir.glob(pattern))

            if not files:
                return f"No screenshots in: {screenshot_dir}"

            # Sort by modification date (most recent first)
            files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

            result = [f"Recent screenshots ({screenshot_dir}):\n"]

            for f in files[:count]:
                stat = f.stat()
                size = stat.st_size / 1024
                date = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                result.append(f"  {f.name:<30} {size:>8.1f} KB  {date}")

            if len(files) > count:
                result.append(f"\n  ... and {len(files) - count} more screenshots")

            return "\n".join(result)

        except Exception as e:
            return f"Error listing screenshots: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
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
            return f"Unrecognized action: {action}"
