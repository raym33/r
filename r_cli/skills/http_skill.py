"""
HTTP Skill for R CLI.

REST API client:
- GET, POST, PUT, DELETE
- Custom headers
- Authentication
- JSON handling
"""

import json
import logging
from typing import Optional
from urllib.parse import urlparse

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool

logger = logging.getLogger(__name__)


class HTTPSkill(Skill):
    """Skill for HTTP/REST operations."""

    name = "http"
    description = "HTTP/REST client: GET, POST, PUT, DELETE with JSON support"

    USER_AGENT = "R-CLI/1.0"
    TIMEOUT = 30

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="http_get",
                description="Make a GET request",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Endpoint URL",
                        },
                        "headers": {
                            "type": "string",
                            "description": "Headers in KEY:value,KEY2:value2 format",
                        },
                        "auth": {
                            "type": "string",
                            "description": "Bearer token or user:password authentication",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.http_get,
            ),
            Tool(
                name="http_post",
                description="Make a POST request",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Endpoint URL",
                        },
                        "data": {
                            "type": "string",
                            "description": "Data to send (JSON string)",
                        },
                        "headers": {
                            "type": "string",
                            "description": "Additional headers",
                        },
                        "auth": {
                            "type": "string",
                            "description": "Authentication",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.http_post,
            ),
            Tool(
                name="http_put",
                description="Make a PUT request",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Endpoint URL",
                        },
                        "data": {
                            "type": "string",
                            "description": "Data to send (JSON string)",
                        },
                        "headers": {
                            "type": "string",
                            "description": "Additional headers",
                        },
                        "auth": {
                            "type": "string",
                            "description": "Authentication",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.http_put,
            ),
            Tool(
                name="http_delete",
                description="Make a DELETE request",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Endpoint URL",
                        },
                        "headers": {
                            "type": "string",
                            "description": "Additional headers",
                        },
                        "auth": {
                            "type": "string",
                            "description": "Authentication",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.http_delete,
            ),
            Tool(
                name="http_request",
                description="Make a custom HTTP request",
                parameters={
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
                            "description": "HTTP method",
                        },
                        "url": {
                            "type": "string",
                            "description": "Endpoint URL",
                        },
                        "data": {
                            "type": "string",
                            "description": "Request body",
                        },
                        "headers": {
                            "type": "string",
                            "description": "Headers",
                        },
                        "auth": {
                            "type": "string",
                            "description": "Authentication",
                        },
                    },
                    "required": ["method", "url"],
                },
                handler=self.http_request,
            ),
        ]

    def _validate_url(self, url: str) -> tuple[bool, str]:
        """Validate the URL."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False, "Only HTTP/HTTPS URLs are allowed"

            # Block localhost/private IPs in production
            hostname = parsed.hostname or ""
            if hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
                # Allow localhost for development
                pass

            return True, ""
        except Exception as e:
            return False, str(e)

    def _parse_headers(self, headers_str: Optional[str]) -> dict:
        """Parse headers string to dictionary."""
        headers = {"User-Agent": self.USER_AGENT}

        if headers_str:
            for item in headers_str.split(","):
                if ":" in item:
                    key, value = item.split(":", 1)
                    headers[key.strip()] = value.strip()

        return headers

    def _parse_auth(self, auth_str: Optional[str]) -> Optional[tuple]:
        """Parse authentication."""
        if not auth_str:
            return None

        if ":" in auth_str:
            # Basic auth: user:password
            return tuple(auth_str.split(":", 1))
        else:
            # Bearer token - will be handled in headers
            return None

    def _get_auth_header(self, auth_str: Optional[str]) -> Optional[dict]:
        """Get authentication header."""
        if auth_str and ":" not in auth_str:
            # Bearer token
            return {"Authorization": f"Bearer {auth_str}"}
        return None

    def _format_response(self, response, include_headers: bool = False) -> str:
        """Format HTTP response."""
        result = [f"HTTP {response.status_code}"]

        if include_headers:
            result.append("\nHeaders:")
            for key, value in response.headers.items():
                result.append(f"  {key}: {value}")

        result.append("\nBody:")

        content = response.text

        # Try to format JSON
        try:
            data = response.json()
            content = json.dumps(data, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, Exception) as e:
            logger.debug(f"Response is not valid JSON: {e}")

        # Limit size
        if len(content) > 10000:
            content = content[:10000] + "\n\n... (response truncated)"

        result.append(content)

        return "\n".join(result)

    def _make_request(
        self,
        method: str,
        url: str,
        data: Optional[str] = None,
        headers: Optional[str] = None,
        auth: Optional[str] = None,
    ) -> str:
        """Make an HTTP request."""
        try:
            import httpx

            # Validate URL
            valid, error = self._validate_url(url)
            if not valid:
                return f"Error: {error}"

            # Prepare headers
            req_headers = self._parse_headers(headers)

            # Add auth header if Bearer
            auth_header = self._get_auth_header(auth)
            if auth_header:
                req_headers.update(auth_header)

            # Prepare auth tuple if Basic
            auth_tuple = self._parse_auth(auth) if auth and ":" in auth else None

            # Prepare data
            json_data = None
            if data:
                try:
                    json_data = json.loads(data)
                    if "Content-Type" not in req_headers:
                        req_headers["Content-Type"] = "application/json"
                except json.JSONDecodeError:
                    # Send as plain text
                    pass

            # Make request
            with httpx.Client(timeout=self.TIMEOUT, follow_redirects=True) as client:
                if json_data:
                    response = client.request(
                        method,
                        url,
                        headers=req_headers,
                        json=json_data,
                        auth=auth_tuple,
                    )
                elif data:
                    response = client.request(
                        method,
                        url,
                        headers=req_headers,
                        content=data,
                        auth=auth_tuple,
                    )
                else:
                    response = client.request(
                        method,
                        url,
                        headers=req_headers,
                        auth=auth_tuple,
                    )

            return self._format_response(response)

        except ImportError:
            return "Error: httpx not installed. Run: pip install httpx"
        except httpx.TimeoutException:
            return f"Error: Timeout connecting to {url}"
        except httpx.ConnectError as e:
            return f"Connection error: {e}"
        except Exception as e:
            return f"Error: {e}"

    def http_get(
        self,
        url: str,
        headers: Optional[str] = None,
        auth: Optional[str] = None,
    ) -> str:
        """GET request."""
        return self._make_request("GET", url, headers=headers, auth=auth)

    def http_post(
        self,
        url: str,
        data: Optional[str] = None,
        headers: Optional[str] = None,
        auth: Optional[str] = None,
    ) -> str:
        """POST request."""
        return self._make_request("POST", url, data=data, headers=headers, auth=auth)

    def http_put(
        self,
        url: str,
        data: Optional[str] = None,
        headers: Optional[str] = None,
        auth: Optional[str] = None,
    ) -> str:
        """PUT request."""
        return self._make_request("PUT", url, data=data, headers=headers, auth=auth)

    def http_delete(
        self,
        url: str,
        headers: Optional[str] = None,
        auth: Optional[str] = None,
    ) -> str:
        """DELETE request."""
        return self._make_request("DELETE", url, headers=headers, auth=auth)

    def http_request(
        self,
        method: str,
        url: str,
        data: Optional[str] = None,
        headers: Optional[str] = None,
        auth: Optional[str] = None,
    ) -> str:
        """Custom HTTP request."""
        return self._make_request(method.upper(), url, data=data, headers=headers, auth=auth)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        method = kwargs.get("method", "GET").upper()
        url = kwargs.get("url", "")

        if not url:
            return "Error: URL is required"

        return self._make_request(
            method,
            url,
            data=kwargs.get("data"),
            headers=kwargs.get("headers"),
            auth=kwargs.get("auth"),
        )
