"""
Skill de generación de PDF para R CLI.

Genera documentos PDF profesionales desde:
- Texto plano
- Markdown
- Templates predefinidos
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class PDFSkill(Skill):
    """Skill para generar documentos PDF."""

    name = "pdf"
    description = "Genera documentos PDF profesionales desde texto o Markdown"

    # Templates disponibles
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
                description="Genera un documento PDF desde texto o Markdown",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Contenido del documento (texto o Markdown)",
                        },
                        "title": {
                            "type": "string",
                            "description": "Título del documento",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Ruta donde guardar el PDF (opcional)",
                        },
                        "template": {
                            "type": "string",
                            "enum": ["minimal", "business", "academic", "report"],
                            "description": "Plantilla de estilo (default: minimal)",
                        },
                        "author": {
                            "type": "string",
                            "description": "Autor del documento",
                        },
                    },
                    "required": ["content"],
                },
                handler=self.generate_pdf,
            ),
            Tool(
                name="markdown_to_pdf",
                description="Convierte un archivo Markdown existente a PDF",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Ruta del archivo Markdown",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Ruta del PDF de salida (opcional)",
                        },
                        "template": {
                            "type": "string",
                            "enum": ["minimal", "business", "academic", "report"],
                            "description": "Plantilla de estilo",
                        },
                    },
                    "required": ["input_path"],
                },
                handler=self.markdown_to_pdf,
            ),
            Tool(
                name="list_pdf_templates",
                description="Lista las plantillas de PDF disponibles",
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
        """Genera un PDF desde contenido de texto."""
        try:
            from fpdf import FPDF

            # Configuración del template
            tpl = self.TEMPLATES.get(template, self.TEMPLATES["minimal"])

            # Crear PDF
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()

            # Agregar fuente Unicode para soporte de caracteres especiales
            # Usar fuente built-in que soporta más caracteres
            pdf.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True) if os.path.exists("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf") else None

            # Configurar fuente
            pdf.set_font(tpl["font_family"], size=tpl["font_size"])

            # Título
            if title:
                pdf.set_font(tpl["font_family"], "B", size=tpl["font_size"] + 6)
                pdf.cell(0, 15, title, ln=True, align="C")
                pdf.ln(5)
                pdf.set_font(tpl["font_family"], size=tpl["font_size"])

            # Metadatos
            if author:
                pdf.set_font(tpl["font_family"], "I", size=tpl["font_size"] - 1)
                pdf.cell(0, 8, f"Autor: {author}", ln=True, align="C")
                pdf.cell(
                    0,
                    8,
                    f"Fecha: {datetime.now().strftime('%d/%m/%Y')}",
                    ln=True,
                    align="C",
                )
                pdf.ln(10)
                pdf.set_font(tpl["font_family"], size=tpl["font_size"])

            # Procesar contenido (Markdown básico)
            lines = content.split("\n")
            for line in lines:
                line = line.strip()

                if not line:
                    pdf.ln(5)
                    continue

                # Headers Markdown
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
                    # Bullet point con indentación
                    pdf.multi_cell(0, 6, f"  - {line[2:]}")
                elif line.startswith("```"):
                    # Código: cambiar fuente
                    pdf.set_font("Courier", size=tpl["font_size"] - 1)
                else:
                    # Texto normal
                    # Manejar **bold** básico
                    if "**" in line:
                        # Simplificación: quitar ** por ahora
                        line = line.replace("**", "")
                    pdf.multi_cell(0, 6, line)

            # Footer con número de página
            if tpl["footer"]:
                pdf.set_y(-15)
                pdf.set_font(tpl["font_family"], "I", 8)
                pdf.cell(0, 10, f"Página {pdf.page_no()}", align="C")

            # Determinar ruta de salida
            if output_path:
                out_path = Path(output_path)
            else:
                # Generar nombre basado en título o timestamp
                filename = (
                    title.replace(" ", "_")[:30] if title else f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                out_path = Path(self.output_dir) / f"{filename}.pdf"

            # Crear directorio si no existe
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Guardar
            pdf.output(str(out_path))

            return f"PDF generado exitosamente: {out_path}"

        except ImportError:
            return "Error: fpdf2 no instalado. Ejecuta: pip install fpdf2"
        except Exception as e:
            return f"Error generando PDF: {e}"

    def markdown_to_pdf(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        template: str = "minimal",
    ) -> str:
        """Convierte archivo Markdown a PDF."""
        try:
            input_file = Path(input_path)

            if not input_file.exists():
                return f"Error: Archivo no encontrado: {input_path}"

            # Leer Markdown
            with open(input_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Extraer título del primer header si existe
            title = None
            lines = content.split("\n")
            for line in lines:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            # Generar output path
            if not output_path:
                output_path = str(input_file.with_suffix(".pdf"))

            return self.generate_pdf(
                content=content,
                title=title,
                output_path=output_path,
                template=template,
            )

        except Exception as e:
            return f"Error convirtiendo Markdown: {e}"

    def list_templates(self) -> str:
        """Lista templates disponibles."""
        result = ["📄 Templates de PDF disponibles:\n"]

        for name, config in self.TEMPLATES.items():
            result.append(f"  • {name}")
            result.append(f"    Fuente: {config['font_family']}, {config['font_size']}pt")
            result.append(f"    Header: {'Sí' if config['header'] else 'No'}")
            result.append("")

        result.append("Uso: generate_pdf(content, template='business')")
        return "\n".join(result)

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        content = kwargs.get("content", "")
        if not content:
            return "Error: Se requiere contenido para generar el PDF"

        return self.generate_pdf(
            content=content,
            title=kwargs.get("title"),
            output_path=kwargs.get("output"),
            template=kwargs.get("template", "minimal"),
            author=kwargs.get("author"),
        )
