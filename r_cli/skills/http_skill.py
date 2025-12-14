"""
Skill HTTP para R CLI.

Cliente REST API:
- GET, POST, PUT, DELETE
- Headers personalizados
- Autenticación
- Manejo de JSON
"""

import json
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class HTTPSkill(Skill):
    """Skill para operaciones HTTP/REST."""

    name = "http"
    description = "Cliente HTTP/REST: GET, POST, PUT, DELETE con soporte JSON"

    USER_AGENT = "R-CLI/1.0"
    TIMEOUT = 30

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="http_get",
                description="Realiza una petición GET",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL del endpoint",
                        },
                        "headers": {
                            "type": "string",
                            "description": "Headers en formato KEY:value,KEY2:value2",
                        },
                        "auth": {
                            "type": "string",
                            "description": "Autenticación Bearer token o user:password",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.http_get,
            ),
            Tool(
                name="http_post",
                description="Realiza una petición POST",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL del endpoint",
                        },
                        "data": {
                            "type": "string",
                            "description": "Datos a enviar (JSON string)",
                        },
                        "headers": {
                            "type": "string",
                            "description": "Headers adicionales",
                        },
                        "auth": {
                            "type": "string",
                            "description": "Autenticación",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.http_post,
            ),
            Tool(
                name="http_put",
                description="Realiza una petición PUT",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL del endpoint",
                        },
                        "data": {
                            "type": "string",
                            "description": "Datos a enviar (JSON string)",
                        },
                        "headers": {
                            "type": "string",
                            "description": "Headers adicionales",
                        },
                        "auth": {
                            "type": "string",
                            "description": "Autenticación",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.http_put,
            ),
            Tool(
                name="http_delete",
                description="Realiza una petición DELETE",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL del endpoint",
                        },
                        "headers": {
                            "type": "string",
                            "description": "Headers adicionales",
                        },
                        "auth": {
                            "type": "string",
                            "description": "Autenticación",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.http_delete,
            ),
            Tool(
                name="http_request",
                description="Realiza una petición HTTP personalizada",
                parameters={
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
                            "description": "Método HTTP",
                        },
                        "url": {
                            "type": "string",
                            "description": "URL del endpoint",
                        },
                        "data": {
                            "type": "string",
                            "description": "Cuerpo de la petición",
                        },
                        "headers": {
                            "type": "string",
                            "description": "Headers",
                        },
                        "auth": {
                            "type": "string",
                            "description": "Autenticación",
                        },
                    },
                    "required": ["method", "url"],
                },
                handler=self.http_request,
            ),
        ]

    def _validate_url(self, url: str) -> tuple[bool, str]:
        """Valida la URL."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False, "Solo se permiten URLs HTTP/HTTPS"

            # Bloquear localhost/IPs privadas en producción
            hostname = parsed.hostname or ""
            if hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
                # Permitir localhost para desarrollo
                pass

            return True, ""
        except Exception as e:
            return False, str(e)

    def _parse_headers(self, headers_str: Optional[str]) -> dict:
        """Parsea string de headers a diccionario."""
        headers = {"User-Agent": self.USER_AGENT}

        if headers_str:
            for item in headers_str.split(","):
                if ":" in item:
                    key, value = item.split(":", 1)
                    headers[key.strip()] = value.strip()

        return headers

    def _parse_auth(self, auth_str: Optional[str]) -> Optional[tuple]:
        """Parsea autenticación."""
        if not auth_str:
            return None

        if ":" in auth_str:
            # Basic auth: user:password
            return tuple(auth_str.split(":", 1))
        else:
            # Bearer token - se manejará en headers
            return None

    def _get_auth_header(self, auth_str: Optional[str]) -> Optional[dict]:
        """Obtiene header de autenticación."""
        if auth_str and ":" not in auth_str:
            # Bearer token
            return {"Authorization": f"Bearer {auth_str}"}
        return None

    def _format_response(self, response, include_headers: bool = False) -> str:
        """Formatea la respuesta HTTP."""
        result = [f"HTTP {response.status_code}"]

        if include_headers:
            result.append("\nHeaders:")
            for key, value in response.headers.items():
                result.append(f"  {key}: {value}")

        result.append("\nBody:")

        content = response.text

        # Intentar formatear JSON
        try:
            data = response.json()
            content = json.dumps(data, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, Exception):
            pass

        # Limitar tamaño
        if len(content) > 10000:
            content = content[:10000] + "\n\n... (respuesta truncada)"

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
        """Realiza una petición HTTP."""
        try:
            import httpx

            # Validar URL
            valid, error = self._validate_url(url)
            if not valid:
                return f"Error: {error}"

            # Preparar headers
            req_headers = self._parse_headers(headers)

            # Agregar auth header si es Bearer
            auth_header = self._get_auth_header(auth)
            if auth_header:
                req_headers.update(auth_header)

            # Preparar auth tuple si es Basic
            auth_tuple = self._parse_auth(auth) if auth and ":" in auth else None

            # Preparar data
            json_data = None
            if data:
                try:
                    json_data = json.loads(data)
                    if "Content-Type" not in req_headers:
                        req_headers["Content-Type"] = "application/json"
                except json.JSONDecodeError:
                    # Enviar como texto plano
                    pass

            # Realizar petición
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
            return "Error: httpx no instalado. Ejecuta: pip install httpx"
        except httpx.TimeoutException:
            return f"Error: Timeout conectando a {url}"
        except httpx.ConnectError as e:
            return f"Error de conexión: {e}"
        except Exception as e:
            return f"Error: {e}"

    def http_get(
        self,
        url: str,
        headers: Optional[str] = None,
        auth: Optional[str] = None,
    ) -> str:
        """Petición GET."""
        return self._make_request("GET", url, headers=headers, auth=auth)

    def http_post(
        self,
        url: str,
        data: Optional[str] = None,
        headers: Optional[str] = None,
        auth: Optional[str] = None,
    ) -> str:
        """Petición POST."""
        return self._make_request("POST", url, data=data, headers=headers, auth=auth)

    def http_put(
        self,
        url: str,
        data: Optional[str] = None,
        headers: Optional[str] = None,
        auth: Optional[str] = None,
    ) -> str:
        """Petición PUT."""
        return self._make_request("PUT", url, data=data, headers=headers, auth=auth)

    def http_delete(
        self,
        url: str,
        headers: Optional[str] = None,
        auth: Optional[str] = None,
    ) -> str:
        """Petición DELETE."""
        return self._make_request("DELETE", url, headers=headers, auth=auth)

    def http_request(
        self,
        method: str,
        url: str,
        data: Optional[str] = None,
        headers: Optional[str] = None,
        auth: Optional[str] = None,
    ) -> str:
        """Petición HTTP personalizada."""
        return self._make_request(method.upper(), url, data=data, headers=headers, auth=auth)

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        method = kwargs.get("method", "GET").upper()
        url = kwargs.get("url", "")

        if not url:
            return "Error: Se requiere una URL"

        return self._make_request(
            method,
            url,
            data=kwargs.get("data"),
            headers=kwargs.get("headers"),
            auth=kwargs.get("auth"),
        )
