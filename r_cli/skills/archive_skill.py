"""
Archive Skill for R CLI.

Compressed file operations:
- Create ZIP, TAR, TAR.GZ
- Extract files
- List contents
- Add files
"""

import os
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class ArchiveSkill(Skill):
    """Skill for compressed file operations."""

    name = "archive"
    description = "Compressed files: create, extract and list ZIP, TAR, TAR.GZ"

    # Size limit for extraction (100MB)
    MAX_EXTRACT_SIZE = 100 * 1024 * 1024

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="create_archive",
                description="Create a compressed archive (ZIP, TAR, TAR.GZ)",
                parameters={
                    "type": "object",
                    "properties": {
                        "output_path": {
                            "type": "string",
                            "description": "Output file path (extension determines format)",
                        },
                        "source_paths": {
                            "type": "string",
                            "description": "Paths of files/folders to compress (comma-separated)",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["zip", "tar", "tar.gz", "tgz"],
                            "description": "Compression format (default: inferred from extension)",
                        },
                    },
                    "required": ["output_path", "source_paths"],
                },
                handler=self.create_archive,
            ),
            Tool(
                name="extract_archive",
                description="Extract a compressed archive",
                parameters={
                    "type": "object",
                    "properties": {
                        "archive_path": {
                            "type": "string",
                            "description": "Compressed archive path",
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Destination directory (default: current directory)",
                        },
                    },
                    "required": ["archive_path"],
                },
                handler=self.extract_archive,
            ),
            Tool(
                name="list_archive",
                description="List contents of a compressed archive",
                parameters={
                    "type": "object",
                    "properties": {
                        "archive_path": {
                            "type": "string",
                            "description": "Compressed archive path",
                        },
                    },
                    "required": ["archive_path"],
                },
                handler=self.list_archive,
            ),
            Tool(
                name="add_to_archive",
                description="Add files to an existing ZIP",
                parameters={
                    "type": "object",
                    "properties": {
                        "archive_path": {
                            "type": "string",
                            "description": "ZIP archive path",
                        },
                        "source_paths": {
                            "type": "string",
                            "description": "Paths of files to add (comma-separated)",
                        },
                    },
                    "required": ["archive_path", "source_paths"],
                },
                handler=self.add_to_archive,
            ),
            Tool(
                name="archive_info",
                description="Show detailed archive information",
                parameters={
                    "type": "object",
                    "properties": {
                        "archive_path": {
                            "type": "string",
                            "description": "Compressed archive path",
                        },
                    },
                    "required": ["archive_path"],
                },
                handler=self.archive_info,
            ),
        ]

    def _get_format(self, path: Path, format_hint: Optional[str] = None) -> str:
        """Determine format based on extension or hint."""
        if format_hint:
            return format_hint.lower()

        suffix = path.suffix.lower()
        if suffix == ".zip":
            return "zip"
        elif suffix == ".tar":
            return "tar"
        elif suffix in (".gz", ".tgz") or str(path).endswith(".tar.gz"):
            return "tar.gz"
        else:
            return "zip"  # Default

    def _format_size(self, size: int) -> str:
        """Format size in bytes."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def create_archive(
        self,
        output_path: str,
        source_paths: str,
        format: Optional[str] = None,
    ) -> str:
        """Create a compressed archive."""
        try:
            out_path = Path(output_path).expanduser()
            archive_format = self._get_format(out_path, format)

            # Parse source paths
            sources = [Path(p.strip()).expanduser() for p in source_paths.split(",")]

            # Validate existence
            for src in sources:
                if not src.exists():
                    return f"Error: Does not exist: {src}"

            # Create parent directory if it doesn't exist
            out_path.parent.mkdir(parents=True, exist_ok=True)

            if archive_format == "zip":
                return self._create_zip(out_path, sources)
            elif archive_format in ("tar", "tar.gz", "tgz"):
                return self._create_tar(out_path, sources, compress=(archive_format != "tar"))
            else:
                return f"Unsupported format: {archive_format}"

        except Exception as e:
            return f"Error creating archive: {e}"

    def _create_zip(self, output: Path, sources: list[Path]) -> str:
        """Create a ZIP archive."""
        count = 0
        total_size = 0

        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            for src in sources:
                if src.is_file():
                    zf.write(src, src.name)
                    count += 1
                    total_size += src.stat().st_size
                elif src.is_dir():
                    for root, _, files in os.walk(src):
                        for file in files:
                            file_path = Path(root) / file
                            arcname = file_path.relative_to(src.parent)
                            zf.write(file_path, arcname)
                            count += 1
                            total_size += file_path.stat().st_size

        compressed_size = output.stat().st_size
        ratio = (1 - compressed_size / total_size) * 100 if total_size > 0 else 0

        return f"ZIP created: {output}\n   {count} files, {self._format_size(compressed_size)} ({ratio:.1f}% compressed)"

    def _create_tar(self, output: Path, sources: list[Path], compress: bool = True) -> str:
        """Create a TAR/TAR.GZ archive."""
        mode = "w:gz" if compress else "w"
        count = 0
        total_size = 0

        with tarfile.open(output, mode) as tf:
            for src in sources:
                tf.add(src, arcname=src.name)
                if src.is_file():
                    count += 1
                    total_size += src.stat().st_size
                elif src.is_dir():
                    for root, _, files in os.walk(src):
                        count += len(files)
                        for file in files:
                            total_size += (Path(root) / file).stat().st_size

        compressed_size = output.stat().st_size
        ratio = (1 - compressed_size / total_size) * 100 if total_size > 0 else 0

        format_name = "TAR.GZ" if compress else "TAR"
        return f"{format_name} created: {output}\n   {count} files, {self._format_size(compressed_size)} ({ratio:.1f}% compressed)"

    def extract_archive(
        self,
        archive_path: str,
        output_dir: Optional[str] = None,
    ) -> str:
        """Extract a compressed archive."""
        try:
            arc_path = Path(archive_path).expanduser()

            if not arc_path.exists():
                return f"Error: Archive not found: {archive_path}"

            # Determine output directory
            if output_dir:
                out_dir = Path(output_dir).expanduser()
            else:
                out_dir = Path.cwd()

            out_dir.mkdir(parents=True, exist_ok=True)

            archive_format = self._get_format(arc_path)

            if archive_format == "zip":
                return self._extract_zip(arc_path, out_dir)
            elif archive_format in ("tar", "tar.gz", "tgz"):
                return self._extract_tar(arc_path, out_dir)
            else:
                return f"Unsupported format: {archive_format}"

        except Exception as e:
            return f"Error extracting archive: {e}"

    def _extract_zip(self, archive: Path, output_dir: Path) -> str:
        """Extract a ZIP archive."""
        with zipfile.ZipFile(archive, "r") as zf:
            # Verify total size before extracting
            total_size = sum(info.file_size for info in zf.infolist())
            if total_size > self.MAX_EXTRACT_SIZE:
                return f"Error: Archive too large ({self._format_size(total_size)})"

            # Check for path traversal
            for info in zf.infolist():
                target_path = output_dir / info.filename
                if not str(target_path.resolve()).startswith(str(output_dir.resolve())):
                    return "Error: Archive contains dangerous paths (path traversal)"

            zf.extractall(output_dir)
            count = len(zf.namelist())

        return f"Extracted to: {output_dir}\n   {count} files, {self._format_size(total_size)}"

    def _extract_tar(self, archive: Path, output_dir: Path) -> str:
        """Extract a TAR/TAR.GZ archive."""
        # Determine mode
        if str(archive).endswith(".gz") or str(archive).endswith(".tgz"):
            mode = "r:gz"
        else:
            mode = "r"

        with tarfile.open(archive, mode) as tf:
            # Check for path traversal
            for member in tf.getmembers():
                target_path = output_dir / member.name
                if not str(target_path.resolve()).startswith(str(output_dir.resolve())):
                    return "Error: Archive contains dangerous paths (path traversal)"

            # Verify total size
            total_size = sum(m.size for m in tf.getmembers() if m.isfile())
            if total_size > self.MAX_EXTRACT_SIZE:
                return f"Error: Archive too large ({self._format_size(total_size)})"

            tf.extractall(output_dir)
            count = len([m for m in tf.getmembers() if m.isfile()])

        return f"Extracted to: {output_dir}\n   {count} files, {self._format_size(total_size)}"

    def list_archive(self, archive_path: str) -> str:
        """List contents of a compressed archive."""
        try:
            arc_path = Path(archive_path).expanduser()

            if not arc_path.exists():
                return f"Error: Archive not found: {archive_path}"

            archive_format = self._get_format(arc_path)

            if archive_format == "zip":
                return self._list_zip(arc_path)
            elif archive_format in ("tar", "tar.gz", "tgz"):
                return self._list_tar(arc_path)
            else:
                return f"Unsupported format: {archive_format}"

        except Exception as e:
            return f"Error listing archive: {e}"

    def _list_zip(self, archive: Path) -> str:
        """List contents of a ZIP."""
        with zipfile.ZipFile(archive, "r") as zf:
            result = [f"Contents of {archive.name}:\n"]

            for info in sorted(zf.infolist(), key=lambda x: x.filename)[:50]:
                size = self._format_size(info.file_size)
                date = datetime(*info.date_time[:6]).strftime("%Y-%m-%d %H:%M")
                result.append(f"  {info.filename:<40} {size:>10} {date}")

            total = len(zf.namelist())
            if total > 50:
                result.append(f"\n  ... and {total - 50} more files")

            total_size = sum(i.file_size for i in zf.infolist())
            result.append(f"\n  Total: {total} files, {self._format_size(total_size)}")

        return "\n".join(result)

    def _list_tar(self, archive: Path) -> str:
        """List contents of a TAR/TAR.GZ."""
        mode = "r:gz" if str(archive).endswith((".gz", ".tgz")) else "r"

        with tarfile.open(archive, mode) as tf:
            result = [f"Contents of {archive.name}:\n"]

            members = sorted(tf.getmembers(), key=lambda x: x.name)[:50]
            for member in members:
                if member.isfile():
                    size = self._format_size(member.size)
                    date = datetime.fromtimestamp(member.mtime).strftime("%Y-%m-%d %H:%M")
                    result.append(f"  {member.name:<40} {size:>10} {date}")
                elif member.isdir():
                    result.append(f"  {member.name}/")

            all_members = tf.getmembers()
            total = len(all_members)
            if total > 50:
                result.append(f"\n  ... and {total - 50} more files")

            total_size = sum(m.size for m in all_members if m.isfile())
            result.append(f"\n  Total: {total} items, {self._format_size(total_size)}")

        return "\n".join(result)

    def add_to_archive(self, archive_path: str, source_paths: str) -> str:
        """Add files to an existing ZIP."""
        try:
            arc_path = Path(archive_path).expanduser()

            if not arc_path.exists():
                return f"Error: Archive not found: {archive_path}"

            if not str(arc_path).endswith(".zip"):
                return "Error: Can only add to ZIP files"

            # Parse source paths
            sources = [Path(p.strip()).expanduser() for p in source_paths.split(",")]

            count = 0
            with zipfile.ZipFile(arc_path, "a", zipfile.ZIP_DEFLATED) as zf:
                for src in sources:
                    if not src.exists():
                        return f"Error: Does not exist: {src}"

                    if src.is_file():
                        zf.write(src, src.name)
                        count += 1
                    elif src.is_dir():
                        for root, _, files in os.walk(src):
                            for file in files:
                                file_path = Path(root) / file
                                arcname = file_path.relative_to(src.parent)
                                zf.write(file_path, arcname)
                                count += 1

            return f"Added {count} files to: {arc_path}"

        except Exception as e:
            return f"Error adding files: {e}"

    def archive_info(self, archive_path: str) -> str:
        """Show detailed archive information."""
        try:
            arc_path = Path(archive_path).expanduser()

            if not arc_path.exists():
                return f"Error: Archive not found: {archive_path}"

            stat = arc_path.stat()
            info = [
                f"Archive info: {arc_path.name}",
                "",
                f"Path: {arc_path.absolute()}",
                f"Compressed size: {self._format_size(stat.st_size)}",
                f"Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}",
            ]

            archive_format = self._get_format(arc_path)
            info.append(f"Format: {archive_format.upper()}")

            # Format-specific information
            if archive_format == "zip":
                with zipfile.ZipFile(arc_path, "r") as zf:
                    original_size = sum(i.file_size for i in zf.infolist())
                    file_count = len(zf.namelist())
            else:
                mode = "r:gz" if archive_format in ("tar.gz", "tgz") else "r"
                with tarfile.open(arc_path, mode) as tf:
                    members = tf.getmembers()
                    original_size = sum(m.size for m in members if m.isfile())
                    file_count = len([m for m in members if m.isfile()])

            info.append(f"Original size: {self._format_size(original_size)}")
            info.append(f"Files: {file_count}")

            if original_size > 0:
                ratio = (1 - stat.st_size / original_size) * 100
                info.append(f"Compression ratio: {ratio:.1f}%")

            return "\n".join(info)

        except Exception as e:
            return f"Error getting info: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "list")

        if action == "create":
            output = kwargs.get("output", "")
            sources = kwargs.get("sources", "")
            if not output or not sources:
                return "Error: output and sources are required"
            return self.create_archive(output, sources, kwargs.get("format"))

        elif action == "extract":
            archive = kwargs.get("archive", "")
            if not archive:
                return "Error: archive path is required"
            return self.extract_archive(archive, kwargs.get("output"))

        elif action == "list":
            archive = kwargs.get("archive", "")
            if not archive:
                return "Error: archive path is required"
            return self.list_archive(archive)

        elif action == "info":
            archive = kwargs.get("archive", "")
            if not archive:
                return "Error: archive path is required"
            return self.archive_info(archive)

        else:
            return f"Unrecognized action: {action}"
