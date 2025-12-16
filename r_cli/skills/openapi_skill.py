"""
OpenAPI Skill for R CLI.

Service bridge for API integration:
- Load OpenAPI/Swagger specifications
- Auto-discover local services
- Generate dynamic tools from endpoints
- Call APIs without custom glue code
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class OpenAPISkill(Skill):
    """Skill for OpenAPI-based service integration."""

    name = "openapi"
    description = "API integration: load OpenAPI specs, discover services, call endpoints"

    TIMEOUT = 30

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loaded_specs: dict[str, dict] = {}  # name -> spec
        self._base_urls: dict[str, str] = {}  # name -> base_url

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="load_openapi_spec",
                description="Load an OpenAPI/Swagger specification from file or URL",
                parameters={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "Path to spec file or URL (supports JSON/YAML)",
                        },
                        "name": {
                            "type": "string",
                            "description": "Name for this API (default: derived from spec)",
                        },
                        "base_url": {
                            "type": "string",
                            "description": "Override base URL for API calls",
                        },
                    },
                    "required": ["source"],
                },
                handler=self.load_openapi_spec,
            ),
            Tool(
                name="list_endpoints",
                description="List all endpoints from a loaded OpenAPI spec",
                parameters={
                    "type": "object",
                    "properties": {
                        "api_name": {
                            "type": "string",
                            "description": "Name of loaded API (or 'all' for all APIs)",
                        },
                        "filter": {
                            "type": "string",
                            "description": "Filter endpoints by path pattern",
                        },
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "all"],
                            "description": "Filter by HTTP method",
                        },
                    },
                },
                handler=self.list_endpoints,
            ),
            Tool(
                name="call_endpoint",
                description="Call an endpoint from a loaded OpenAPI spec",
                parameters={
                    "type": "object",
                    "properties": {
                        "api_name": {
                            "type": "string",
                            "description": "Name of loaded API",
                        },
                        "path": {
                            "type": "string",
                            "description": "Endpoint path (e.g., /users/{id})",
                        },
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                            "description": "HTTP method (default: GET)",
                        },
                        "path_params": {
                            "type": "object",
                            "description": "Path parameters as key-value pairs",
                        },
                        "query_params": {
                            "type": "object",
                            "description": "Query parameters as key-value pairs",
                        },
                        "body": {
                            "type": "object",
                            "description": "Request body (for POST/PUT/PATCH)",
                        },
                        "headers": {
                            "type": "object",
                            "description": "Additional headers",
                        },
                    },
                    "required": ["api_name", "path"],
                },
                handler=self.call_endpoint,
            ),
            Tool(
                name="discover_services",
                description="Auto-discover local services running on common ports",
                parameters={
                    "type": "object",
                    "properties": {
                        "ports": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Ports to scan (default: common dev ports)",
                        },
                        "load_specs": {
                            "type": "boolean",
                            "description": "Try to load OpenAPI specs from discovered services",
                        },
                    },
                },
                handler=self.discover_services,
            ),
            Tool(
                name="describe_endpoint",
                description="Get detailed information about a specific endpoint",
                parameters={
                    "type": "object",
                    "properties": {
                        "api_name": {
                            "type": "string",
                            "description": "Name of loaded API",
                        },
                        "path": {
                            "type": "string",
                            "description": "Endpoint path",
                        },
                        "method": {
                            "type": "string",
                            "description": "HTTP method (default: GET)",
                        },
                    },
                    "required": ["api_name", "path"],
                },
                handler=self.describe_endpoint,
            ),
            Tool(
                name="list_loaded_apis",
                description="List all loaded OpenAPI specifications",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.list_loaded_apis,
            ),
            Tool(
                name="generate_curl",
                description="Generate a curl command for an endpoint",
                parameters={
                    "type": "object",
                    "properties": {
                        "api_name": {
                            "type": "string",
                            "description": "Name of loaded API",
                        },
                        "path": {
                            "type": "string",
                            "description": "Endpoint path",
                        },
                        "method": {
                            "type": "string",
                            "description": "HTTP method (default: GET)",
                        },
                        "path_params": {
                            "type": "object",
                            "description": "Path parameters",
                        },
                        "query_params": {
                            "type": "object",
                            "description": "Query parameters",
                        },
                        "body": {
                            "type": "object",
                            "description": "Request body",
                        },
                    },
                    "required": ["api_name", "path"],
                },
                handler=self.generate_curl,
            ),
        ]

    def _parse_spec(self, content: str, source: str) -> dict:
        """Parse OpenAPI spec from JSON or YAML."""
        # Try JSON first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try YAML
        try:
            import yaml

            return yaml.safe_load(content)
        except ImportError:
            pass
        except Exception:
            pass

        raise ValueError(f"Could not parse spec from {source} (not valid JSON/YAML)")

    def _fetch_url(self, url: str) -> str:
        """Fetch content from URL."""
        try:
            import httpx

            response = httpx.get(url, timeout=self.TIMEOUT, follow_redirects=True)
            response.raise_for_status()
            return response.text
        except ImportError:
            # Fallback to curl
            result = subprocess.run(
                ["curl", "-s", "-L", url],
                check=False,
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
            )
            if result.returncode != 0:
                raise Exception(f"curl failed: {result.stderr}")
            return result.stdout

    def _get_base_url(self, spec: dict, override: Optional[str] = None) -> str:
        """Extract base URL from spec or use override."""
        if override:
            return override.rstrip("/")

        # OpenAPI 3.x
        if spec.get("servers"):
            return spec["servers"][0].get("url", "http://localhost").rstrip("/")

        # Swagger 2.x
        if "host" in spec:
            scheme = spec.get("schemes", ["http"])[0]
            base_path = spec.get("basePath", "")
            return f"{scheme}://{spec['host']}{base_path}".rstrip("/")

        return "http://localhost"

    def load_openapi_spec(
        self,
        source: str,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> str:
        """Load an OpenAPI specification."""
        result = []

        try:
            # Determine if URL or file
            if source.startswith(("http://", "https://")):
                content = self._fetch_url(source)
            else:
                path = Path(source).expanduser()
                if not path.exists():
                    return f"Error: File not found: {source}"
                content = path.read_text()

            # Parse spec
            spec = self._parse_spec(content, source)

            # Get API name
            api_name = name or spec.get("info", {}).get("title", "api")
            api_name = re.sub(r"[^a-zA-Z0-9_]", "_", api_name).lower()

            # Get base URL
            resolved_base_url = self._get_base_url(spec, base_url)

            # Store
            self._loaded_specs[api_name] = spec
            self._base_urls[api_name] = resolved_base_url

            # Summary
            info = spec.get("info", {})
            paths = spec.get("paths", {})
            endpoint_count = sum(
                len([m for m in p if m in ("get", "post", "put", "delete", "patch")])
                for p in paths.values()
            )

            result.append(f"=== Loaded OpenAPI Spec: {api_name} ===\n")
            result.append(f"Title: {info.get('title', 'N/A')}")
            result.append(f"Version: {info.get('version', 'N/A')}")
            result.append(f"Base URL: {resolved_base_url}")
            result.append(f"Endpoints: {endpoint_count}")

            if info.get("description"):
                result.append(f"\nDescription: {info['description'][:200]}")

        except Exception as e:
            return f"Error loading spec: {e}"

        return "\n".join(result)

    def list_endpoints(
        self,
        api_name: str = "all",
        filter: Optional[str] = None,
        method: str = "all",
    ) -> str:
        """List endpoints from loaded specs."""
        if not self._loaded_specs:
            return "No APIs loaded. Use load_openapi_spec first."

        result = []
        apis = self._loaded_specs.keys() if api_name == "all" else [api_name]

        for name in apis:
            if name not in self._loaded_specs:
                result.append(f"API not found: {name}")
                continue

            spec = self._loaded_specs[name]
            base_url = self._base_urls[name]
            result.append(f"=== {name} ({base_url}) ===\n")

            paths = spec.get("paths", {})
            for path, methods in sorted(paths.items()):
                # Filter by path pattern
                if filter and filter.lower() not in path.lower():
                    continue

                for http_method, details in methods.items():
                    if http_method not in ("get", "post", "put", "delete", "patch"):
                        continue

                    # Filter by method
                    if method != "all" and http_method.upper() != method.upper():
                        continue

                    summary = details.get("summary", details.get("operationId", ""))
                    result.append(f"  {http_method.upper():6} {path}")
                    if summary:
                        result.append(f"         {summary[:60]}")

            result.append("")

        return "\n".join(result) if result else "No matching endpoints found"

    def call_endpoint(
        self,
        api_name: str,
        path: str,
        method: str = "GET",
        path_params: Optional[dict] = None,
        query_params: Optional[dict] = None,
        body: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> str:
        """Call an API endpoint."""
        if api_name not in self._loaded_specs:
            return f"Error: API not loaded: {api_name}. Use load_openapi_spec first."

        base_url = self._base_urls[api_name]

        # Substitute path parameters
        resolved_path = path
        if path_params:
            for key, value in path_params.items():
                resolved_path = resolved_path.replace(f"{{{key}}}", str(value))

        url = f"{base_url}{resolved_path}"

        # Add query parameters
        if query_params:
            query_string = "&".join(f"{k}={v}" for k, v in query_params.items())
            url = f"{url}?{query_string}"

        result = [f"=== API Call: {method} {url} ===\n"]

        try:
            import httpx

            # Prepare request
            req_headers = {"Accept": "application/json"}
            if headers:
                req_headers.update(headers)
            if body:
                req_headers["Content-Type"] = "application/json"

            # Make request
            with httpx.Client(timeout=self.TIMEOUT) as client:
                response = client.request(
                    method=method.upper(),
                    url=url,
                    headers=req_headers,
                    json=body,
                )

            result.append(f"Status: {response.status_code}")
            result.append(f"Headers: {dict(response.headers)}")

            # Parse response
            try:
                resp_json = response.json()
                result.append(f"\nResponse:\n{json.dumps(resp_json, indent=2)[:2000]}")
            except Exception:
                result.append(f"\nResponse:\n{response.text[:2000]}")

        except ImportError:
            # Fallback to curl
            cmd = ["curl", "-s", "-X", method.upper()]
            if headers:
                for k, v in headers.items():
                    cmd.extend(["-H", f"{k}: {v}"])
            if body:
                cmd.extend(["-H", "Content-Type: application/json"])
                cmd.extend(["-d", json.dumps(body)])
            cmd.append(url)

            proc = subprocess.run(
                cmd, check=False, capture_output=True, text=True, timeout=self.TIMEOUT
            )
            result.append(f"Response:\n{proc.stdout[:2000]}")

        except Exception as e:
            return f"Error calling endpoint: {e}"

        return "\n".join(result)

    def discover_services(
        self,
        ports: Optional[list[int]] = None,
        load_specs: bool = True,
    ) -> str:
        """Auto-discover local services."""
        if ports is None:
            ports = [
                3000,
                3001,
                4000,
                5000,
                5001,  # Node.js, Flask
                8000,
                8080,
                8888,  # Django, FastAPI, Spring
                9000,
                9090,  # Various
                80,
                443,  # Standard HTTP/HTTPS
            ]

        result = ["=== Service Discovery ===\n"]
        discovered = []

        for port in ports:
            try:
                import httpx

                # Try to connect
                for path in ["", "/api", "/docs", "/swagger", "/openapi.json"]:
                    url = f"http://localhost:{port}{path}"
                    try:
                        response = httpx.get(url, timeout=2, follow_redirects=True)
                        if response.status_code < 500:
                            discovered.append(
                                {
                                    "port": port,
                                    "path": path,
                                    "status": response.status_code,
                                    "url": url,
                                }
                            )
                            break
                    except Exception:
                        continue
            except ImportError:
                # Fallback: just check if port is open
                import socket

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                if sock.connect_ex(("localhost", port)) == 0:
                    discovered.append({"port": port, "url": f"http://localhost:{port}"})
                sock.close()

        if not discovered:
            return "No services discovered on common ports"

        result.append(f"Found {len(discovered)} services:\n")
        for svc in discovered:
            result.append(f"  Port {svc['port']}: {svc['url']}")

            # Try to load OpenAPI spec
            if load_specs:
                spec_paths = [
                    "/openapi.json",
                    "/swagger.json",
                    "/api/openapi.json",
                    "/api-docs",
                    "/v1/openapi.json",
                    "/docs/openapi.json",
                ]
                for spec_path in spec_paths:
                    try:
                        spec_url = f"http://localhost:{svc['port']}{spec_path}"
                        content = self._fetch_url(spec_url)
                        spec = self._parse_spec(content, spec_url)
                        if "paths" in spec or "openapi" in spec or "swagger" in spec:
                            api_name = f"localhost_{svc['port']}"
                            self._loaded_specs[api_name] = spec
                            self._base_urls[api_name] = f"http://localhost:{svc['port']}"
                            result.append(f"    -> Loaded OpenAPI spec as '{api_name}'")
                            break
                    except Exception:
                        continue

        return "\n".join(result)

    def describe_endpoint(
        self,
        api_name: str,
        path: str,
        method: str = "GET",
    ) -> str:
        """Get detailed info about an endpoint."""
        if api_name not in self._loaded_specs:
            return f"Error: API not loaded: {api_name}"

        spec = self._loaded_specs[api_name]
        paths = spec.get("paths", {})

        if path not in paths:
            return f"Error: Path not found: {path}"

        method_lower = method.lower()
        if method_lower not in paths[path]:
            available = [m for m in paths[path] if m in ("get", "post", "put", "delete", "patch")]
            return f"Error: Method {method} not available. Available: {available}"

        endpoint = paths[path][method_lower]
        result = [f"=== {method.upper()} {path} ===\n"]

        # Basic info
        result.append(f"Summary: {endpoint.get('summary', 'N/A')}")
        result.append(f"Operation ID: {endpoint.get('operationId', 'N/A')}")
        if endpoint.get("description"):
            result.append(f"Description: {endpoint['description'][:300]}")

        # Parameters
        params = endpoint.get("parameters", [])
        if params:
            result.append("\n## Parameters")
            for p in params:
                required = "*" if p.get("required") else ""
                p_type = p.get("schema", {}).get("type", p.get("type", "any"))
                result.append(f"  {p['name']}{required} ({p.get('in', 'query')}): {p_type}")
                if p.get("description"):
                    result.append(f"    {p['description'][:100]}")

        # Request body
        request_body = endpoint.get("requestBody", {})
        if request_body:
            result.append("\n## Request Body")
            content = request_body.get("content", {})
            for content_type, schema_info in content.items():
                result.append(f"  Content-Type: {content_type}")
                schema = schema_info.get("schema", {})
                if "$ref" in schema:
                    result.append(f"  Schema: {schema['$ref']}")
                elif schema.get("properties"):
                    result.append("  Properties:")
                    for prop_name, prop_info in schema["properties"].items():
                        result.append(f"    - {prop_name}: {prop_info.get('type', 'any')}")

        # Responses
        responses = endpoint.get("responses", {})
        if responses:
            result.append("\n## Responses")
            for code, resp in responses.items():
                result.append(f"  {code}: {resp.get('description', 'N/A')[:50]}")

        return "\n".join(result)

    def list_loaded_apis(self) -> str:
        """List all loaded APIs."""
        if not self._loaded_specs:
            return "No APIs loaded yet. Use load_openapi_spec to load one."

        result = ["=== Loaded APIs ===\n"]
        for name, spec in self._loaded_specs.items():
            info = spec.get("info", {})
            paths_count = len(spec.get("paths", {}))
            result.append(f"  {name}")
            result.append(f"    Title: {info.get('title', 'N/A')}")
            result.append(f"    Base URL: {self._base_urls[name]}")
            result.append(f"    Paths: {paths_count}")
            result.append("")

        return "\n".join(result)

    def generate_curl(
        self,
        api_name: str,
        path: str,
        method: str = "GET",
        path_params: Optional[dict] = None,
        query_params: Optional[dict] = None,
        body: Optional[dict] = None,
    ) -> str:
        """Generate curl command for an endpoint."""
        if api_name not in self._loaded_specs:
            return f"Error: API not loaded: {api_name}"

        base_url = self._base_urls[api_name]

        # Substitute path parameters
        resolved_path = path
        if path_params:
            for key, value in path_params.items():
                resolved_path = resolved_path.replace(f"{{{key}}}", str(value))

        url = f"{base_url}{resolved_path}"

        # Build curl command
        parts = ["curl"]

        if method.upper() != "GET":
            parts.extend(["-X", method.upper()])

        if query_params:
            query_string = "&".join(f"{k}={v}" for k, v in query_params.items())
            url = f"{url}?{query_string}"

        if body:
            parts.extend(["-H", "'Content-Type: application/json'"])
            parts.extend(["-d", f"'{json.dumps(body)}'"])

        parts.append(f"'{url}'")

        return " \\\n  ".join(parts)

    def get_prompt(self) -> str:
        return """You are an API integration expert. Help users:
- Load and explore OpenAPI/Swagger specifications
- Discover local services and their APIs
- Call API endpoints with proper parameters
- Generate curl commands for testing

Use load_openapi_spec to load an API spec from file or URL.
Use discover_services to find local running services.
Use list_endpoints to see available endpoints.
Use describe_endpoint for detailed endpoint information.
Use call_endpoint to make API calls.
Use generate_curl to get curl commands.
"""
