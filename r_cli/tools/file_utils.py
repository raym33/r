"""
Utilidades de manejo de archivos.
"""

import os
from pathlib import Path
from typing import Optional
import mimetypes


def safe_path(path: str, base_dir: Optional[str] = None) -> Path:
    """
    Valida y normaliza una ruta de archivo.

    Args:
        path: Ruta a validar
        base_dir: Directorio base permitido (para seguridad)

    Returns:
        Path normalizado

    Raises:
        ValueError: Si la ruta es inválida o fuera del base_dir
    """
    # Expandir ~ y variables de entorno
    expanded = os.path.expanduser(os.path.expandvars(path))
    normalized = Path(expanded).resolve()

    # Verificar que está dentro del base_dir si se especifica
    if base_dir:
        base = Path(os.path.expanduser(base_dir)).resolve()
        try:
            normalized.relative_to(base)
        except ValueError:
            raise ValueError(f"Ruta fuera del directorio permitido: {path}")

    return normalized


def ensure_dir(path: str) -> Path:
    """
    Crea un directorio si no existe.

    Returns:
        Path del directorio creado/existente
    """
    dir_path = Path(os.path.expanduser(path))
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_file_type(path: str) -> dict:
    """
    Detecta el tipo de archivo.

    Returns:
        Dict con: extension, mime_type, category, is_text
    """
    file_path = Path(path)
    extension = file_path.suffix.lower()

    # Obtener MIME type
    mime_type, _ = mimetypes.guess_type(str(file_path))

    # Categorías conocidas
    categories = {
        ".py": ("Python", True),
        ".js": ("JavaScript", True),
        ".ts": ("TypeScript", True),
        ".html": ("HTML", True),
        ".css": ("CSS", True),
        ".json": ("JSON", True),
        ".yaml": ("YAML", True),
        ".yml": ("YAML", True),
        ".md": ("Markdown", True),
        ".txt": ("Text", True),
        ".csv": ("CSV", True),
        ".sql": ("SQL", True),
        ".sh": ("Shell", True),
        ".bash": ("Bash", True),
        ".pdf": ("PDF", False),
        ".doc": ("Word", False),
        ".docx": ("Word", False),
        ".xls": ("Excel", False),
        ".xlsx": ("Excel", False),
        ".png": ("Image", False),
        ".jpg": ("Image", False),
        ".jpeg": ("Image", False),
        ".gif": ("Image", False),
        ".svg": ("SVG", True),
        ".zip": ("Archive", False),
        ".tar": ("Archive", False),
        ".gz": ("Archive", False),
    }

    category, is_text = categories.get(extension, ("Unknown", False))

    # Si no está en la lista, intentar detectar por MIME
    if category == "Unknown" and mime_type:
        if mime_type.startswith("text/"):
            is_text = True
            category = "Text"
        elif mime_type.startswith("image/"):
            category = "Image"
        elif mime_type.startswith("audio/"):
            category = "Audio"
        elif mime_type.startswith("video/"):
            category = "Video"
        elif mime_type.startswith("application/"):
            category = "Application"

    return {
        "extension": extension,
        "mime_type": mime_type or "application/octet-stream",
        "category": category,
        "is_text": is_text,
    }


def format_size(size_bytes: int) -> str:
    """Formatea tamaño de archivo a legible humano."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def list_files_recursive(
    directory: str,
    pattern: str = "*",
    max_depth: int = 10,
    include_hidden: bool = False,
) -> list[Path]:
    """
    Lista archivos recursivamente.

    Args:
        directory: Directorio raíz
        pattern: Patrón glob
        max_depth: Profundidad máxima
        include_hidden: Incluir archivos ocultos

    Returns:
        Lista de paths
    """
    root = Path(directory)
    if not root.exists():
        return []

    results = []

    def walk(current: Path, depth: int):
        if depth > max_depth:
            return

        try:
            for item in current.iterdir():
                # Saltar ocultos si no se piden
                if not include_hidden and item.name.startswith("."):
                    continue

                if item.is_file():
                    if item.match(pattern):
                        results.append(item)
                elif item.is_dir():
                    walk(item, depth + 1)
        except PermissionError:
            pass

    walk(root, 0)
    return sorted(results)


def read_file_safe(path: str, max_size: int = 10_000_000) -> tuple[str, Optional[str]]:
    """
    Lee archivo con límites de seguridad.

    Returns:
        Tuple de (contenido, error). Si hay error, contenido es "".
    """
    try:
        file_path = Path(path)

        if not file_path.exists():
            return "", f"Archivo no encontrado: {path}"

        if not file_path.is_file():
            return "", f"No es un archivo: {path}"

        size = file_path.stat().st_size
        if size > max_size:
            return "", f"Archivo muy grande: {format_size(size)} (máx: {format_size(max_size)})"

        file_type = get_file_type(path)
        if not file_type["is_text"]:
            return "", f"No es un archivo de texto: {file_type['category']}"

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        return content, None

    except PermissionError:
        return "", f"Sin permisos para leer: {path}"
    except Exception as e:
        return "", f"Error leyendo archivo: {e}"
