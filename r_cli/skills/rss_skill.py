"""
RSS Skill for R CLI.

RSS/Atom feed utilities:
- Parse feeds
- Extract items
- Generate feeds
"""

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class RSSSkill(Skill):
    """Skill for RSS/Atom feed operations."""

    name = "rss"
    description = "RSS: parse and generate RSS/Atom feeds"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="rss_parse",
                description="Parse an RSS or Atom feed",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Feed URL or XML content",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.rss_parse,
            ),
            Tool(
                name="rss_items",
                description="Get items from a feed",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Feed URL",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max items to return (default: 10)",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.rss_items,
            ),
            Tool(
                name="rss_generate",
                description="Generate an RSS feed",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Feed title",
                        },
                        "link": {
                            "type": "string",
                            "description": "Feed link",
                        },
                        "description": {
                            "type": "string",
                            "description": "Feed description",
                        },
                        "items": {
                            "type": "array",
                            "description": "Feed items (title, link, description)",
                        },
                    },
                    "required": ["title", "link", "items"],
                },
                handler=self.rss_generate,
            ),
            Tool(
                name="rss_validate",
                description="Validate RSS feed format",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "RSS XML content",
                        },
                    },
                    "required": ["content"],
                },
                handler=self.rss_validate,
            ),
        ]

    def _fetch_feed(self, url: str) -> tuple[bool, str]:
        """Fetch feed content."""
        if url.startswith("<?xml") or url.startswith("<"):
            return True, url

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "R-CLI/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                return True, response.read().decode("utf-8")
        except Exception as e:
            return False, str(e)

    def _parse_rss(self, root: ET.Element) -> dict:
        """Parse RSS 2.0 feed."""
        channel = root.find("channel")
        if channel is None:
            return {}

        feed = {
            "type": "rss",
            "version": root.get("version", "2.0"),
            "title": self._get_text(channel, "title"),
            "link": self._get_text(channel, "link"),
            "description": self._get_text(channel, "description"),
            "language": self._get_text(channel, "language"),
            "lastBuildDate": self._get_text(channel, "lastBuildDate"),
            "items": [],
        }

        for item in channel.findall("item"):
            feed["items"].append({
                "title": self._get_text(item, "title"),
                "link": self._get_text(item, "link"),
                "description": self._get_text(item, "description"),
                "pubDate": self._get_text(item, "pubDate"),
                "guid": self._get_text(item, "guid"),
                "author": self._get_text(item, "author"),
            })

        return feed

    def _parse_atom(self, root: ET.Element) -> dict:
        """Parse Atom feed."""
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        feed = {
            "type": "atom",
            "title": self._get_text(root, "atom:title", ns),
            "link": root.find("atom:link[@rel='alternate']", ns),
            "updated": self._get_text(root, "atom:updated", ns),
            "id": self._get_text(root, "atom:id", ns),
            "items": [],
        }

        if feed["link"] is not None:
            feed["link"] = feed["link"].get("href", "")
        else:
            link_elem = root.find("atom:link", ns)
            feed["link"] = link_elem.get("href", "") if link_elem is not None else ""

        for entry in root.findall("atom:entry", ns):
            link_elem = entry.find("atom:link[@rel='alternate']", ns)
            if link_elem is None:
                link_elem = entry.find("atom:link", ns)

            feed["items"].append({
                "title": self._get_text(entry, "atom:title", ns),
                "link": link_elem.get("href", "") if link_elem is not None else "",
                "description": self._get_text(entry, "atom:summary", ns) or self._get_text(entry, "atom:content", ns),
                "pubDate": self._get_text(entry, "atom:published", ns) or self._get_text(entry, "atom:updated", ns),
                "guid": self._get_text(entry, "atom:id", ns),
                "author": self._get_text(entry, "atom:author/atom:name", ns),
            })

        return feed

    def _get_text(self, elem: ET.Element, path: str, ns: dict | None = None) -> Optional[str]:
        """Get text content from element."""
        child = elem.find(path, ns) if ns else elem.find(path)
        if child is not None and child.text:
            return child.text.strip()
        return None

    def rss_parse(self, url: str) -> str:
        """Parse RSS/Atom feed."""
        success, content = self._fetch_feed(url)
        if not success:
            return f"Error fetching feed: {content}"

        try:
            root = ET.fromstring(content)

            # Detect feed type
            if root.tag == "rss":
                feed = self._parse_rss(root)
            elif root.tag.endswith("feed"):
                feed = self._parse_atom(root)
            else:
                return f"Unknown feed format: {root.tag}"

            # Clean up None values
            feed = {k: v for k, v in feed.items() if v is not None}
            feed["item_count"] = len(feed.get("items", []))

            return json.dumps(feed, indent=2)

        except ET.ParseError as e:
            return f"XML parse error: {e}"
        except Exception as e:
            return f"Error: {e}"

    def rss_items(self, url: str, limit: int = 10) -> str:
        """Get feed items."""
        success, content = self._fetch_feed(url)
        if not success:
            return f"Error: {content}"

        try:
            root = ET.fromstring(content)

            items = []
            if root.tag == "rss":
                channel = root.find("channel")
                for item in channel.findall("item")[:limit]:
                    items.append({
                        "title": self._get_text(item, "title"),
                        "link": self._get_text(item, "link"),
                        "date": self._get_text(item, "pubDate"),
                    })
            else:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall("atom:entry", ns)[:limit]:
                    link = entry.find("atom:link", ns)
                    items.append({
                        "title": self._get_text(entry, "atom:title", ns),
                        "link": link.get("href", "") if link is not None else "",
                        "date": self._get_text(entry, "atom:published", ns),
                    })

            return json.dumps({
                "count": len(items),
                "items": items,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def rss_generate(
        self,
        title: str,
        link: str,
        items: list,
        description: str = "",
    ) -> str:
        """Generate RSS feed."""
        rss = ET.Element("rss", version="2.0")
        channel = ET.SubElement(rss, "channel")

        ET.SubElement(channel, "title").text = title
        ET.SubElement(channel, "link").text = link
        ET.SubElement(channel, "description").text = description
        ET.SubElement(channel, "lastBuildDate").text = datetime.utcnow().strftime(
            "%a, %d %b %Y %H:%M:%S +0000"
        )

        for item_data in items:
            item = ET.SubElement(channel, "item")
            if isinstance(item_data, dict):
                for key, value in item_data.items():
                    if value:
                        ET.SubElement(item, key).text = str(value)
            elif isinstance(item_data, str):
                ET.SubElement(item, "title").text = item_data

        # Pretty print
        from xml.dom import minidom
        xml_str = ET.tostring(rss, encoding="unicode")
        pretty = minidom.parseString(xml_str).toprettyxml(indent="  ")

        # Remove extra declaration
        lines = pretty.split("\n")[1:]
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + "\n".join(lines)

    def rss_validate(self, content: str) -> str:
        """Validate RSS feed."""
        try:
            root = ET.fromstring(content)

            errors = []
            warnings = []

            if root.tag == "rss":
                channel = root.find("channel")
                if channel is None:
                    errors.append("Missing <channel> element")
                else:
                    if channel.find("title") is None:
                        errors.append("Missing <title> in channel")
                    if channel.find("link") is None:
                        errors.append("Missing <link> in channel")
                    if channel.find("description") is None:
                        warnings.append("Missing <description> in channel")

                    items = channel.findall("item")
                    for i, item in enumerate(items):
                        if item.find("title") is None and item.find("description") is None:
                            errors.append(f"Item {i+1}: needs title or description")

            elif root.tag.endswith("feed"):
                if root.find("{http://www.w3.org/2005/Atom}title") is None:
                    errors.append("Missing <title> element")
            else:
                errors.append(f"Unknown root element: {root.tag}")

            return json.dumps({
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "type": "rss" if root.tag == "rss" else "atom",
            }, indent=2)

        except ET.ParseError as e:
            return json.dumps({
                "valid": False,
                "errors": [f"XML parse error: {e}"],
            }, indent=2)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        return self.rss_parse(kwargs.get("url", ""))
