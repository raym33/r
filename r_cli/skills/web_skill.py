"""
Skill de Web Scraping para R CLI.

Permite extraer información de páginas web:
- Obtener texto de URLs
- Extraer enlaces
- Descargar contenido
- Parsear HTML
"""

import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class WebSkill(Skill):
    """Skill para web scraping y extracción de contenido web."""

    name = "web"
    description = "Web scraping: extraer texto, enlaces y contenido de páginas web"

    # User agent para requests
    USER_AGENT = "R-CLI/1.0 (Local AI Assistant)"

    # Timeout para requests
    TIMEOUT = 30

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="fetch_webpage",
                description="Obtiene el contenido de una página web",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL de la página web",
                        },
                        "extract_text": {
                            "type": "boolean",
                            "description": "Si extraer solo texto (sin HTML)",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.fetch_webpage,
            ),
            Tool(
                name="extract_links",
                description="Extrae todos los enlaces de una página web",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL de la página web",
                        },
                        "filter_pattern": {
                            "type": "string",
                            "description": "Patrón regex para filtrar enlaces",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.extract_links,
            ),
            Tool(
                name="download_file",
                description="Descarga un archivo de una URL",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL del archivo a descargar",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Ruta donde guardar el archivo",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.download_file,
            ),
            Tool(
                name="extract_tables",
                description="Extrae tablas de una página web como texto",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL de la página web",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.extract_tables,
            ),
        ]

    def _validate_url(self, url: str) -> tuple[bool, str]:
        """Valida que la URL sea segura."""
        try:
            parsed = urlparse(url)

            # Solo HTTP/HTTPS
            if parsed.scheme not in ("http", "https"):
                return False, "Solo se permiten URLs HTTP/HTTPS"

            # No permitir IPs locales o localhost
            hostname = parsed.hostname or ""
            if hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
                return False, "No se permiten URLs locales"

            # No permitir rangos de IP privados
            if hostname.startswith(("192.168.", "10.", "172.")):
                return False, "No se permiten rangos de IP privados"

            return True, ""
        except Exception as e:
            return False, f"URL inválida: {e}"

    def fetch_webpage(self, url: str, extract_text: bool = True) -> str:
        """Obtiene el contenido de una página web."""
        try:
            import httpx

            # Validar URL
            valid, error = self._validate_url(url)
            if not valid:
                return f"Error: {error}"

            # Hacer request
            headers = {"User-Agent": self.USER_AGENT}
            response = httpx.get(url, headers=headers, timeout=self.TIMEOUT, follow_redirects=True)
            response.raise_for_status()

            content = response.text

            if extract_text:
                try:
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(content, "html.parser")

                    # Remover scripts y estilos
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.decompose()

                    # Extraer texto
                    text = soup.get_text(separator="\n", strip=True)

                    # Limpiar líneas vacías múltiples
                    lines = [line.strip() for line in text.split("\n") if line.strip()]
                    text = "\n".join(lines)

                    # Limitar tamaño
                    if len(text) > 10000:
                        text = text[:10000] + "\n\n... (contenido truncado)"

                    return f"Contenido de {url}:\n\n{text}"

                except ImportError:
                    return "Error: beautifulsoup4 no instalado. Ejecuta: pip install beautifulsoup4"
            else:
                # Retornar HTML crudo (limitado)
                if len(content) > 20000:
                    content = content[:20000] + "\n<!-- truncado -->"
                return content

        except ImportError:
            return "Error: httpx no instalado. Ejecuta: pip install httpx"
        except httpx.TimeoutException:
            return f"Error: Timeout al conectar a {url}"
        except httpx.HTTPStatusError as e:
            return f"Error HTTP {e.response.status_code}: {e}"
        except Exception as e:
            return f"Error obteniendo página: {e}"

    def extract_links(self, url: str, filter_pattern: Optional[str] = None) -> str:
        """Extrae enlaces de una página web."""
        try:
            import httpx
            from bs4 import BeautifulSoup

            # Validar URL
            valid, error = self._validate_url(url)
            if not valid:
                return f"Error: {error}"

            # Obtener página
            headers = {"User-Agent": self.USER_AGENT}
            response = httpx.get(url, headers=headers, timeout=self.TIMEOUT, follow_redirects=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Extraer enlaces
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)[:50]  # Limitar texto

                # Convertir a URL absoluta
                absolute_url = urljoin(url, href)

                # Filtrar si hay patrón
                if filter_pattern:
                    if not re.search(filter_pattern, absolute_url, re.IGNORECASE):
                        continue

                links.append((absolute_url, text))

            # Eliminar duplicados manteniendo orden
            seen = set()
            unique_links = []
            for link, text in links:
                if link not in seen:
                    seen.add(link)
                    unique_links.append((link, text))

            if not unique_links:
                return "No se encontraron enlaces."

            result = [f"Enlaces encontrados en {url}:\n"]
            for link, text in unique_links[:50]:  # Limitar a 50
                if text:
                    result.append(f"  • {text}: {link}")
                else:
                    result.append(f"  • {link}")

            if len(unique_links) > 50:
                result.append(f"\n... y {len(unique_links) - 50} enlaces más")

            return "\n".join(result)

        except ImportError as e:
            if "httpx" in str(e):
                return "Error: httpx no instalado. Ejecuta: pip install httpx"
            return "Error: beautifulsoup4 no instalado. Ejecuta: pip install beautifulsoup4"
        except Exception as e:
            return f"Error extrayendo enlaces: {e}"

    def download_file(self, url: str, output_path: Optional[str] = None) -> str:
        """Descarga un archivo de una URL."""
        try:
            import httpx

            # Validar URL
            valid, error = self._validate_url(url)
            if not valid:
                return f"Error: {error}"

            # Determinar nombre de archivo
            if output_path:
                out_path = Path(output_path)
            else:
                # Extraer nombre de la URL
                parsed = urlparse(url)
                filename = Path(parsed.path).name or "downloaded_file"
                out_path = Path(self.output_dir) / filename

            # Crear directorio si no existe
            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Descargar con streaming
            headers = {"User-Agent": self.USER_AGENT}
            with httpx.stream(
                "GET", url, headers=headers, timeout=self.TIMEOUT, follow_redirects=True
            ) as response:
                response.raise_for_status()

                # Verificar tamaño
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > 100_000_000:  # 100MB
                    return "Error: Archivo demasiado grande (>100MB)"

                # Escribir archivo
                total_size = 0
                with open(out_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        total_size += len(chunk)

                        # Límite de seguridad
                        if total_size > 100_000_000:
                            f.close()
                            out_path.unlink()
                            return "Error: Descarga cancelada, archivo demasiado grande"

            size_mb = total_size / (1024 * 1024)
            return f"✅ Archivo descargado: {out_path} ({size_mb:.2f} MB)"

        except ImportError:
            return "Error: httpx no instalado. Ejecuta: pip install httpx"
        except httpx.HTTPStatusError as e:
            return f"Error HTTP {e.response.status_code}"
        except Exception as e:
            return f"Error descargando archivo: {e}"

    def extract_tables(self, url: str) -> str:
        """Extrae tablas de una página web."""
        try:
            import httpx
            from bs4 import BeautifulSoup

            # Validar URL
            valid, error = self._validate_url(url)
            if not valid:
                return f"Error: {error}"

            # Obtener página
            headers = {"User-Agent": self.USER_AGENT}
            response = httpx.get(url, headers=headers, timeout=self.TIMEOUT, follow_redirects=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            tables = soup.find_all("table")

            if not tables:
                return "No se encontraron tablas en la página."

            result = [f"Se encontraron {len(tables)} tabla(s):\n"]

            for i, table in enumerate(tables[:5], 1):  # Máximo 5 tablas
                result.append(f"\n--- Tabla {i} ---")

                rows = table.find_all("tr")
                for row in rows[:20]:  # Máximo 20 filas por tabla
                    cells = row.find_all(["th", "td"])
                    cell_texts = [cell.get_text(strip=True)[:30] for cell in cells]  # Limitar texto
                    result.append(" | ".join(cell_texts))

                if len(rows) > 20:
                    result.append(f"... ({len(rows)} filas total)")

            if len(tables) > 5:
                result.append(f"\n... y {len(tables) - 5} tablas más")

            return "\n".join(result)

        except ImportError as e:
            if "httpx" in str(e):
                return "Error: httpx no instalado. Ejecuta: pip install httpx"
            return "Error: beautifulsoup4 no instalado. Ejecuta: pip install beautifulsoup4"
        except Exception as e:
            return f"Error extrayendo tablas: {e}"

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        url = kwargs.get("url", "")
        if not url:
            return "Error: Se requiere una URL"

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
            return f"Acción no reconocida: {action}"
