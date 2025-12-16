"""
HTML Skill for R CLI.

HTML utilities:
- Parse and extract data
- Clean HTML
- Convert to text
- Extract links/images
"""

import json
import re
from typing import Optional
from html.parser import HTMLParser
from html import unescape

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class HTMLSkill(Skill):
    """Skill for HTML operations."""

    name = "html"
    description = "HTML: parse, extract, clean, convert to text"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="html_to_text",
                description="Convert HTML to plain text",
                parameters={
                    "type": "object",
                    "properties": {
                        "html": {
                            "type": "string",
                            "description": "HTML content",
                        },
                    },
                    "required": ["html"],
                },
                handler=self.html_to_text,
            ),
            Tool(
                name="html_extract_links",
                description="Extract all links from HTML",
                parameters={
                    "type": "object",
                    "properties": {
                        "html": {
                            "type": "string",
                            "description": "HTML content",
                        },
                    },
                    "required": ["html"],
                },
                handler=self.html_extract_links,
            ),
            Tool(
                name="html_extract_images",
                description="Extract all image URLs from HTML",
                parameters={
                    "type": "object",
                    "properties": {
                        "html": {
                            "type": "string",
                            "description": "HTML content",
                        },
                    },
                    "required": ["html"],
                },
                handler=self.html_extract_images,
            ),
            Tool(
                name="html_extract_meta",
                description="Extract meta tags from HTML",
                parameters={
                    "type": "object",
                    "properties": {
                        "html": {
                            "type": "string",
                            "description": "HTML content",
                        },
                    },
                    "required": ["html"],
                },
                handler=self.html_extract_meta,
            ),
            Tool(
                name="html_clean",
                description="Clean/sanitize HTML (remove scripts, styles, etc.)",
                parameters={
                    "type": "object",
                    "properties": {
                        "html": {
                            "type": "string",
                            "description": "HTML content",
                        },
                        "allowed_tags": {
                            "type": "string",
                            "description": "Comma-separated allowed tags (default: p,a,b,i,u,br,ul,ol,li,h1,h2,h3)",
                        },
                    },
                    "required": ["html"],
                },
                handler=self.html_clean,
            ),
            Tool(
                name="html_extract_tables",
                description="Extract tables from HTML as JSON",
                parameters={
                    "type": "object",
                    "properties": {
                        "html": {
                            "type": "string",
                            "description": "HTML content",
                        },
                    },
                    "required": ["html"],
                },
                handler=self.html_extract_tables,
            ),
            Tool(
                name="html_minify",
                description="Minify HTML (remove whitespace)",
                parameters={
                    "type": "object",
                    "properties": {
                        "html": {
                            "type": "string",
                            "description": "HTML content",
                        },
                    },
                    "required": ["html"],
                },
                handler=self.html_minify,
            ),
            Tool(
                name="html_prettify",
                description="Format/prettify HTML",
                parameters={
                    "type": "object",
                    "properties": {
                        "html": {
                            "type": "string",
                            "description": "HTML content",
                        },
                    },
                    "required": ["html"],
                },
                handler=self.html_prettify,
            ),
        ]

    def _use_bs4(self):
        """Try to use BeautifulSoup if available."""
        try:
            from bs4 import BeautifulSoup
            return BeautifulSoup
        except ImportError:
            return None

    def html_to_text(self, html: str) -> str:
        """Convert HTML to plain text."""
        BeautifulSoup = self._use_bs4()

        if BeautifulSoup:
            soup = BeautifulSoup(html, "html.parser")
            # Remove script and style elements
            for element in soup(["script", "style", "head", "meta", "link"]):
                element.decompose()
            text = soup.get_text(separator="\n", strip=True)
            # Clean up multiple newlines
            text = re.sub(r'\n\s*\n', '\n\n', text)
            return text

        # Fallback: simple regex-based
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def html_extract_links(self, html: str) -> str:
        """Extract all links."""
        BeautifulSoup = self._use_bs4()

        links = []

        if BeautifulSoup:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                links.append({
                    "href": a["href"],
                    "text": a.get_text(strip=True),
                })
        else:
            # Fallback: regex
            for match in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', html, re.IGNORECASE):
                links.append({
                    "href": match.group(1),
                    "text": match.group(2).strip(),
                })

        return json.dumps({"count": len(links), "links": links}, indent=2)

    def html_extract_images(self, html: str) -> str:
        """Extract all image URLs."""
        BeautifulSoup = self._use_bs4()

        images = []

        if BeautifulSoup:
            soup = BeautifulSoup(html, "html.parser")
            for img in soup.find_all("img"):
                images.append({
                    "src": img.get("src", ""),
                    "alt": img.get("alt", ""),
                })
        else:
            # Fallback: regex
            for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE):
                images.append({"src": match.group(1), "alt": ""})

        return json.dumps({"count": len(images), "images": images}, indent=2)

    def html_extract_meta(self, html: str) -> str:
        """Extract meta tags."""
        BeautifulSoup = self._use_bs4()

        meta = {}

        if BeautifulSoup:
            soup = BeautifulSoup(html, "html.parser")

            # Title
            title = soup.find("title")
            if title:
                meta["title"] = title.get_text(strip=True)

            # Meta tags
            for tag in soup.find_all("meta"):
                name = tag.get("name") or tag.get("property", "")
                content = tag.get("content", "")
                if name and content:
                    meta[name] = content

        else:
            # Fallback: regex
            title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
            if title_match:
                meta["title"] = title_match.group(1).strip()

            for match in re.finditer(r'<meta[^>]+(?:name|property)=["\']([^"\']+)["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE):
                meta[match.group(1)] = match.group(2)

        return json.dumps(meta, indent=2)

    def html_clean(
        self,
        html: str,
        allowed_tags: str = "p,a,b,i,u,br,ul,ol,li,h1,h2,h3,h4,h5,h6,strong,em,span,div",
    ) -> str:
        """Clean/sanitize HTML."""
        BeautifulSoup = self._use_bs4()

        allowed = set(t.strip().lower() for t in allowed_tags.split(","))

        if BeautifulSoup:
            soup = BeautifulSoup(html, "html.parser")

            # Remove unwanted tags completely
            for tag in soup(["script", "style", "iframe", "object", "embed"]):
                tag.decompose()

            # Remove tags not in allowed list (keep content)
            for tag in soup.find_all(True):
                if tag.name.lower() not in allowed:
                    tag.unwrap()

            # Remove all attributes except href for links
            for tag in soup.find_all(True):
                attrs = dict(tag.attrs)
                for attr in attrs:
                    if attr != "href":
                        del tag[attr]

            return str(soup)

        # Fallback: aggressive cleaning
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        return text

    def html_extract_tables(self, html: str) -> str:
        """Extract tables as JSON."""
        BeautifulSoup = self._use_bs4()

        if not BeautifulSoup:
            return "Error: BeautifulSoup required. Run: pip install beautifulsoup4"

        soup = BeautifulSoup(html, "html.parser")
        tables = []

        for table in soup.find_all("table"):
            rows = []
            headers = []

            # Get headers
            for th in table.find_all("th"):
                headers.append(th.get_text(strip=True))

            # Get rows
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td"])]
                if cells:
                    if headers:
                        rows.append(dict(zip(headers, cells)))
                    else:
                        rows.append(cells)

            if rows:
                tables.append({
                    "headers": headers if headers else None,
                    "rows": rows,
                })

        return json.dumps({"count": len(tables), "tables": tables}, indent=2)

    def html_minify(self, html: str) -> str:
        """Minify HTML."""
        # Remove comments
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        # Remove whitespace between tags
        html = re.sub(r'>\s+<', '><', html)
        # Remove leading/trailing whitespace
        html = re.sub(r'\s+', ' ', html)
        return html.strip()

    def html_prettify(self, html: str) -> str:
        """Prettify HTML."""
        BeautifulSoup = self._use_bs4()

        if BeautifulSoup:
            soup = BeautifulSoup(html, "html.parser")
            return soup.prettify()

        # Simple fallback
        indent = 0
        result = []
        for match in re.finditer(r'(<[^>]+>)|([^<]+)', html):
            tag = match.group(1)
            text = match.group(2)

            if tag:
                if tag.startswith("</"):
                    indent -= 1
                result.append("  " * indent + tag)
                if not tag.startswith("</") and not tag.endswith("/>") and not tag.startswith("<!"):
                    indent += 1
            elif text and text.strip():
                result.append("  " * indent + text.strip())

        return "\n".join(result)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "to_text")
        if action == "to_text":
            return self.html_to_text(kwargs.get("html", ""))
        return f"Unknown action: {action}"
