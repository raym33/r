"""
Sitemap Skill for R CLI.

XML Sitemap utilities:
- Parse sitemaps
- Generate sitemaps
- Validate sitemap format
"""

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class SitemapSkill(Skill):
    """Skill for XML Sitemap operations."""

    name = "sitemap"
    description = "Sitemap: parse and generate XML sitemaps"

    NS = {
        "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "image": "http://www.google.com/schemas/sitemap-image/1.1",
        "video": "http://www.google.com/schemas/sitemap-video/1.1",
        "news": "http://www.google.com/schemas/sitemap-news/0.9",
    }

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="sitemap_parse",
                description="Parse an XML sitemap",
                parameters={
                    "type": "object",
                    "properties": {
                        "url_or_content": {
                            "type": "string",
                            "description": "Sitemap URL or XML content",
                        },
                    },
                    "required": ["url_or_content"],
                },
                handler=self.sitemap_parse,
            ),
            Tool(
                name="sitemap_generate",
                description="Generate XML sitemap",
                parameters={
                    "type": "object",
                    "properties": {
                        "urls": {
                            "type": "array",
                            "description": "List of URLs or URL objects",
                        },
                    },
                    "required": ["urls"],
                },
                handler=self.sitemap_generate,
            ),
            Tool(
                name="sitemap_index",
                description="Generate sitemap index",
                parameters={
                    "type": "object",
                    "properties": {
                        "sitemaps": {
                            "type": "array",
                            "description": "List of sitemap URLs",
                        },
                    },
                    "required": ["sitemaps"],
                },
                handler=self.sitemap_index,
            ),
            Tool(
                name="sitemap_validate",
                description="Validate sitemap format",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Sitemap XML content",
                        },
                    },
                    "required": ["content"],
                },
                handler=self.sitemap_validate,
            ),
            Tool(
                name="sitemap_urls",
                description="Extract URLs from sitemap",
                parameters={
                    "type": "object",
                    "properties": {
                        "url_or_content": {
                            "type": "string",
                            "description": "Sitemap URL or XML content",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max URLs to return",
                        },
                    },
                    "required": ["url_or_content"],
                },
                handler=self.sitemap_urls,
            ),
        ]

    def _fetch_content(self, url_or_content: str) -> tuple[bool, str]:
        """Fetch content from URL or return as-is."""
        if url_or_content.startswith("<?xml") or url_or_content.startswith("<"):
            return True, url_or_content

        try:
            req = urllib.request.Request(
                url_or_content,
                headers={"User-Agent": "R-CLI/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                return True, response.read().decode("utf-8")
        except Exception as e:
            return False, str(e)

    def _get_text(self, elem: ET.Element, tag: str, ns: dict | None = None) -> Optional[str]:
        """Get text from child element."""
        ns = ns or self.NS
        child = elem.find(tag, ns)
        if child is not None and child.text:
            return child.text.strip()
        return None

    def sitemap_parse(self, url_or_content: str) -> str:
        """Parse sitemap."""
        success, content = self._fetch_content(url_or_content)
        if not success:
            return f"Error fetching sitemap: {content}"

        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            return f"XML parse error: {e}"

        # Remove namespace prefix for easier access
        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

        result = {
            "type": "unknown",
            "count": 0,
            "urls": [],
        }

        # Sitemap index
        if tag == "sitemapindex":
            result["type"] = "index"
            for sitemap in root.findall("sm:sitemap", self.NS):
                loc = self._get_text(sitemap, "sm:loc")
                lastmod = self._get_text(sitemap, "sm:lastmod")
                if loc:
                    result["urls"].append({
                        "loc": loc,
                        "lastmod": lastmod,
                    })

        # Regular sitemap
        elif tag == "urlset":
            result["type"] = "urlset"
            for url in root.findall("sm:url", self.NS):
                url_data = {
                    "loc": self._get_text(url, "sm:loc"),
                    "lastmod": self._get_text(url, "sm:lastmod"),
                    "changefreq": self._get_text(url, "sm:changefreq"),
                    "priority": self._get_text(url, "sm:priority"),
                }
                # Clean None values
                url_data = {k: v for k, v in url_data.items() if v is not None}
                if url_data.get("loc"):
                    result["urls"].append(url_data)

        result["count"] = len(result["urls"])

        return json.dumps(result, indent=2)

    def sitemap_generate(self, urls: list) -> str:
        """Generate sitemap XML."""
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]

        for url in urls:
            if isinstance(url, str):
                url = {"loc": url}

            lines.append("  <url>")
            lines.append(f"    <loc>{url.get('loc', '')}</loc>")

            if "lastmod" in url:
                lines.append(f"    <lastmod>{url['lastmod']}</lastmod>")
            else:
                lines.append(f"    <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>")

            if "changefreq" in url:
                lines.append(f"    <changefreq>{url['changefreq']}</changefreq>")

            if "priority" in url:
                lines.append(f"    <priority>{url['priority']}</priority>")

            lines.append("  </url>")

        lines.append("</urlset>")

        return "\n".join(lines)

    def sitemap_index(self, sitemaps: list) -> str:
        """Generate sitemap index."""
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]

        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00")

        for sitemap in sitemaps:
            if isinstance(sitemap, str):
                sitemap = {"loc": sitemap}

            lines.append("  <sitemap>")
            lines.append(f"    <loc>{sitemap.get('loc', '')}</loc>")
            lines.append(f"    <lastmod>{sitemap.get('lastmod', now)}</lastmod>")
            lines.append("  </sitemap>")

        lines.append("</sitemapindex>")

        return "\n".join(lines)

    def sitemap_validate(self, content: str) -> str:
        """Validate sitemap."""
        errors = []
        warnings = []

        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            return json.dumps({
                "valid": False,
                "errors": [f"XML parse error: {e}"],
            }, indent=2)

        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

        if tag not in ["urlset", "sitemapindex"]:
            errors.append(f"Invalid root element: {tag}")

        # Check namespace
        if "sitemaps.org" not in root.tag:
            warnings.append("Missing or invalid sitemap namespace")

        url_count = 0

        if tag == "urlset":
            for url in root.findall("sm:url", self.NS):
                url_count += 1
                loc = self._get_text(url, "sm:loc")
                if not loc:
                    errors.append(f"URL {url_count}: missing <loc> element")
                elif not loc.startswith("http"):
                    warnings.append(f"URL {url_count}: <loc> should be absolute URL")

                priority = self._get_text(url, "sm:priority")
                if priority:
                    try:
                        p = float(priority)
                        if not 0 <= p <= 1:
                            warnings.append(f"URL {url_count}: priority should be 0.0-1.0")
                    except ValueError:
                        errors.append(f"URL {url_count}: invalid priority value")

                changefreq = self._get_text(url, "sm:changefreq")
                valid_freq = ["always", "hourly", "daily", "weekly", "monthly", "yearly", "never"]
                if changefreq and changefreq not in valid_freq:
                    warnings.append(f"URL {url_count}: invalid changefreq")

        if url_count > 50000:
            errors.append(f"Sitemap has {url_count} URLs, maximum is 50,000")

        return json.dumps({
            "valid": len(errors) == 0,
            "type": tag,
            "url_count": url_count,
            "errors": errors,
            "warnings": warnings,
        }, indent=2)

    def sitemap_urls(
        self,
        url_or_content: str,
        limit: int = 100,
    ) -> str:
        """Extract URLs from sitemap."""
        success, content = self._fetch_content(url_or_content)
        if not success:
            return f"Error: {content}"

        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            return f"XML parse error: {e}"

        urls = []

        for url in root.findall("sm:url", self.NS)[:limit]:
            loc = self._get_text(url, "sm:loc")
            if loc:
                urls.append(loc)

        return json.dumps({
            "count": len(urls),
            "urls": urls,
        }, indent=2)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        if "url_or_content" in kwargs:
            return self.sitemap_parse(kwargs["url_or_content"])
        return "Provide sitemap URL or content"
