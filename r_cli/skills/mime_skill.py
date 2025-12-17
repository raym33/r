"""
MIME Skill for R CLI.

MIME type utilities:
- Detect MIME types
- Map extensions
- Content type handling
"""

import json
import mimetypes
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class MIMESkill(Skill):
    """Skill for MIME type operations."""

    name = "mime"
    description = "MIME: detect types, map extensions, content types"

    # Extended MIME types
    EXTRA_TYPES = {
        # Code
        ".ts": "application/typescript",
        ".tsx": "application/typescript",
        ".jsx": "text/jsx",
        ".vue": "text/x-vue",
        ".svelte": "text/x-svelte",
        ".rs": "text/x-rust",
        ".go": "text/x-go",
        ".kt": "text/x-kotlin",
        ".swift": "text/x-swift",
        ".scala": "text/x-scala",
        ".r": "text/x-r",
        ".jl": "text/x-julia",
        ".lua": "text/x-lua",
        ".zig": "text/x-zig",
        ".nim": "text/x-nim",
        ".dart": "application/dart",
        ".elm": "text/x-elm",
        ".ex": "text/x-elixir",
        ".erl": "text/x-erlang",
        ".hs": "text/x-haskell",
        ".clj": "text/x-clojure",
        ".ml": "text/x-ocaml",
        ".fs": "text/x-fsharp",
        # Config
        ".yml": "text/yaml",
        ".yaml": "text/yaml",
        ".toml": "application/toml",
        ".ini": "text/plain",
        ".env": "text/plain",
        ".conf": "text/plain",
        ".cfg": "text/plain",
        # Data
        ".jsonl": "application/x-ndjson",
        ".ndjson": "application/x-ndjson",
        ".parquet": "application/vnd.apache.parquet",
        ".avro": "application/avro",
        ".arrow": "application/vnd.apache.arrow.file",
        ".feather": "application/vnd.apache.arrow.file",
        ".sqlite": "application/x-sqlite3",
        ".db": "application/x-sqlite3",
        # Documents
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".rst": "text/x-rst",
        ".adoc": "text/asciidoc",
        ".org": "text/x-org",
        ".tex": "application/x-tex",
        ".bib": "application/x-bibtex",
        ".ipynb": "application/x-ipynb+json",
        # Media
        ".webp": "image/webp",
        ".avif": "image/avif",
        ".heic": "image/heic",
        ".heif": "image/heif",
        ".opus": "audio/opus",
        ".flac": "audio/flac",
        ".m4a": "audio/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        # Archives
        ".7z": "application/x-7z-compressed",
        ".xz": "application/x-xz",
        ".zst": "application/zstd",
        ".br": "application/x-brotli",
        # Fonts
        ".woff2": "font/woff2",
        ".woff": "font/woff",
        ".ttf": "font/ttf",
        ".otf": "font/otf",
        ".eot": "application/vnd.ms-fontobject",
        # Web
        ".wasm": "application/wasm",
        ".map": "application/json",
        ".mjs": "application/javascript",
        ".cjs": "application/javascript",
    }

    def __init__(self, config=None):
        """Initialize MIME skill."""
        super().__init__(config)
        mimetypes.init()
        for ext, mime in self.EXTRA_TYPES.items():
            mimetypes.add_type(mime, ext)

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="mime_detect",
                description="Detect MIME type from filename or extension",
                parameters={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Filename or path",
                        },
                    },
                    "required": ["filename"],
                },
                handler=self.mime_detect,
            ),
            Tool(
                name="mime_extension",
                description="Get file extension for MIME type",
                parameters={
                    "type": "object",
                    "properties": {
                        "mime_type": {
                            "type": "string",
                            "description": "MIME type",
                        },
                    },
                    "required": ["mime_type"],
                },
                handler=self.mime_extension,
            ),
            Tool(
                name="mime_info",
                description="Get detailed MIME type information",
                parameters={
                    "type": "object",
                    "properties": {
                        "mime_type": {
                            "type": "string",
                            "description": "MIME type",
                        },
                    },
                    "required": ["mime_type"],
                },
                handler=self.mime_info,
            ),
            Tool(
                name="mime_category",
                description="Get files by MIME category",
                parameters={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Category: text, image, audio, video, application",
                        },
                    },
                    "required": ["category"],
                },
                handler=self.mime_category,
            ),
            Tool(
                name="mime_detect_content",
                description="Detect MIME type from file content",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to file",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.mime_detect_content,
            ),
        ]

    def mime_detect(self, filename: str) -> str:
        """Detect MIME type from filename."""
        mime_type, encoding = mimetypes.guess_type(filename)

        # Fallback for unknown extensions
        if not mime_type:
            ext = Path(filename).suffix.lower()
            mime_type = self.EXTRA_TYPES.get(ext, "application/octet-stream")

        return json.dumps(
            {
                "filename": filename,
                "mime_type": mime_type,
                "encoding": encoding,
                "extension": Path(filename).suffix,
            },
            indent=2,
        )

    def mime_extension(self, mime_type: str) -> str:
        """Get extension for MIME type."""
        ext = mimetypes.guess_extension(mime_type)

        # Get all extensions
        all_extensions = mimetypes.guess_all_extensions(mime_type)

        return json.dumps(
            {
                "mime_type": mime_type,
                "extension": ext,
                "all_extensions": all_extensions,
            },
            indent=2,
        )

    def mime_info(self, mime_type: str) -> str:
        """Get MIME type information."""
        parts = mime_type.split("/")

        category = parts[0] if len(parts) > 0 else "unknown"
        subtype = parts[1] if len(parts) > 1 else "unknown"

        # Check for parameters
        params = {}
        if ";" in subtype:
            subtype_parts = subtype.split(";")
            subtype = subtype_parts[0]
            for param in subtype_parts[1:]:
                if "=" in param:
                    k, v = param.strip().split("=", 1)
                    params[k] = v

        # Is it text-based?
        text_based = category == "text" or mime_type in [
            "application/json",
            "application/xml",
            "application/javascript",
            "application/typescript",
            "application/x-yaml",
        ]

        # Is it compressible?
        compressible = text_based or category == "application"

        return json.dumps(
            {
                "mime_type": mime_type,
                "category": category,
                "subtype": subtype,
                "parameters": params,
                "text_based": text_based,
                "compressible": compressible,
                "extensions": mimetypes.guess_all_extensions(mime_type),
            },
            indent=2,
        )

    def mime_category(self, category: str) -> str:
        """Get MIME types by category."""
        category = category.lower()

        types = []
        for mime_type in mimetypes.types_map.values():
            if mime_type.startswith(f"{category}/"):
                types.append(mime_type)

        # Add from extra types
        for ext, mime in self.EXTRA_TYPES.items():
            if mime.startswith(f"{category}/") and mime not in types:
                types.append(mime)

        return json.dumps(
            {
                "category": category,
                "count": len(set(types)),
                "types": sorted(set(types)),
            },
            indent=2,
        )

    def mime_detect_content(self, file_path: str) -> str:
        """Detect MIME type from file content (magic bytes)."""
        path = Path(file_path).expanduser()

        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"}, indent=2)

        # Read first bytes for magic detection
        try:
            with open(path, "rb") as f:
                header = f.read(32)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

        # Magic byte signatures
        signatures = [
            (b"\x89PNG\r\n\x1a\n", "image/png"),
            (b"\xff\xd8\xff", "image/jpeg"),
            (b"GIF87a", "image/gif"),
            (b"GIF89a", "image/gif"),
            (b"RIFF", "audio/wav"),  # Also for webp
            (b"ID3", "audio/mpeg"),
            (b"\xff\xfb", "audio/mpeg"),
            (b"\xff\xfa", "audio/mpeg"),
            (b"OggS", "audio/ogg"),
            (b"fLaC", "audio/flac"),
            (b"\x00\x00\x00\x1cftyp", "video/mp4"),
            (b"\x00\x00\x00\x20ftyp", "video/mp4"),
            (b"\x1aE\xdf\xa3", "video/webm"),
            (b"PK\x03\x04", "application/zip"),
            (b"\x1f\x8b\x08", "application/gzip"),
            (b"BZh", "application/x-bzip2"),
            (b"\xfd7zXZ\x00", "application/x-xz"),
            (b"7z\xbc\xaf'\x1c", "application/x-7z-compressed"),
            (b"%PDF", "application/pdf"),
            (b"{\n", "application/json"),
            (b"[", "application/json"),
            (b"<?xml", "application/xml"),
            (b"<!DOCTYPE html", "text/html"),
            (b"<html", "text/html"),
            (b"SQLite format 3", "application/x-sqlite3"),
        ]

        detected = None
        for sig, mime in signatures:
            if header.startswith(sig):
                detected = mime
                break

        # Fallback to extension
        if not detected:
            detected, _ = mimetypes.guess_type(str(path))

        return json.dumps(
            {
                "file": str(path),
                "mime_type": detected or "application/octet-stream",
                "detected_by": "magic_bytes" if detected else "extension",
                "size": path.stat().st_size,
            },
            indent=2,
        )

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        if "filename" in kwargs:
            return self.mime_detect(kwargs["filename"])
        return "Provide a filename to detect MIME type"
