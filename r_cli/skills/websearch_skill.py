"""
Web Search Skill - Internet access for R CLI.

Provides web search and content fetching capabilities.
"""

import os
import re
from typing import Optional
from urllib.parse import quote, quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

from r_cli.core.agent import Skill
from r_cli.core.config import Config
from r_cli.core.llm import Tool


class WebSearchSkill(Skill):
    """Web search and content fetching skill."""

    name = "websearch"
    description = "Search the web and fetch content from URLs"

    def __init__(self, config: Optional[Config] = None):
        super().__init__(config)
        self.timeout = 15
        self.max_content_length = 8000
        # User agent - Wikipedia requires informative UA
        self.headers = {"User-Agent": "R-CLI/1.0 (https://github.com/raym33/r; Local AI Assistant)"}

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="web_search",
                description="Search the web for information. Use this to answer questions about people, events, facts, or any topic requiring internet knowledge.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query (e.g., 'Albert Einstein biography')",
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "Number of results to return (default: 5)",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
                handler=self.web_search,
            ),
            Tool(
                name="fetch_url",
                description="Fetch and extract text content from a URL",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to fetch",
                        },
                        "extract_main": {
                            "type": "boolean",
                            "description": "Extract only main content (default: true)",
                            "default": True,
                        },
                    },
                    "required": ["url"],
                },
                handler=self.fetch_url,
            ),
            Tool(
                name="wikipedia_search",
                description="Search Wikipedia for information about a topic. Best for factual information about people, places, events, concepts.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The topic to search (e.g., 'Albert Einstein')",
                        },
                        "language": {
                            "type": "string",
                            "description": "Wikipedia language code (default: 'en')",
                            "default": "en",
                        },
                    },
                    "required": ["query"],
                },
                handler=self.wikipedia_search,
            ),
        ]

    def web_search(self, query: str, num_results: int = 5) -> str:
        """
        Search the web using DuckDuckGo HTML (no API key needed).
        """
        try:
            # Use DuckDuckGo HTML search
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(search_url, headers=self.headers)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            # Parse DuckDuckGo results
            for result in soup.select(".result")[:num_results]:
                title_elem = result.select_one(".result__title")
                snippet_elem = result.select_one(".result__snippet")
                link_elem = result.select_one(".result__url")

                if title_elem:
                    title = title_elem.get_text(strip=True)
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    url = link_elem.get_text(strip=True) if link_elem else ""

                    results.append(f"**{title}**\n{snippet}\nURL: {url}\n")

            if not results:
                return f"No results found for: {query}"

            return f"Web search results for '{query}':\n\n" + "\n---\n".join(results)

        except httpx.TimeoutException:
            return f"Search timed out for: {query}"
        except Exception as e:
            return f"Search error: {e!s}"

    def fetch_url(self, url: str, extract_main: bool = True) -> str:
        """
        Fetch content from a URL and extract text.
        """
        try:
            # Validate URL
            parsed = urlparse(url)
            if not parsed.scheme:
                url = "https://" + url

            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, headers=self.headers)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script, style, nav, footer elements
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            if extract_main:
                # Try to find main content
                main_content = (
                    soup.find("main")
                    or soup.find("article")
                    or soup.find(class_=re.compile(r"content|article|post|entry"))
                    or soup.find("body")
                )
                if main_content:
                    text = main_content.get_text(separator="\n", strip=True)
                else:
                    text = soup.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)

            # Clean up text
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            text = "\n".join(lines)

            # Truncate if too long
            if len(text) > self.max_content_length:
                text = text[: self.max_content_length] + "\n\n[Content truncated...]"

            title = soup.title.string if soup.title else url
            return f"Content from: {title}\nURL: {url}\n\n{text}"

        except httpx.TimeoutException:
            return f"Timeout fetching: {url}"
        except Exception as e:
            return f"Error fetching URL: {e!s}"

    def wikipedia_search(self, query: str, language: str = "en") -> str:
        """
        Search Wikipedia and return article summary.
        """
        try:
            # Use Wikipedia API - replace spaces with underscores for article titles
            title = query.replace(" ", "_")
            api_url = (
                f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{quote(title, safe='')}"
            )

            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(api_url, headers=self.headers)

                if response.status_code == 404:
                    # Try search API instead
                    search_url = f"https://{language}.wikipedia.org/w/api.php"
                    params = {
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "format": "json",
                        "srlimit": 1,
                    }
                    search_response = client.get(search_url, params=params, headers=self.headers)
                    search_data = search_response.json()

                    if search_data.get("query", {}).get("search"):
                        # Get first result's title
                        found_title = search_data["query"]["search"][0]["title"]
                        title_encoded = found_title.replace(" ", "_")
                        api_url = f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{quote(title_encoded, safe='')}"
                        response = client.get(api_url, headers=self.headers)
                    else:
                        return f"No Wikipedia article found for: {query}"

                response.raise_for_status()
                data = response.json()

            title = data.get("title", query)
            extract = data.get("extract", "No summary available.")
            url = data.get("content_urls", {}).get("desktop", {}).get("page", "")

            # Get additional info if available
            description = data.get("description", "")

            result = f"**{title}**"
            if description:
                result += f" - {description}"
            result += f"\n\n{extract}"
            if url:
                result += f"\n\nSource: {url}"

            return result

        except httpx.TimeoutException:
            return f"Wikipedia search timed out for: {query}"
        except Exception as e:
            return f"Wikipedia error: {e!s}"

    def execute(self, **kwargs) -> str:
        """Direct execution."""
        action = kwargs.get("action", "search")
        query = kwargs.get("query", "")

        if action == "search":
            return self.web_search(query)
        elif action == "wikipedia":
            return self.wikipedia_search(query)
        elif action == "fetch":
            return self.fetch_url(kwargs.get("url", ""))
        else:
            return f"Unknown action: {action}"
