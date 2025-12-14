"""
Skill de Filesystem para R CLI.

Operaciones seguras de archivos:
- Listar directorios
- Leer archivos
- Escribir archivos
- Buscar archivos
"""

import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class FilesystemSkill(Skill):
    """Skill para operaciones de filesystem."""

    name = "fs"
    description = "Operaciones de archivos: listar, leer, escribir, buscar"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="list_directory",
                description="Lista archivos y carpetas en un directorio",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Ruta del directorio (default: directorio actual)",
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Patrón glob para filtrar (ej: *.pdf, *.py)",
                        },
                    },
                },
                handler=self.list_directory,
            ),
            Tool(
                name="read_file",
                description="Lee el contenido de un archivo de texto",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Ruta del archivo a leer",
                        },
                        "max_lines": {
                            "type": "integer",
                            "description": "Máximo de líneas a leer (default: 100)",
                        },
                    },
                    "required": ["path"],
                },
                handler=self.read_file,
            ),
            Tool(
                name="write_file",
                description="Escribe contenido a un archivo",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Ruta donde guardar el archivo",
                        },
                        "content": {
                            "type": "string",
                            "description": "Contenido a escribir",
                        },
                        "append": {
                            "type": "boolean",
                            "description": "Si agregar al final en vez de sobrescribir",
                        },
                    },
                    "required": ["path", "content"],
                },
                handler=self.write_file,
            ),
            Tool(
                name="search_files",
                description="Busca archivos por nombre o contenido",
                parameters={
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directorio donde buscar",
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Patrón de nombre (ej: *.py, report*)",
                        },
                        "content": {
                            "type": "string",
                            "description": "Texto a buscar dentro de archivos",
                        },
                    },
                    "required": ["directory"],
                },
                handler=self.search_files,
            ),
            Tool(
                name="file_info",
                description="Obtiene información de un archivo (tamaño, fecha, tipo)",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Ruta del archivo",
                        },
                    },
                    "required": ["path"],
                },
                handler=self.file_info,
            ),
        ]

    def list_directory(
        self, path: Optional[str] = None, pattern: Optional[str] = None
    ) -> str:
        """Lista contenido de un directorio."""
        try:
            dir_path = Path(path) if path else Path.cwd()

            if not dir_path.exists():
                return f"Error: El directorio no existe: {dir_path}"

            if not dir_path.is_dir():
                return f"Error: No es un directorio: {dir_path}"

            # Obtener archivos
            if pattern:
                items = list(dir_path.glob(pattern))
            else:
                items = list(dir_path.iterdir())

            # Ordenar: carpetas primero, luego archivos
            dirs = sorted([i for i in items if i.is_dir()])
            files = sorted([i for i in items if i.is_file()])

            result = [f"Contenido de: {dir_path}\n"]

            if dirs:
                result.append("📁 Carpetas:")
                for d in dirs[:20]:  # Limitar a 20
                    result.append(f"  {d.name}/")

            if files:
                result.append("\n📄 Archivos:")
                for f in files[:30]:  # Limitar a 30
                    size = f.stat().st_size
                    size_str = self._format_size(size)
                    result.append(f"  {f.name} ({size_str})")

            if len(dirs) > 20 or len(files) > 30:
                result.append(f"\n... y más ({len(dirs)} carpetas, {len(files)} archivos total)")

            return "\n".join(result)

        except PermissionError:
            return f"Error: Sin permisos para acceder a {path}"
        except Exception as e:
            return f"Error listando directorio: {e}"

    def read_file(self, path: str, max_lines: int = 100) -> str:
        """Lee contenido de un archivo."""
        try:
            file_path = Path(path)

            if not file_path.exists():
                return f"Error: Archivo no encontrado: {path}"

            if not file_path.is_file():
                return f"Error: No es un archivo: {path}"

            # Verificar tamaño
            size = file_path.stat().st_size
            if size > 1_000_000:  # 1MB
                return f"Error: Archivo muy grande ({self._format_size(size)}). Usa max_lines para leer parcialmente."

            # Leer
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            if len(lines) > max_lines:
                content = "".join(lines[:max_lines])
                return f"{content}\n\n... (mostrando {max_lines} de {len(lines)} líneas)"
            else:
                return "".join(lines)

        except UnicodeDecodeError:
            return f"Error: El archivo no es texto legible (puede ser binario)"
        except PermissionError:
            return f"Error: Sin permisos para leer {path}"
        except Exception as e:
            return f"Error leyendo archivo: {e}"

    def write_file(self, path: str, content: str, append: bool = False) -> str:
        """Escribe contenido a un archivo."""
        try:
            file_path = Path(path)

            # Crear directorio padre si no existe
            file_path.parent.mkdir(parents=True, exist_ok=True)

            mode = "a" if append else "w"
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(content)

            action = "agregado a" if append else "escrito en"
            return f"✅ Contenido {action}: {file_path}"

        except PermissionError:
            return f"Error: Sin permisos para escribir en {path}"
        except Exception as e:
            return f"Error escribiendo archivo: {e}"

    def search_files(
        self,
        directory: str,
        pattern: Optional[str] = None,
        content: Optional[str] = None,
    ) -> str:
        """Busca archivos por nombre o contenido."""
        try:
            dir_path = Path(directory)

            if not dir_path.exists():
                return f"Error: Directorio no existe: {directory}"

            # Buscar por patrón de nombre
            if pattern:
                matches = list(dir_path.rglob(pattern))[:50]  # Limitar resultados
            else:
                matches = list(dir_path.rglob("*"))[:100]

            # Filtrar solo archivos
            matches = [m for m in matches if m.is_file()]

            # Si hay búsqueda de contenido, filtrar
            if content:
                content_matches = []
                for match in matches:
                    try:
                        with open(match, "r", encoding="utf-8", errors="ignore") as f:
                            if content.lower() in f.read().lower():
                                content_matches.append(match)
                    except Exception:
                        continue
                matches = content_matches

            if not matches:
                return "No se encontraron archivos que coincidan."

            result = [f"Encontrados {len(matches)} archivos:\n"]
            for m in matches[:20]:
                rel_path = m.relative_to(dir_path) if dir_path in m.parents else m
                result.append(f"  📄 {rel_path}")

            if len(matches) > 20:
                result.append(f"\n  ... y {len(matches) - 20} más")

            return "\n".join(result)

        except Exception as e:
            return f"Error buscando: {e}"

    def file_info(self, path: str) -> str:
        """Obtiene información detallada de un archivo."""
        try:
            file_path = Path(path)

            if not file_path.exists():
                return f"Error: No existe: {path}"

            stat = file_path.stat()

            info = [
                f"📄 Información de: {file_path.name}",
                f"",
                f"Ruta completa: {file_path.absolute()}",
                f"Tipo: {'Directorio' if file_path.is_dir() else 'Archivo'}",
                f"Tamaño: {self._format_size(stat.st_size)}",
                f"Modificado: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}",
                f"Creado: {datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}",
            ]

            if file_path.is_file():
                info.append(f"Extensión: {file_path.suffix or '(sin extensión)'}")

                # Contar líneas si es texto
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = sum(1 for _ in f)
                    info.append(f"Líneas: {lines}")
                except Exception:
                    pass

            return "\n".join(info)

        except Exception as e:
            return f"Error obteniendo info: {e}"

    def _format_size(self, size: int) -> str:
        """Formatea tamaño en bytes a formato legible."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        action = kwargs.get("action", "list")

        if action == "list":
            return self.list_directory(kwargs.get("path"))
        elif action == "read":
            return self.read_file(kwargs.get("path", ""))
        elif action == "write":
            return self.write_file(kwargs.get("path", ""), kwargs.get("content", ""))
        elif action == "search":
            return self.search_files(kwargs.get("directory", "."), kwargs.get("pattern"))
        else:
            return f"Acción no reconocida: {action}"
