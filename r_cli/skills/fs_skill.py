"""
Filesystem Skill for R CLI.

Safe file operations:
- List directories
- Read files
- Write files
- Search files
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool

logger = logging.getLogger(__name__)


class FilesystemSkill(Skill):
    """Skill for filesystem operations."""

    name = "fs"
    description = "File operations: list, read, write, search"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="list_directory",
                description="List files and folders in a directory",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path (default: current directory)",
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Glob pattern to filter (e.g.: *.pdf, *.py)",
                        },
                    },
                },
                handler=self.list_directory,
            ),
            Tool(
                name="read_file",
                description="Read the content of a text file",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to read",
                        },
                        "max_lines": {
                            "type": "integer",
                            "description": "Maximum lines to read (default: 100)",
                        },
                    },
                    "required": ["path"],
                },
                handler=self.read_file,
            ),
            Tool(
                name="write_file",
                description="Write content to a file",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path where to save the file",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write",
                        },
                        "append": {
                            "type": "boolean",
                            "description": "Whether to append instead of overwrite",
                        },
                    },
                    "required": ["path", "content"],
                },
                handler=self.write_file,
            ),
            Tool(
                name="search_files",
                description="Search files by name or content",
                parameters={
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory to search in",
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Name pattern (e.g.: *.py, report*)",
                        },
                        "content": {
                            "type": "string",
                            "description": "Text to search inside files",
                        },
                    },
                    "required": ["directory"],
                },
                handler=self.search_files,
            ),
            Tool(
                name="file_info",
                description="Get file information (size, date, type)",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path",
                        },
                    },
                    "required": ["path"],
                },
                handler=self.file_info,
            ),
        ]

    def list_directory(self, path: Optional[str] = None, pattern: Optional[str] = None) -> str:
        """List directory contents."""
        try:
            dir_path = Path(path) if path else Path.cwd()

            if not dir_path.exists():
                return f"Error: Directory does not exist: {dir_path}"

            if not dir_path.is_dir():
                return f"Error: Not a directory: {dir_path}"

            # Get files
            if pattern:
                items = list(dir_path.glob(pattern))
            else:
                items = list(dir_path.iterdir())

            # Sort: folders first, then files
            dirs = sorted([i for i in items if i.is_dir()])
            files = sorted([i for i in items if i.is_file()])

            result = [f"Contents of: {dir_path}\n"]

            if dirs:
                result.append("📁 Folders:")
                for d in dirs[:20]:  # Limit to 20
                    result.append(f"  {d.name}/")

            if files:
                result.append("\n📄 Files:")
                for f in files[:30]:  # Limit to 30
                    size = f.stat().st_size
                    size_str = self._format_size(size)
                    result.append(f"  {f.name} ({size_str})")

            if len(dirs) > 20 or len(files) > 30:
                result.append(f"\n... and more ({len(dirs)} folders, {len(files)} files total)")

            return "\n".join(result)

        except PermissionError:
            return f"Error: No permission to access {path}"
        except Exception as e:
            return f"Error listing directory: {e}"

    def read_file(self, path: str, max_lines: int = 100) -> str:
        """Read file content."""
        try:
            file_path = Path(path)

            if not file_path.exists():
                return f"Error: File not found: {path}"

            if not file_path.is_file():
                return f"Error: Not a file: {path}"

            # Check size
            size = file_path.stat().st_size
            if size > 1_000_000:  # 1MB
                return f"Error: File too large ({self._format_size(size)}). Use max_lines to read partially."

            # Read
            with open(file_path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            if len(lines) > max_lines:
                content = "".join(lines[:max_lines])
                return f"{content}\n\n... (showing {max_lines} of {len(lines)} lines)"
            else:
                return "".join(lines)

        except UnicodeDecodeError:
            return "Error: File is not readable text (may be binary)"
        except PermissionError:
            return f"Error: No permission to read {path}"
        except Exception as e:
            return f"Error reading file: {e}"

    def write_file(self, path: str, content: str, append: bool = False) -> str:
        """Write content to a file."""
        try:
            file_path = Path(path)

            # Create parent directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)

            mode = "a" if append else "w"
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(content)

            action = "appended to" if append else "written to"
            return f"✅ Content {action}: {file_path}"

        except PermissionError:
            return f"Error: No permission to write to {path}"
        except Exception as e:
            return f"Error writing file: {e}"

    def search_files(
        self,
        directory: str,
        pattern: Optional[str] = None,
        content: Optional[str] = None,
    ) -> str:
        """Search files by name or content."""
        try:
            dir_path = Path(directory)

            if not dir_path.exists():
                return f"Error: Directory does not exist: {directory}"

            # Search by name pattern
            if pattern:
                matches = list(dir_path.rglob(pattern))[:50]  # Limit results
            else:
                matches = list(dir_path.rglob("*"))[:100]

            # Filter only files
            matches = [m for m in matches if m.is_file()]

            # If content search, filter
            if content:
                content_matches = []
                for match in matches:
                    try:
                        with open(match, encoding="utf-8", errors="ignore") as f:
                            if content.lower() in f.read().lower():
                                content_matches.append(match)
                    except Exception as e:
                        logger.debug(f"Could not search content in {match}: {e}")
                        continue
                matches = content_matches

            if not matches:
                return "No matching files found."

            result = [f"Found {len(matches)} files:\n"]
            for m in matches[:20]:
                rel_path = m.relative_to(dir_path) if dir_path in m.parents else m
                result.append(f"  📄 {rel_path}")

            if len(matches) > 20:
                result.append(f"\n  ... and {len(matches) - 20} more")

            return "\n".join(result)

        except Exception as e:
            return f"Error searching: {e}"

    def file_info(self, path: str) -> str:
        """Get detailed file information."""
        try:
            file_path = Path(path)

            if not file_path.exists():
                return f"Error: Does not exist: {path}"

            stat = file_path.stat()

            info = [
                f"📄 Information for: {file_path.name}",
                "",
                f"Full path: {file_path.absolute()}",
                f"Type: {'Directory' if file_path.is_dir() else 'File'}",
                f"Size: {self._format_size(stat.st_size)}",
                f"Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}",
                f"Created: {datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}",
            ]

            if file_path.is_file():
                info.append(f"Extension: {file_path.suffix or '(no extension)'}")

                # Count lines if text
                try:
                    with open(file_path, encoding="utf-8") as f:
                        lines = sum(1 for _ in f)
                    info.append(f"Lines: {lines}")
                except Exception as e:
                    logger.debug(f"Could not count lines in {file_path}: {e}")

            return "\n".join(info)

        except Exception as e:
            return f"Error getting info: {e}"

    def _format_size(self, size: int) -> str:
        """Format size in bytes to readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "list")

        if action == "list":
            return self.list_directory(kwargs.get("path"))
        elif action == "read":
            return self.read_file(kwargs.get("path", ""))
        elif action == "write":
            return self.write_file(kwargs.get("path", ""), kwargs.get("content", ""))
        elif action == "search":
            return self.search_files(kwargs.get("directory", "."), kwargs.get("pattern"))
        else:
            return f"Unrecognized action: {action}"
