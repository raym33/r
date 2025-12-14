"""
Clipboard Skill for R CLI.

System clipboard operations:
- Copy text
- Paste text
- Clipboard history
"""

import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class ClipboardSkill(Skill):
    """Skill for system clipboard operations."""

    name = "clipboard"
    description = "System clipboard: copy, paste and manage history"

    def __init__(self, config=None):
        super().__init__(config)
        self._history: list[tuple[datetime, str]] = []
        self._max_history = 20

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="clipboard_copy",
                description="Copy text to system clipboard",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to copy to clipboard",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.copy,
            ),
            Tool(
                name="clipboard_paste",
                description="Get current clipboard content",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.paste,
            ),
            Tool(
                name="clipboard_history",
                description="Show recent clipboard history",
                parameters={
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Number of entries to show (default: 10)",
                        },
                    },
                },
                handler=self.history,
            ),
            Tool(
                name="clipboard_clear",
                description="Clear the clipboard",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.clear,
            ),
            Tool(
                name="clipboard_from_file",
                description="Copy file content to clipboard",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to file to copy",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.copy_from_file,
            ),
            Tool(
                name="clipboard_to_file",
                description="Save clipboard content to a file",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path where to save content",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.paste_to_file,
            ),
        ]

    def _get_clipboard_command(self) -> tuple[list[str], list[str]]:
        """Get clipboard commands for the current OS."""
        system = platform.system()

        if system == "Linux":
            # Try xclip first, then xsel
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
        """Add text to history."""
        self._history.append((datetime.now(), text[:500]))  # Limit size
        if len(self._history) > self._max_history:
            self._history.pop(0)

    def copy(self, text: str) -> str:
        """Copy text to clipboard."""
        try:
            copy_cmd, _ = self._get_clipboard_command()

            if not copy_cmd:
                return "Error: Could not detect clipboard system"

            # Execute copy command
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
                return f"Copied to clipboard: {preview}"
            else:
                return f"Error: {stderr.decode()}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout copying to clipboard"
        except FileNotFoundError:
            return self._suggest_install()
        except Exception as e:
            return f"Error copying to clipboard: {e}"

    def paste(self) -> str:
        """Get clipboard content."""
        try:
            _, paste_cmd = self._get_clipboard_command()

            if not paste_cmd:
                return "Error: Could not detect clipboard system"

            # Execute paste command
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
                    return "Clipboard is empty"

                # Limit output size
                if len(content) > 5000:
                    content = content[:5000] + "\n\n... (content truncated)"

                return f"Clipboard content:\n\n{content}"
            else:
                return f"Error: {result.stderr}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout reading clipboard"
        except FileNotFoundError:
            return self._suggest_install()
        except Exception as e:
            return f"Error reading clipboard: {e}"

    def history(self, count: int = 10) -> str:
        """Show clipboard history."""
        if not self._history:
            return "History is empty (only recorded during this session)"

        result = ["Clipboard history:\n"]
        entries = self._history[-count:]

        for i, (timestamp, text) in enumerate(reversed(entries), 1):
            time_str = timestamp.strftime("%H:%M:%S")
            preview = text[:60].replace("\n", " ")
            if len(text) > 60:
                preview += "..."
            result.append(f"{i}. [{time_str}] {preview}")

        return "\n".join(result)

    def clear(self) -> str:
        """Clear clipboard."""
        try:
            # Copy empty text
            return self.copy("")

        except Exception as e:
            return f"Error clearing clipboard: {e}"

    def copy_from_file(self, file_path: str) -> str:
        """Copy file content to clipboard."""
        try:
            path = Path(file_path).expanduser()

            if not path.exists():
                return f"Error: File not found: {file_path}"

            if not path.is_file():
                return f"Error: Not a file: {file_path}"

            # Check size
            size = path.stat().st_size
            if size > 1_000_000:  # 1MB
                return "Error: File too large for clipboard (>1MB)"

            # Read content
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()

            return self.copy(content)

        except Exception as e:
            return f"Error copying file: {e}"

    def paste_to_file(self, file_path: str) -> str:
        """Save clipboard content to a file."""
        try:
            _, paste_cmd = self._get_clipboard_command()

            if not paste_cmd:
                return "Error: Could not detect clipboard system"

            # Get content
            result = subprocess.run(
                paste_cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return f"Error reading clipboard: {result.stderr}"

            content = result.stdout

            if not content:
                return "Clipboard is empty"

            # Save file
            path = Path(file_path).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            return f"Content saved to: {path}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout reading clipboard"
        except FileNotFoundError:
            return self._suggest_install()
        except Exception as e:
            return f"Error saving file: {e}"

    def _suggest_install(self) -> str:
        """Suggest how to install clipboard command."""
        system = platform.system()

        if system == "Linux":
            return "Error: xclip is not installed. Install with:\n  sudo apt install xclip  # Debian/Ubuntu\n  sudo dnf install xclip  # Fedora\n  sudo pacman -S xclip    # Arch"
        elif system == "Darwin":
            return "Error: pbcopy/pbpaste not found (should be default on macOS)"
        elif system == "Windows":
            return "Error: clip.exe not found (should be default on Windows)"
        else:
            return f"Error: Unsupported operating system: {system}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "paste")

        if action == "copy":
            text = kwargs.get("text", "")
            if not text:
                return "Error: text is required for copy"
            return self.copy(text)
        elif action == "paste":
            return self.paste()
        elif action == "history":
            return self.history(kwargs.get("count", 10))
        elif action == "clear":
            return self.clear()
        else:
            return f"Unrecognized action: {action}"
