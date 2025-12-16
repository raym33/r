"""
Markdown Skill for R CLI.

Markdown manipulation:
- Generate Markdown documents
- Convert to/from HTML
- Extract sections
- Create tables
"""

import re
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class MarkdownSkill(Skill):
    """Skill for Markdown generation and conversion."""

    name = "markdown"
    description = "Markdown: generate documents, convert to HTML, create tables"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="md_to_html",
                description="Convert Markdown to HTML",
                parameters={
                    "type": "object",
                    "properties": {
                        "markdown": {
                            "type": "string",
                            "description": "Markdown content",
                        },
                    },
                    "required": ["markdown"],
                },
                handler=self.md_to_html,
            ),
            Tool(
                name="md_table",
                description="Generate a Markdown table from data",
                parameters={
                    "type": "object",
                    "properties": {
                        "headers": {
                            "type": "string",
                            "description": "Comma-separated column headers",
                        },
                        "rows": {
                            "type": "string",
                            "description": "JSON array of row arrays",
                        },
                        "alignment": {
                            "type": "string",
                            "description": "Column alignments: left, center, right (comma-separated)",
                        },
                    },
                    "required": ["headers", "rows"],
                },
                handler=self.md_table,
            ),
            Tool(
                name="md_toc",
                description="Generate table of contents from Markdown",
                parameters={
                    "type": "object",
                    "properties": {
                        "markdown": {
                            "type": "string",
                            "description": "Markdown content",
                        },
                        "max_depth": {
                            "type": "integer",
                            "description": "Maximum heading depth (default: 3)",
                        },
                    },
                    "required": ["markdown"],
                },
                handler=self.md_toc,
            ),
            Tool(
                name="md_extract_links",
                description="Extract all links from Markdown",
                parameters={
                    "type": "object",
                    "properties": {
                        "markdown": {
                            "type": "string",
                            "description": "Markdown content",
                        },
                    },
                    "required": ["markdown"],
                },
                handler=self.md_extract_links,
            ),
            Tool(
                name="md_extract_code",
                description="Extract code blocks from Markdown",
                parameters={
                    "type": "object",
                    "properties": {
                        "markdown": {
                            "type": "string",
                            "description": "Markdown content",
                        },
                        "language": {
                            "type": "string",
                            "description": "Filter by language (optional)",
                        },
                    },
                    "required": ["markdown"],
                },
                handler=self.md_extract_code,
            ),
            Tool(
                name="md_format",
                description="Format and clean Markdown",
                parameters={
                    "type": "object",
                    "properties": {
                        "markdown": {
                            "type": "string",
                            "description": "Markdown content",
                        },
                    },
                    "required": ["markdown"],
                },
                handler=self.md_format,
            ),
        ]

    def md_to_html(self, markdown: str) -> str:
        """Convert Markdown to HTML."""
        try:
            import markdown as md
            html = md.markdown(markdown, extensions=["tables", "fenced_code"])
            return html
        except ImportError:
            # Basic conversion without library
            html = markdown
            # Headers
            html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
            html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
            html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
            # Bold and italic
            html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
            html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
            # Links
            html = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', html)
            # Code
            html = re.sub(r"`(.+?)`", r"<code>\1</code>", html)
            # Paragraphs
            html = re.sub(r"\n\n", "</p><p>", html)
            return f"<p>{html}</p>"

    def md_table(
        self,
        headers: str,
        rows: str,
        alignment: Optional[str] = None,
    ) -> str:
        """Generate Markdown table."""
        try:
            import json
            header_list = [h.strip() for h in headers.split(",")]
            row_data = json.loads(rows)

            # Alignment
            if alignment:
                aligns = [a.strip().lower() for a in alignment.split(",")]
            else:
                aligns = ["left"] * len(header_list)

            def align_str(a: str) -> str:
                if a == "center":
                    return ":---:"
                elif a == "right":
                    return "---:"
                return "---"

            # Build table
            lines = []
            lines.append("| " + " | ".join(header_list) + " |")
            lines.append("| " + " | ".join(align_str(a) for a in aligns) + " |")

            for row in row_data:
                if isinstance(row, list):
                    lines.append("| " + " | ".join(str(c) for c in row) + " |")
                elif isinstance(row, dict):
                    cells = [str(row.get(h, "")) for h in header_list]
                    lines.append("| " + " | ".join(cells) + " |")

            return "\n".join(lines)

        except Exception as e:
            return f"Error: {e}"

    def md_toc(self, markdown: str, max_depth: int = 3) -> str:
        """Generate table of contents."""
        lines = []
        for match in re.finditer(r"^(#{1,6})\s+(.+)$", markdown, re.MULTILINE):
            level = len(match.group(1))
            if level > max_depth:
                continue
            title = match.group(2)
            slug = re.sub(r"[^\w\s-]", "", title.lower()).replace(" ", "-")
            indent = "  " * (level - 1)
            lines.append(f"{indent}- [{title}](#{slug})")

        return "\n".join(lines) if lines else "No headings found"

    def md_extract_links(self, markdown: str) -> str:
        """Extract links from Markdown."""
        links = []

        # Standard links [text](url)
        for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", markdown):
            links.append({"text": match.group(1), "url": match.group(2)})

        # Reference links
        for match in re.finditer(r"^\[([^\]]+)\]:\s*(\S+)", markdown, re.MULTILINE):
            links.append({"text": match.group(1), "url": match.group(2)})

        import json
        return json.dumps(links, indent=2)

    def md_extract_code(self, markdown: str, language: Optional[str] = None) -> str:
        """Extract code blocks."""
        blocks = []
        pattern = r"```(\w*)\n(.*?)```"

        for match in re.finditer(pattern, markdown, re.DOTALL):
            lang = match.group(1) or "text"
            code = match.group(2).strip()

            if language and lang.lower() != language.lower():
                continue

            blocks.append({"language": lang, "code": code})

        import json
        return json.dumps(blocks, indent=2, ensure_ascii=False)

    def md_format(self, markdown: str) -> str:
        """Format and clean Markdown."""
        lines = markdown.split("\n")
        result = []
        prev_blank = False

        for line in lines:
            line = line.rstrip()

            # Normalize headers (space after #)
            if re.match(r"^#+\S", line):
                line = re.sub(r"^(#+)", r"\1 ", line)

            # Current line is blank
            is_blank = not line.strip()

            # Avoid multiple blank lines
            if is_blank and prev_blank:
                continue

            result.append(line)
            prev_blank = is_blank

        return "\n".join(result).strip()

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "to_html")
        if action == "to_html":
            return self.md_to_html(kwargs.get("markdown", ""))
        elif action == "table":
            return self.md_table(
                kwargs.get("headers", ""),
                kwargs.get("rows", "[]"),
            )
        return f"Unknown action: {action}"
