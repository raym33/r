"""
LaTeX Skill for R CLI.

Generate professional LaTeX documents and compile them to PDF.
Ideal for:
- Academic documents
- Scientific papers
- Technical reports
- Mathematical formulas
- Professional CVs
"""

import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class LaTeXSkill(Skill):
    """Skill for generating and compiling LaTeX documents."""

    name = "latex"
    description = "Generate and compile LaTeX documents to professional PDF"

    # Predefined LaTeX templates
    TEMPLATES = {
        "article": r"""
\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[spanish,english]{babel}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{geometry}
\geometry{margin=2.5cm}

\title{{{title}}}
\author{{{author}}}
\date{{{date}}}

\begin{document}
\maketitle

{{content}}

\end{document}
""",
        "report": r"""
\documentclass[11pt,a4paper]{report}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{geometry}
\usepackage{fancyhdr}
\geometry{margin=2.5cm}

\pagestyle{fancy}
\fancyhf{}
\rhead{{{title}}}
\lhead{{{author}}}
\cfoot{\thepage}

\title{{{title}}}
\author{{{author}}}
\date{{{date}}}

\begin{document}
\maketitle
\tableofcontents
\newpage

{{content}}

\end{document}
""",
        "minimal": r"""
\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage{amsmath}

\begin{document}

{{content}}

\end{document}
""",
        "academic": r"""
\documentclass[12pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb,amsthm}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{geometry}
\usepackage{setspace}
\usepackage{natbib}
\geometry{margin=2.5cm}
\onehalfspacing

\theoremstyle{definition}
\newtheorem{definition}{Definition}
\newtheorem{theorem}{Theorem}
\newtheorem{lemma}{Lemma}

\title{{{title}}}
\author{{{author}}}
\date{{{date}}}

\begin{document}
\maketitle
\begin{abstract}
{{abstract}}
\end{abstract}

{{content}}

\end{document}
""",
        "cv": r"""
\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{geometry}
\usepackage{hyperref}
\usepackage{titlesec}
\usepackage{enumitem}
\geometry{margin=2cm}

\titleformat{\section}{\large\bfseries}{}{0em}{}[\titlerule]
\titlespacing{\section}{0pt}{10pt}{5pt}

\pagestyle{empty}

\begin{document}

\begin{center}
{\LARGE\bfseries {{author}}}\\[5pt]
{{contact}}
\end{center}

{{content}}

\end{document}
""",
        "letter": r"""
\documentclass[11pt,a4paper]{letter}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{geometry}
\geometry{margin=2.5cm}

\signature{{{author}}}
\address{{{from_address}}}

\begin{document}
\begin{letter}{{{to_address}}}

\opening{{{opening}}}

{{content}}

\closing{{{closing}}}

\end{letter}
\end{document}
""",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._check_latex_installed()

    def _check_latex_installed(self) -> bool:
        """Check if LaTeX is installed."""
        return shutil.which("pdflatex") is not None

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="compile_latex",
                description="Compile LaTeX code to PDF",
                parameters={
                    "type": "object",
                    "properties": {
                        "latex_code": {
                            "type": "string",
                            "description": "Complete LaTeX code to compile",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path where to save the PDF (optional)",
                        },
                        "filename": {
                            "type": "string",
                            "description": "Filename without extension",
                        },
                    },
                    "required": ["latex_code"],
                },
                handler=self.compile_latex,
            ),
            Tool(
                name="create_document",
                description="Create a LaTeX document from content using a template",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Document content (can be plain text or LaTeX)",
                        },
                        "title": {
                            "type": "string",
                            "description": "Document title",
                        },
                        "author": {
                            "type": "string",
                            "description": "Document author",
                        },
                        "template": {
                            "type": "string",
                            "enum": ["article", "report", "minimal", "academic", "cv", "letter"],
                            "description": "Template to use (default: article)",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path where to save the PDF",
                        },
                    },
                    "required": ["content"],
                },
                handler=self.create_document,
            ),
            Tool(
                name="markdown_to_latex",
                description="Convert Markdown to LaTeX",
                parameters={
                    "type": "object",
                    "properties": {
                        "markdown": {
                            "type": "string",
                            "description": "Markdown text to convert",
                        },
                    },
                    "required": ["markdown"],
                },
                handler=self.markdown_to_latex,
            ),
            Tool(
                name="list_latex_templates",
                description="List available LaTeX templates",
                parameters={"type": "object", "properties": {}},
                handler=self.list_templates,
            ),
            Tool(
                name="render_equation",
                description="Render a mathematical equation to PDF",
                parameters={
                    "type": "object",
                    "properties": {
                        "equation": {
                            "type": "string",
                            "description": "Equation in LaTeX format (without $)",
                        },
                        "display": {
                            "type": "boolean",
                            "description": "Whether to use display mode (centered, larger)",
                        },
                    },
                    "required": ["equation"],
                },
                handler=self.render_equation,
            ),
        ]

    def compile_latex(
        self,
        latex_code: str,
        output_path: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> str:
        """Compile LaTeX code to PDF."""
        if not self._check_latex_installed():
            return "Error: pdflatex is not installed. Install TeX Live or MiKTeX."

        try:
            # Create temporary directory
            with tempfile.TemporaryDirectory() as tmpdir:
                # Write .tex file
                tex_file = Path(tmpdir) / "document.tex"
                with open(tex_file, "w", encoding="utf-8") as f:
                    f.write(latex_code)

                # Compile (2 times for references)
                for _ in range(2):
                    result = subprocess.run(
                        [
                            "pdflatex",
                            "-interaction=nonstopmode",
                            "-output-directory",
                            tmpdir,
                            str(tex_file),
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )

                # Check if PDF was generated
                pdf_temp = Path(tmpdir) / "document.pdf"
                if not pdf_temp.exists():
                    # Extract errors from log
                    log_file = Path(tmpdir) / "document.log"
                    error_msg = "LaTeX compilation error"
                    if log_file.exists():
                        log_content = log_file.read_text()
                        # Find error lines
                        errors = [l for l in log_content.split("\n") if l.startswith("!")]
                        if errors:
                            error_msg = "\n".join(errors[:5])
                    return f"Error compiling LaTeX:\n{error_msg}"

                # Determine output path
                if output_path:
                    out_path = Path(output_path)
                else:
                    name = filename or f"latex_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    out_path = Path(self.output_dir) / f"{name}.pdf"

                # Create directory if it doesn't exist
                out_path.parent.mkdir(parents=True, exist_ok=True)

                # Copy PDF to destination
                shutil.copy(pdf_temp, out_path)

                return f"PDF compiled successfully: {out_path}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout compiling LaTeX (>60s)"
        except Exception as e:
            return f"Error compiling LaTeX: {e}"

    def create_document(
        self,
        content: str,
        title: Optional[str] = None,
        author: Optional[str] = None,
        template: str = "article",
        output_path: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Create a document using a template."""
        try:
            # Get template
            if template not in self.TEMPLATES:
                return f"Error: Template not found. Available: {list(self.TEMPLATES.keys())}"

            latex_template = self.TEMPLATES[template]

            # Default values
            replacements = {
                "title": title or "Document",
                "author": author or "",
                "date": datetime.now().strftime("%B %d, %Y"),
                "content": content,
                "abstract": kwargs.get("abstract", ""),
                "contact": kwargs.get("contact", ""),
                "from_address": kwargs.get("from_address", ""),
                "to_address": kwargs.get("to_address", ""),
                "opening": kwargs.get("opening", "Dear Sir/Madam,"),
                "closing": kwargs.get("closing", "Sincerely,"),
            }

            # Replace placeholders
            latex_code = latex_template
            for key, value in replacements.items():
                latex_code = latex_code.replace("{{" + key + "}}", value)

            # Compile
            filename = title.replace(" ", "_")[:30] if title else None
            return self.compile_latex(latex_code, output_path, filename)

        except Exception as e:
            return f"Error creating document: {e}"

    def markdown_to_latex(self, markdown: str) -> str:
        """Convert basic Markdown to LaTeX."""
        try:
            latex = markdown

            # Headers
            latex = self._replace_pattern(latex, r"^### (.+)$", r"\\subsubsection{\1}")
            latex = self._replace_pattern(latex, r"^## (.+)$", r"\\subsection{\1}")
            latex = self._replace_pattern(latex, r"^# (.+)$", r"\\section{\1}")

            # Bold and italic
            latex = self._replace_pattern(latex, r"\*\*(.+?)\*\*", r"\\textbf{\1}")
            latex = self._replace_pattern(latex, r"\*(.+?)\*", r"\\textit{\1}")
            latex = self._replace_pattern(latex, r"_(.+?)_", r"\\textit{\1}")

            # Inline code
            latex = self._replace_pattern(latex, r"`(.+?)`", r"\\texttt{\1}")

            # Lists
            lines = latex.split("\n")
            new_lines = []
            in_list = False

            for line in lines:
                if line.strip().startswith("- ") or line.strip().startswith("* "):
                    if not in_list:
                        new_lines.append("\\begin{itemize}")
                        in_list = True
                    item = line.strip()[2:]
                    new_lines.append(f"  \\item {item}")
                else:
                    if in_list:
                        new_lines.append("\\end{itemize}")
                        in_list = False
                    new_lines.append(line)

            if in_list:
                new_lines.append("\\end{itemize}")

            latex = "\n".join(new_lines)

            # Escape special characters that were not processed
            special_chars = ["&", "%", "$", "#", "_"]
            for char in special_chars:
                # Only escape if not already escaped
                latex = latex.replace(f"\\{char}", f"__ESCAPED_{char}__")
                latex = latex.replace(char, f"\\{char}")
                latex = latex.replace(f"__ESCAPED_{char}__", f"\\{char}")

            return f"Conversion completed:\n\n{latex}"

        except Exception as e:
            return f"Error converting Markdown: {e}"

    def _replace_pattern(self, text: str, pattern: str, replacement: str) -> str:
        """Replace regex patterns."""
        import re

        return re.sub(pattern, replacement, text, flags=re.MULTILINE)

    def render_equation(
        self,
        equation: str,
        display: bool = True,
    ) -> str:
        """Render a mathematical equation to PDF."""
        if display:
            content = f"\\[\n{equation}\n\\]"
        else:
            content = f"${equation}$"

        latex_code = f"""
\\documentclass[12pt]{{article}}
\\usepackage{{amsmath,amssymb}}
\\usepackage[margin=1cm]{{geometry}}
\\pagestyle{{empty}}

\\begin{{document}}
\\begin{{center}}
{content}
\\end{{center}}
\\end{{document}}
"""
        return self.compile_latex(latex_code, filename=f"equation_{hash(equation) % 10000}")

    def list_templates(self) -> str:
        """List available templates."""
        result = ["Available LaTeX templates:\n"]

        descriptions = {
            "article": "Standard article - papers, short reports",
            "report": "Report with chapters - long documents, thesis",
            "minimal": "Minimal - content only, no formatting",
            "academic": "Academic - theorems, abstract, bibliography",
            "cv": "Curriculum Vitae - professional format",
            "letter": "Formal letter",
        }

        for name, desc in descriptions.items():
            result.append(f"  - {name}: {desc}")

        result.append("\nUsage: create_document(content, template='academic')")
        return "\n".join(result)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        content = kwargs.get("content", "")
        latex_code = kwargs.get("latex", "")

        if latex_code:
            return self.compile_latex(latex_code, kwargs.get("output"))
        elif content:
            return self.create_document(
                content=content,
                title=kwargs.get("title"),
                author=kwargs.get("author"),
                template=kwargs.get("template", "article"),
                output_path=kwargs.get("output"),
            )
        else:
            return "Error: Content or LaTeX code is required"
