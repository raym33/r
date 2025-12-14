"""
PDF Generation Skill for R CLI.

Generate professional PDF documents from:
- Plain text
- Markdown
- Predefined templates
"""

import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


def _find_unicode_font() -> Optional[str]:
    """Find an available Unicode font based on operating system."""
    system = platform.system()

    # Font paths by operating system
    font_paths = []

    if system == "Linux":
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
    elif system == "Darwin":  # macOS
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Georgia.ttf",
        ]
    elif system == "Windows":
        windows_fonts = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
        font_paths = [
            str(windows_fonts / "arial.ttf"),
            str(windows_fonts / "calibri.ttf"),
            str(windows_fonts / "segoeui.ttf"),
            str(windows_fonts / "tahoma.ttf"),
        ]

    # Find first available font
    for font_path in font_paths:
        if os.path.exists(font_path):
            return font_path

    return None


class PDFSkill(Skill):
    """Skill for generating PDF documents."""

    name = "pdf"
    description = "Generate professional PDF documents from text or Markdown"

    # Available templates
    TEMPLATES = {
        "minimal": {
            "font_family": "Helvetica",
            "font_size": 11,
            "margin": 25,
            "header": False,
            "footer": True,
        },
        "business": {
            "font_family": "Helvetica",
            "font_size": 11,
            "margin": 30,
            "header": True,
            "footer": True,
        },
        "academic": {
            "font_family": "Times",
            "font_size": 12,
            "margin": 35,
            "header": True,
            "footer": True,
        },
        "report": {
            "font_family": "Helvetica",
            "font_size": 10,
            "margin": 25,
            "header": True,
            "footer": True,
        },
    }

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="generate_pdf",
                description="Generate a PDF document from text or Markdown",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Document content (text or Markdown)",
                        },
                        "title": {
                            "type": "string",
                            "description": "Document title",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path to save the PDF (optional)",
                        },
                        "template": {
                            "type": "string",
                            "enum": ["minimal", "business", "academic", "report"],
                            "description": "Style template (default: minimal)",
                        },
                        "author": {
                            "type": "string",
                            "description": "Document author",
                        },
                    },
                    "required": ["content"],
                },
                handler=self.generate_pdf,
            ),
            Tool(
                name="markdown_to_pdf",
                description="Convert an existing Markdown file to PDF",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Path to the Markdown file",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output PDF path (optional)",
                        },
                        "template": {
                            "type": "string",
                            "enum": ["minimal", "business", "academic", "report"],
                            "description": "Style template",
                        },
                    },
                    "required": ["input_path"],
                },
                handler=self.markdown_to_pdf,
            ),
            Tool(
                name="list_pdf_templates",
                description="List available PDF templates",
                parameters={"type": "object", "properties": {}},
                handler=self.list_templates,
            ),
        ]

    def generate_pdf(
        self,
        content: str,
        title: Optional[str] = None,
        output_path: Optional[str] = None,
        template: str = "minimal",
        author: Optional[str] = None,
    ) -> str:
        """Generate a PDF from text content."""
        try:
            from fpdf import FPDF
            from fpdf.enums import XPos, YPos

            # Template configuration
            tpl = self.TEMPLATES.get(template, self.TEMPLATES["minimal"])

            # Create PDF
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()

            # Add Unicode font for special character support
            unicode_font = _find_unicode_font()
            if unicode_font and not unicode_font.endswith(".ttc"):
                try:
                    pdf.add_font("Unicode", "", unicode_font, uni=True)
                except Exception:
                    pass  # Use default font if it fails

            # Configure font
            pdf.set_font(tpl["font_family"], size=tpl["font_size"])

            # Title
            if title:
                pdf.set_font(tpl["font_family"], "B", size=tpl["font_size"] + 6)
                pdf.cell(0, 15, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
                pdf.ln(5)
                pdf.set_font(tpl["font_family"], size=tpl["font_size"])

            # Metadata
            if author:
                pdf.set_font(tpl["font_family"], "I", size=tpl["font_size"] - 1)
                pdf.cell(0, 8, f"Author: {author}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
                pdf.cell(
                    0,
                    8,
                    f"Date: {datetime.now().strftime('%Y-%m-%d')}",
                    new_x=XPos.LMARGIN,
                    new_y=YPos.NEXT,
                    align="C",
                )
                pdf.ln(10)
                pdf.set_font(tpl["font_family"], size=tpl["font_size"])

            # Process content (basic Markdown)
            lines = content.split("\n")
            for line in lines:
                line = line.strip()

                if not line:
                    pdf.ln(5)
                    continue

                # Markdown headers
                if line.startswith("# "):
                    pdf.set_font(tpl["font_family"], "B", size=tpl["font_size"] + 4)
                    pdf.ln(5)
                    pdf.multi_cell(0, 8, line[2:])
                    pdf.ln(3)
                    pdf.set_font(tpl["font_family"], size=tpl["font_size"])
                elif line.startswith("## "):
                    pdf.set_font(tpl["font_family"], "B", size=tpl["font_size"] + 2)
                    pdf.ln(3)
                    pdf.multi_cell(0, 7, line[3:])
                    pdf.ln(2)
                    pdf.set_font(tpl["font_family"], size=tpl["font_size"])
                elif line.startswith("### "):
                    pdf.set_font(tpl["font_family"], "B", size=tpl["font_size"])
                    pdf.multi_cell(0, 6, line[4:])
                    pdf.ln(1)
                    pdf.set_font(tpl["font_family"], size=tpl["font_size"])
                elif line.startswith("- ") or line.startswith("* "):
                    # Bullet point with indentation
                    pdf.multi_cell(0, 6, f"  - {line[2:]}")
                elif line.startswith("```"):
                    # Code: change font
                    pdf.set_font("Courier", size=tpl["font_size"] - 1)
                else:
                    # Normal text
                    # Handle basic **bold**
                    if "**" in line:
                        # Simplification: remove ** for now
                        line = line.replace("**", "")
                    pdf.multi_cell(0, 6, line)

            # Footer with page number
            if tpl["footer"]:
                pdf.set_y(-15)
                pdf.set_font(tpl["font_family"], "I", 8)
                pdf.cell(0, 10, f"Page {pdf.page_no()}", align="C")

            # Determine output path
            if output_path:
                out_path = Path(output_path)
            else:
                # Generate name based on title or timestamp
                filename = (
                    title.replace(" ", "_")[:30]
                    if title
                    else f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                out_path = Path(self.output_dir) / f"{filename}.pdf"

            # Create directory if it doesn't exist
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Save
            pdf.output(str(out_path))

            return f"PDF generated successfully: {out_path}"

        except ImportError:
            return "Error: fpdf2 not installed. Run: pip install fpdf2"
        except Exception as e:
            return f"Error generating PDF: {e}"

    def markdown_to_pdf(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        template: str = "minimal",
    ) -> str:
        """Convert Markdown file to PDF."""
        try:
            input_file = Path(input_path)

            if not input_file.exists():
                return f"Error: File not found: {input_path}"

            # Read Markdown
            with open(input_file, encoding="utf-8") as f:
                content = f.read()

            # Extract title from first header if exists
            title = None
            lines = content.split("\n")
            for line in lines:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            # Generate output path
            if not output_path:
                output_path = str(input_file.with_suffix(".pdf"))

            return self.generate_pdf(
                content=content,
                title=title,
                output_path=output_path,
                template=template,
            )

        except Exception as e:
            return f"Error converting Markdown: {e}"

    def list_templates(self) -> str:
        """List available templates."""
        result = ["Available PDF templates:\n"]

        for name, config in self.TEMPLATES.items():
            result.append(f"  - {name}")
            result.append(f"    Font: {config['font_family']}, {config['font_size']}pt")
            result.append(f"    Header: {'Yes' if config['header'] else 'No'}")
            result.append("")

        result.append("Usage: generate_pdf(content, template='business')")
        return "\n".join(result)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        content = kwargs.get("content", "")
        if not content:
            return "Error: Content is required to generate the PDF"

        return self.generate_pdf(
            content=content,
            title=kwargs.get("title"),
            output_path=kwargs.get("output"),
            template=kwargs.get("template", "minimal"),
            author=kwargs.get("author"),
        )
