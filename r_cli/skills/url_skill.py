"""
URL Skill for R CLI.

URL utilities:
- Parse and build URLs
- Encode/decode
- Extract components
- Query string handling
"""

import json
import re
from typing import Optional
from urllib.parse import (
    parse_qs,
    parse_qsl,
    quote,
    quote_plus,
    unquote,
    unquote_plus,
    urlencode,
    urlparse,
    urlunparse,
)

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class URLSkill(Skill):
    """Skill for URL operations."""

    name = "url"
    description = "URL: parse, build, encode/decode, query strings"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="url_parse",
                description="Parse URL into components",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to parse",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.url_parse,
            ),
            Tool(
                name="url_build",
                description="Build URL from components",
                parameters={
                    "type": "object",
                    "properties": {
                        "scheme": {
                            "type": "string",
                            "description": "Protocol (http, https)",
                        },
                        "host": {
                            "type": "string",
                            "description": "Hostname",
                        },
                        "path": {
                            "type": "string",
                            "description": "Path",
                        },
                        "query": {
                            "type": "object",
                            "description": "Query parameters",
                        },
                        "port": {
                            "type": "integer",
                            "description": "Port number",
                        },
                    },
                    "required": ["host"],
                },
                handler=self.url_build,
            ),
            Tool(
                name="url_encode",
                description="URL encode a string",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to encode",
                        },
                        "plus_spaces": {
                            "type": "boolean",
                            "description": "Use + for spaces (default: false)",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.url_encode,
            ),
            Tool(
                name="url_decode",
                description="URL decode a string",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to decode",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.url_decode,
            ),
            Tool(
                name="url_query_parse",
                description="Parse query string into key-value pairs",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Query string (with or without ?)",
                        },
                    },
                    "required": ["query"],
                },
                handler=self.url_query_parse,
            ),
            Tool(
                name="url_query_build",
                description="Build query string from key-value pairs",
                parameters={
                    "type": "object",
                    "properties": {
                        "params": {
                            "type": "object",
                            "description": "Parameters to encode",
                        },
                    },
                    "required": ["params"],
                },
                handler=self.url_query_build,
            ),
            Tool(
                name="url_join",
                description="Join base URL with relative path",
                parameters={
                    "type": "object",
                    "properties": {
                        "base": {
                            "type": "string",
                            "description": "Base URL",
                        },
                        "path": {
                            "type": "string",
                            "description": "Relative path",
                        },
                    },
                    "required": ["base", "path"],
                },
                handler=self.url_join,
            ),
            Tool(
                name="url_validate",
                description="Validate URL format",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to validate",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.url_validate,
            ),
            Tool(
                name="url_normalize",
                description="Normalize URL (lowercase, remove default port, etc.)",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to normalize",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.url_normalize,
            ),
        ]

    def url_parse(self, url: str) -> str:
        """Parse URL into components."""
        try:
            parsed = urlparse(url)

            # Parse query string
            query_params = parse_qs(parsed.query)
            # Flatten single-value lists
            query_params = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}

            result = {
                "original": url,
                "scheme": parsed.scheme or None,
                "host": parsed.hostname or None,
                "port": parsed.port,
                "path": parsed.path or None,
                "query": parsed.query or None,
                "query_params": query_params if query_params else None,
                "fragment": parsed.fragment or None,
                "username": parsed.username,
                "password": parsed.password,
            }

            # Remove None values
            result = {k: v for k, v in result.items() if v is not None}

            return json.dumps(result, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def url_build(
        self,
        host: str,
        scheme: str = "https",
        path: str = "",
        query: Optional[dict] = None,
        port: Optional[int] = None,
    ) -> str:
        """Build URL from components."""
        try:
            netloc = host
            if port:
                netloc = f"{host}:{port}"

            query_string = urlencode(query) if query else ""

            url = urlunparse((scheme, netloc, path, "", query_string, ""))

            return json.dumps({
                "url": url,
                "components": {
                    "scheme": scheme,
                    "host": host,
                    "port": port,
                    "path": path,
                    "query": query,
                },
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def url_encode(self, text: str, plus_spaces: bool = False) -> str:
        """URL encode text."""
        if plus_spaces:
            encoded = quote_plus(text)
        else:
            encoded = quote(text, safe="")

        return json.dumps({
            "original": text,
            "encoded": encoded,
        }, indent=2)

    def url_decode(self, text: str) -> str:
        """URL decode text."""
        # Try both decoders
        decoded_plus = unquote_plus(text)
        decoded = unquote(text)

        return json.dumps({
            "encoded": text,
            "decoded": decoded,
            "decoded_plus": decoded_plus if decoded_plus != decoded else None,
        }, indent=2)

    def url_query_parse(self, query: str) -> str:
        """Parse query string."""
        # Remove leading ?
        if query.startswith("?"):
            query = query[1:]

        try:
            # Parse as dict with lists
            params_list = parse_qs(query)
            # Flatten single values
            params = {k: v[0] if len(v) == 1 else v for k, v in params_list.items()}

            # Also get ordered list
            ordered = parse_qsl(query)

            return json.dumps({
                "query": query,
                "params": params,
                "ordered": ordered,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def url_query_build(self, params: dict) -> str:
        """Build query string."""
        try:
            query = urlencode(params, doseq=True)

            return json.dumps({
                "params": params,
                "query": query,
                "with_question": f"?{query}",
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def url_join(self, base: str, path: str) -> str:
        """Join base URL with relative path."""
        from urllib.parse import urljoin

        try:
            joined = urljoin(base, path)

            return json.dumps({
                "base": base,
                "path": path,
                "result": joined,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def url_validate(self, url: str) -> str:
        """Validate URL."""
        try:
            parsed = urlparse(url)

            # Basic validation
            has_scheme = bool(parsed.scheme)
            has_host = bool(parsed.hostname)
            valid_scheme = parsed.scheme in ["http", "https", "ftp", "file", "mailto", "tel", ""]

            # Pattern check
            url_pattern = re.compile(
                r"^(?:(?:https?|ftp)://)?"
                r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
                r"localhost|"
                r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
                r"(?::\d+)?"
                r"(?:/?|[/?]\S+)$", re.IGNORECASE)

            pattern_valid = bool(url_pattern.match(url))

            return json.dumps({
                "url": url,
                "valid": has_scheme and has_host and valid_scheme,
                "has_scheme": has_scheme,
                "has_host": has_host,
                "scheme_valid": valid_scheme,
                "pattern_match": pattern_valid,
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "url": url,
                "valid": False,
                "error": str(e),
            }, indent=2)

    def url_normalize(self, url: str) -> str:
        """Normalize URL."""
        try:
            parsed = urlparse(url)

            # Lowercase scheme and host
            scheme = parsed.scheme.lower()
            host = parsed.hostname.lower() if parsed.hostname else ""

            # Remove default ports
            port = parsed.port
            if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
                port = None

            netloc = host
            if port:
                netloc = f"{host}:{port}"
            if parsed.username:
                if parsed.password:
                    netloc = f"{parsed.username}:{parsed.password}@{netloc}"
                else:
                    netloc = f"{parsed.username}@{netloc}"

            # Normalize path
            path = parsed.path or "/"

            # Remove trailing slash (except for root)
            if path != "/" and path.endswith("/"):
                path = path.rstrip("/")

            # Sort query parameters
            query_params = parse_qsl(parsed.query)
            query_params.sort()
            query = urlencode(query_params)

            normalized = urlunparse((scheme, netloc, path, "", query, ""))

            return json.dumps({
                "original": url,
                "normalized": normalized,
                "changes": {
                    "lowercased_host": host != (parsed.hostname or ""),
                    "removed_default_port": parsed.port and not port,
                    "sorted_query": bool(query),
                },
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "parse")
        if action == "parse":
            return self.url_parse(kwargs.get("url", ""))
        elif action == "encode":
            return self.url_encode(kwargs.get("text", ""))
        return f"Unknown action: {action}"
