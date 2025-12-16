"""
PDF Tools Skill for R CLI.

Advanced PDF operations:
- Merge PDFs
- Split PDFs
- Extract pages
- Rotate pages
- Add watermark
- Get info
"""

import json
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class PDFToolsSkill(Skill):
    """Skill for advanced PDF operations."""

    name = "pdftools"
    description = "PDF Tools: merge, split, extract, rotate, watermark"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="pdf_info",
                description="Get PDF file information",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to PDF file",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.pdf_info,
            ),
            Tool(
                name="pdf_merge",
                description="Merge multiple PDFs into one",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_paths": {
                            "type": "string",
                            "description": "Comma-separated list of PDF paths",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output PDF path",
                        },
                    },
                    "required": ["input_paths", "output_path"],
                },
                handler=self.pdf_merge,
            ),
            Tool(
                name="pdf_split",
                description="Split PDF into individual pages",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input PDF path",
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Output directory",
                        },
                    },
                    "required": ["input_path", "output_dir"],
                },
                handler=self.pdf_split,
            ),
            Tool(
                name="pdf_extract",
                description="Extract specific pages from PDF",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input PDF path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output PDF path",
                        },
                        "pages": {
                            "type": "string",
                            "description": "Pages to extract (e.g., '1,3,5-10')",
                        },
                    },
                    "required": ["input_path", "output_path", "pages"],
                },
                handler=self.pdf_extract,
            ),
            Tool(
                name="pdf_rotate",
                description="Rotate PDF pages",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input PDF path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output PDF path",
                        },
                        "angle": {
                            "type": "integer",
                            "description": "Rotation angle: 90, 180, 270",
                        },
                        "pages": {
                            "type": "string",
                            "description": "Pages to rotate (e.g., '1,3' or 'all')",
                        },
                    },
                    "required": ["input_path", "output_path", "angle"],
                },
                handler=self.pdf_rotate,
            ),
            Tool(
                name="pdf_watermark",
                description="Add text watermark to PDF",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input PDF path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output PDF path",
                        },
                        "text": {
                            "type": "string",
                            "description": "Watermark text",
                        },
                    },
                    "required": ["input_path", "output_path", "text"],
                },
                handler=self.pdf_watermark,
            ),
            Tool(
                name="pdf_compress",
                description="Compress PDF to reduce file size",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input PDF path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output PDF path",
                        },
                    },
                    "required": ["input_path", "output_path"],
                },
                handler=self.pdf_compress,
            ),
            Tool(
                name="pdf_to_images",
                description="Convert PDF pages to images",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input PDF path",
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Output directory",
                        },
                        "format": {
                            "type": "string",
                            "description": "Image format: png, jpg (default: png)",
                        },
                    },
                    "required": ["input_path", "output_dir"],
                },
                handler=self.pdf_to_images,
            ),
        ]

    def _check_pypdf(self):
        """Check if PyPDF is available."""
        try:
            import pypdf
            return True, pypdf
        except ImportError:
            try:
                import PyPDF2 as pypdf
                return True, pypdf
            except ImportError:
                return False, None

    def pdf_info(self, file_path: str) -> str:
        """Get PDF information."""
        available, pypdf = self._check_pypdf()
        if not available:
            return "Error: pypdf not installed. Run: pip install pypdf"

        path = Path(file_path).expanduser()
        if not path.exists():
            return f"File not found: {file_path}"

        try:
            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)
                info = reader.metadata

                result = {
                    "file": path.name,
                    "pages": len(reader.pages),
                    "encrypted": reader.is_encrypted,
                }

                if info:
                    result["metadata"] = {
                        "title": info.get("/Title", ""),
                        "author": info.get("/Author", ""),
                        "subject": info.get("/Subject", ""),
                        "creator": info.get("/Creator", ""),
                        "producer": info.get("/Producer", ""),
                    }

                # File size
                result["size"] = f"{path.stat().st_size / 1024:.1f} KB"

                return json.dumps(result, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def pdf_merge(self, input_paths: str, output_path: str) -> str:
        """Merge PDFs."""
        available, pypdf = self._check_pypdf()
        if not available:
            return "Error: pypdf not installed. Run: pip install pypdf"

        try:
            files = [f.strip() for f in input_paths.split(",")]
            merger = pypdf.PdfMerger()

            for f in files:
                path = Path(f).expanduser()
                if not path.exists():
                    return f"File not found: {f}"
                merger.append(str(path))

            output = Path(output_path).expanduser()
            merger.write(str(output))
            merger.close()

            return f"Merged {len(files)} PDFs to {output_path}"

        except Exception as e:
            return f"Error: {e}"

    def pdf_split(self, input_path: str, output_dir: str) -> str:
        """Split PDF into pages."""
        available, pypdf = self._check_pypdf()
        if not available:
            return "Error: pypdf not installed. Run: pip install pypdf"

        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        try:
            out_dir = Path(output_dir).expanduser()
            out_dir.mkdir(parents=True, exist_ok=True)

            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)
                num_pages = len(reader.pages)

                for i, page in enumerate(reader.pages):
                    writer = pypdf.PdfWriter()
                    writer.add_page(page)

                    out_file = out_dir / f"{path.stem}_page_{i+1:03d}.pdf"
                    with open(out_file, "wb") as out:
                        writer.write(out)

            return f"Split into {num_pages} files in {output_dir}"

        except Exception as e:
            return f"Error: {e}"

    def pdf_extract(self, input_path: str, output_path: str, pages: str) -> str:
        """Extract pages from PDF."""
        available, pypdf = self._check_pypdf()
        if not available:
            return "Error: pypdf not installed. Run: pip install pypdf"

        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        try:
            # Parse page specification
            page_nums = set()
            for part in pages.split(","):
                part = part.strip()
                if "-" in part:
                    start, end = map(int, part.split("-"))
                    page_nums.update(range(start, end + 1))
                else:
                    page_nums.add(int(part))

            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)
                writer = pypdf.PdfWriter()

                for page_num in sorted(page_nums):
                    if 1 <= page_num <= len(reader.pages):
                        writer.add_page(reader.pages[page_num - 1])

                output = Path(output_path).expanduser()
                with open(output, "wb") as out:
                    writer.write(out)

            return f"Extracted {len(page_nums)} pages to {output_path}"

        except Exception as e:
            return f"Error: {e}"

    def pdf_rotate(
        self,
        input_path: str,
        output_path: str,
        angle: int,
        pages: str = "all",
    ) -> str:
        """Rotate PDF pages."""
        available, pypdf = self._check_pypdf()
        if not available:
            return "Error: pypdf not installed. Run: pip install pypdf"

        if angle not in [90, 180, 270]:
            return "Angle must be 90, 180, or 270"

        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        try:
            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)
                writer = pypdf.PdfWriter()

                # Parse pages
                if pages.lower() == "all":
                    page_nums = set(range(1, len(reader.pages) + 1))
                else:
                    page_nums = set()
                    for part in pages.split(","):
                        page_nums.add(int(part.strip()))

                for i, page in enumerate(reader.pages):
                    if i + 1 in page_nums:
                        page.rotate(angle)
                    writer.add_page(page)

                output = Path(output_path).expanduser()
                with open(output, "wb") as out:
                    writer.write(out)

            return f"Rotated {len(page_nums)} pages by {angle}°, saved to {output_path}"

        except Exception as e:
            return f"Error: {e}"

    def pdf_watermark(
        self,
        input_path: str,
        output_path: str,
        text: str,
    ) -> str:
        """Add watermark to PDF."""
        available, pypdf = self._check_pypdf()
        if not available:
            return "Error: pypdf not installed. Run: pip install pypdf"

        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            import io
        except ImportError:
            return "Error: reportlab not installed. Run: pip install reportlab"

        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        try:
            # Create watermark PDF
            packet = io.BytesIO()
            c = canvas.Canvas(packet, pagesize=letter)
            c.setFont("Helvetica", 50)
            c.setFillAlpha(0.3)
            c.saveState()
            c.translate(300, 400)
            c.rotate(45)
            c.drawCentredString(0, 0, text)
            c.restoreState()
            c.save()
            packet.seek(0)

            watermark = pypdf.PdfReader(packet)
            watermark_page = watermark.pages[0]

            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)
                writer = pypdf.PdfWriter()

                for page in reader.pages:
                    page.merge_page(watermark_page)
                    writer.add_page(page)

                output = Path(output_path).expanduser()
                with open(output, "wb") as out:
                    writer.write(out)

            return f"Added watermark to {output_path}"

        except Exception as e:
            return f"Error: {e}"

    def pdf_compress(self, input_path: str, output_path: str) -> str:
        """Compress PDF."""
        available, pypdf = self._check_pypdf()
        if not available:
            return "Error: pypdf not installed. Run: pip install pypdf"

        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        try:
            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)
                writer = pypdf.PdfWriter()

                for page in reader.pages:
                    page.compress_content_streams()
                    writer.add_page(page)

                output = Path(output_path).expanduser()
                with open(output, "wb") as out:
                    writer.write(out)

            # Compare sizes
            orig_size = path.stat().st_size
            new_size = output.stat().st_size
            reduction = (1 - new_size / orig_size) * 100

            return json.dumps({
                "original_size": f"{orig_size / 1024:.1f} KB",
                "compressed_size": f"{new_size / 1024:.1f} KB",
                "reduction": f"{reduction:.1f}%",
                "output": output_path,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def pdf_to_images(
        self,
        input_path: str,
        output_dir: str,
        format: str = "png",
    ) -> str:
        """Convert PDF to images."""
        try:
            import pdf2image
        except ImportError:
            return "Error: pdf2image not installed. Run: pip install pdf2image"

        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        try:
            out_dir = Path(output_dir).expanduser()
            out_dir.mkdir(parents=True, exist_ok=True)

            images = pdf2image.convert_from_path(str(path))

            for i, image in enumerate(images):
                out_file = out_dir / f"{path.stem}_page_{i+1:03d}.{format}"
                image.save(str(out_file), format.upper())

            return f"Converted {len(images)} pages to {format.upper()} in {output_dir}"

        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "info")
        if action == "info":
            return self.pdf_info(kwargs.get("file", ""))
        return f"Unknown action: {action}"
