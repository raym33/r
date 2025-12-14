"""
Web Scraping Skill for R CLI.

Extract information from web pages:
- Get text from URLs
- Extract links
- Download content
- Parse HTML
"""

import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class WebSkill(Skill):
    """Skill for web scraping and web content extraction."""

    name = "web"
    description = "Web scraping: extract text, links and content from web pages"

    # User agent for requests
    USER_AGENT = "R-CLI/1.0 (Local AI Assistant)"

    # Timeout for requests
    TIMEOUT = 30

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="fetch_webpage",
                description="Get the content of a web page",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL of the web page",
                        },
                        "extract_text": {
                            "type": "boolean",
                            "description": "Whether to extract only text (no HTML)",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.fetch_webpage,
            ),
            Tool(
                name="extract_links",
                description="Extract all links from a web page",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL of the web page",
                        },
                        "filter_pattern": {
                            "type": "string",
                            "description": "Regex pattern to filter links",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.extract_links,
            ),
            Tool(
                name="download_file",
                description="Download a file from a URL",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL of the file to download",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path where to save the file",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.download_file,
            ),
            Tool(
                name="extract_tables",
                description="Extract tables from a web page as text",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL of the web page",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.extract_tables,
            ),
        ]

    def _validate_url(self, url: str) -> tuple[bool, str]:
        """Validate that the URL is safe."""
        try:
            parsed = urlparse(url)

            # Only HTTP/HTTPS
            if parsed.scheme not in ("http", "https"):
                return False, "Only HTTP/HTTPS URLs are allowed"

            # Do not allow local IPs or localhost
            hostname = parsed.hostname or ""
            if hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
                return False, "Local URLs are not allowed"

            # Do not allow private IP ranges
            if hostname.startswith(("192.168.", "10.", "172.")):
                return False, "Private IP ranges are not allowed"

            return True, ""
        except Exception as e:
            return False, f"Invalid URL: {e}"

    def fetch_webpage(self, url: str, extract_text: bool = True) -> str:
        """Get the content of a web page."""
        try:
            import httpx

            # Validate URL
            valid, error = self._validate_url(url)
            if not valid:
                return f"Error: {error}"

            # Make request
            headers = {"User-Agent": self.USER_AGENT}
            response = httpx.get(url, headers=headers, timeout=self.TIMEOUT, follow_redirects=True)
            response.raise_for_status()

            content = response.text

            if extract_text:
                try:
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(content, "html.parser")

                    # Remove scripts and styles
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.decompose()

                    # Extract text
                    text = soup.get_text(separator="\n", strip=True)

                    # Clean multiple empty lines
                    lines = [line.strip() for line in text.split("\n") if line.strip()]
                    text = "\n".join(lines)

                    # Limit size
                    if len(text) > 10000:
                        text = text[:10000] + "\n\n... (content truncated)"

                    return f"Content from {url}:\n\n{text}"

                except ImportError:
                    return "Error: beautifulsoup4 not installed. Run: pip install beautifulsoup4"
            else:
                # Return raw HTML (limited)
                if len(content) > 20000:
                    content = content[:20000] + "\n<!-- truncated -->"
                return content

        except ImportError:
            return "Error: httpx not installed. Run: pip install httpx"
        except httpx.TimeoutException:
            return f"Error: Timeout connecting to {url}"
        except httpx.HTTPStatusError as e:
            return f"Error HTTP {e.response.status_code}: {e}"
        except Exception as e:
            return f"Error fetching page: {e}"

    def extract_links(self, url: str, filter_pattern: Optional[str] = None) -> str:
        """Extract links from a web page."""
        try:
            import httpx
            from bs4 import BeautifulSoup

            # Validate URL
            valid, error = self._validate_url(url)
            if not valid:
                return f"Error: {error}"

            # Get page
            headers = {"User-Agent": self.USER_AGENT}
            response = httpx.get(url, headers=headers, timeout=self.TIMEOUT, follow_redirects=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Extract links
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)[:50]  # Limit text

                # Convert to absolute URL
                absolute_url = urljoin(url, href)

                # Filter if pattern provided
                if filter_pattern:
                    if not re.search(filter_pattern, absolute_url, re.IGNORECASE):
                        continue

                links.append((absolute_url, text))

            # Remove duplicates maintaining order
            seen = set()
            unique_links = []
            for link, text in links:
                if link not in seen:
                    seen.add(link)
                    unique_links.append((link, text))

            if not unique_links:
                return "No links found."

            result = [f"Links found in {url}:\n"]
            for link, text in unique_links[:50]:  # Limit to 50
                if text:
                    result.append(f"  • {text}: {link}")
                else:
                    result.append(f"  • {link}")

            if len(unique_links) > 50:
                result.append(f"\n... and {len(unique_links) - 50} more links")

            return "\n".join(result)

        except ImportError as e:
            if "httpx" in str(e):
                return "Error: httpx not installed. Run: pip install httpx"
            return "Error: beautifulsoup4 not installed. Run: pip install beautifulsoup4"
        except Exception as e:
            return f"Error extracting links: {e}"

    def download_file(self, url: str, output_path: Optional[str] = None) -> str:
        """Download a file from a URL."""
        try:
            import httpx

            # Validate URL
            valid, error = self._validate_url(url)
            if not valid:
                return f"Error: {error}"

            # Determine file name
            if output_path:
                out_path = Path(output_path)
            else:
                # Extract name from URL
                parsed = urlparse(url)
                filename = Path(parsed.path).name or "downloaded_file"
                out_path = Path(self.output_dir) / filename

            # Create directory if it doesn't exist
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Download with streaming
            headers = {"User-Agent": self.USER_AGENT}
            with httpx.stream(
                "GET", url, headers=headers, timeout=self.TIMEOUT, follow_redirects=True
            ) as response:
                response.raise_for_status()

                # Check size
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > 100_000_000:  # 100MB
                    return "Error: File too large (>100MB)"

                # Write file
                total_size = 0
                with open(out_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        total_size += len(chunk)

                        # Safety limit
                        if total_size > 100_000_000:
                            f.close()
                            out_path.unlink()
                            return "Error: Download cancelled, file too large"

            size_mb = total_size / (1024 * 1024)
            return f"File downloaded: {out_path} ({size_mb:.2f} MB)"

        except ImportError:
            return "Error: httpx not installed. Run: pip install httpx"
        except httpx.HTTPStatusError as e:
            return f"Error HTTP {e.response.status_code}"
        except Exception as e:
            return f"Error downloading file: {e}"

    def extract_tables(self, url: str) -> str:
        """Extract tables from a web page."""
        try:
            import httpx
            from bs4 import BeautifulSoup

            # Validate URL
            valid, error = self._validate_url(url)
            if not valid:
                return f"Error: {error}"

            # Get page
            headers = {"User-Agent": self.USER_AGENT}
            response = httpx.get(url, headers=headers, timeout=self.TIMEOUT, follow_redirects=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            tables = soup.find_all("table")

            if not tables:
                return "No tables found on the page."

            result = [f"Found {len(tables)} table(s):\n"]

            for i, table in enumerate(tables[:5], 1):  # Maximum 5 tables
                result.append(f"\n--- Table {i} ---")

                rows = table.find_all("tr")
                for row in rows[:20]:  # Maximum 20 rows per table
                    cells = row.find_all(["th", "td"])
                    cell_texts = [cell.get_text(strip=True)[:30] for cell in cells]  # Limit text
                    result.append(" | ".join(cell_texts))

                if len(rows) > 20:
                    result.append(f"... ({len(rows)} rows total)")

            if len(tables) > 5:
                result.append(f"\n... and {len(tables) - 5} more tables")

            return "\n".join(result)

        except ImportError as e:
            if "httpx" in str(e):
                return "Error: httpx not installed. Run: pip install httpx"
            return "Error: beautifulsoup4 not installed. Run: pip install beautifulsoup4"
        except Exception as e:
            return f"Error extracting tables: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        url = kwargs.get("url", "")
        if not url:
            return "Error: URL required"

        action = kwargs.get("action", "fetch")

        if action == "fetch":
            return self.fetch_webpage(url, kwargs.get("extract_text", True))
        elif action == "links":
            return self.extract_links(url, kwargs.get("filter"))
        elif action == "download":
            return self.download_file(url, kwargs.get("output"))
        elif action == "tables":
            return self.extract_tables(url)
        else:
            return f"Unrecognized action: {action}"
