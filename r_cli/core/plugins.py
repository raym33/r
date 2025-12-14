"""
Sistema de Plugins para R CLI.

Permite a la comunidad crear y compartir skills personalizados.

Estructura de un plugin:
~/.r-cli/plugins/
├── my_plugin/
│   ├── plugin.yaml       # Metadatos del plugin
│   ├── __init__.py       # Punto de entrada
│   ├── skill.py          # Implementación del skill
│   └── requirements.txt  # Dependencias opcionales

Formato plugin.yaml:
```yaml
name: my_plugin
version: 1.0.0
description: Mi plugin personalizado
author: Tu Nombre
skills:
  - MyCustomSkill
dependencies:
  - requests>=2.28.0
```
"""

import hashlib
import importlib.util
import logging
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yaml

from r_cli.core.agent import Skill

logger = logging.getLogger(__name__)

# Regex para validar URLs de GitHub
GITHUB_URL_PATTERN = re.compile(r"^https?://github\.com/[\w\-\.]+/[\w\-\.]+/?$")


class PluginStatus(Enum):
    """Estado de un plugin."""

    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    OUTDATED = "outdated"


@dataclass
class PluginMetadata:
    """Metadatos de un plugin."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    homepage: str = ""
    license: str = "MIT"
    skills: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    min_r_cli_version: str = "0.1.0"
    tags: list[str] = field(default_factory=list)

    # Campos internos
    path: Optional[Path] = None
    status: PluginStatus = PluginStatus.INSTALLED
    installed_at: str = ""
    checksum: str = ""


@dataclass
class PluginRegistry:
    """Registro de plugins instalados."""

    plugins: dict[str, PluginMetadata] = field(default_factory=dict)
    last_updated: str = ""


class PluginManager:
    """Gestor de plugins para R CLI."""

    PLUGIN_YAML = "plugin.yaml"
    REGISTRY_FILE = "registry.yaml"

    # Template para crear nuevos plugins
    PLUGIN_TEMPLATE = {
        "plugin.yaml": """name: {name}
version: 1.0.0
description: {description}
author: {author}
skills:
  - {skill_class}
dependencies: []
tags: []
""",
        "__init__.py": '''"""
{name} - Plugin para R CLI.

{description}
"""

from .skill import {skill_class}

__all__ = ["{skill_class}"]
''',
        "skill.py": '''"""
Skill principal del plugin {name}.
"""

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class {skill_class}(Skill):
    """
    {description}

    Ejemplo de uso:
        r {name} --help
    """

    name = "{name}"
    description = "{description}"

    def get_tools(self) -> list[Tool]:
        """Define las herramientas disponibles."""
        return [
            Tool(
                name="{name}_action",
                description="Acción principal del plugin",
                parameters={{
                    "type": "object",
                    "properties": {{
                        "input": {{
                            "type": "string",
                            "description": "Entrada para procesar",
                        }},
                    }},
                    "required": ["input"],
                }},
                handler=self.main_action,
            ),
        ]

    def main_action(self, input: str) -> str:
        """Acción principal del plugin."""
        # TODO: Implementar lógica aquí
        return f"Procesado: {{input}}"

    def execute(self, **kwargs) -> str:
        """Ejecución directa desde CLI."""
        input_text = kwargs.get("input", "")
        if not input_text:
            return f"Plugin {{self.name}} cargado correctamente. Usa --input para procesar."
        return self.main_action(input_text)
''',
        "requirements.txt": """# Dependencias del plugin
# Ejemplo: requests>=2.28.0
""",
        "README.md": """# {name}

{description}

## Instalación

```bash
r plugin install {name}
```

## Uso

```bash
r {name} --input "tu entrada"
```

## Autor

{author}
""",
    }

    def __init__(self, plugins_dir: Optional[Path] = None):
        """Inicializa el gestor de plugins."""
        self.plugins_dir = plugins_dir or Path.home() / ".r-cli" / "plugins"
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

        self.registry_path = self.plugins_dir / self.REGISTRY_FILE
        self.registry = self._load_registry()
        self._loaded_skills: dict[str, type[Skill]] = {}

    def _load_registry(self) -> PluginRegistry:
        """Carga el registro de plugins."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path) as f:
                    data = yaml.safe_load(f) or {}
                    plugins = {}
                    for name, meta in data.get("plugins", {}).items():
                        plugins[name] = PluginMetadata(**meta)
                    return PluginRegistry(
                        plugins=plugins,
                        last_updated=data.get("last_updated", ""),
                    )
            except Exception as e:
                logger.warning(f"Failed to load plugin registry from {self.registry_path}: {e}")
        return PluginRegistry()

    def _save_registry(self):
        """Guarda el registro de plugins."""
        data = {
            "plugins": {
                name: {
                    "name": meta.name,
                    "version": meta.version,
                    "description": meta.description,
                    "author": meta.author,
                    "homepage": meta.homepage,
                    "license": meta.license,
                    "skills": meta.skills,
                    "dependencies": meta.dependencies,
                    "tags": meta.tags,
                    "path": str(meta.path) if meta.path else None,
                    "status": meta.status.value,
                    "installed_at": meta.installed_at,
                    "checksum": meta.checksum,
                }
                for name, meta in self.registry.plugins.items()
            },
            "last_updated": datetime.now().isoformat(),
        }
        with open(self.registry_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def create_plugin(
        self,
        name: str,
        description: str = "Mi plugin personalizado",
        author: str = "",
    ) -> str:
        """Crea un nuevo plugin desde template."""
        # Validar nombre
        if not name.isidentifier():
            return f"Error: Nombre de plugin inválido '{name}'. Usa solo letras, números y guiones bajos."

        plugin_dir = self.plugins_dir / name
        if plugin_dir.exists():
            return f"Error: El plugin '{name}' ya existe en {plugin_dir}"

        try:
            # Crear directorio
            plugin_dir.mkdir(parents=True)

            # Generar nombre de clase
            skill_class = "".join(word.capitalize() for word in name.split("_")) + "Skill"

            # Crear archivos desde template
            for filename, template in self.PLUGIN_TEMPLATE.items():
                content = template.format(
                    name=name,
                    description=description,
                    author=author,
                    skill_class=skill_class,
                )
                (plugin_dir / filename).write_text(content)

            # Registrar plugin
            metadata = PluginMetadata(
                name=name,
                version="1.0.0",
                description=description,
                author=author,
                skills=[skill_class],
                path=plugin_dir,
                status=PluginStatus.INSTALLED,
                installed_at=datetime.now().isoformat(),
            )
            self.registry.plugins[name] = metadata
            self._save_registry()

            return f"""Plugin '{name}' creado exitosamente en:
{plugin_dir}

Archivos creados:
  - plugin.yaml (metadatos)
  - __init__.py (punto de entrada)
  - skill.py (implementación)
  - requirements.txt (dependencias)
  - README.md (documentación)

Próximos pasos:
1. Edita skill.py para implementar tu lógica
2. Añade dependencias en requirements.txt
3. Prueba con: r {name} --input "test"
"""

        except Exception as e:
            # Limpiar si falla
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)
            return f"Error creando plugin: {e}"

    def install_plugin(
        self,
        source: str,
        force: bool = False,
    ) -> str:
        """Instala un plugin desde directorio local o URL."""
        try:
            source_path = Path(source).expanduser()

            # Si es un directorio local
            if source_path.is_dir():
                return self._install_from_directory(source_path, force)

            # Si es una URL de GitHub
            if source.startswith("https://github.com/") or source.startswith("github.com/"):
                return self._install_from_github(source, force)

            # Si es solo un nombre, buscar en directorio de plugins
            local_path = self.plugins_dir / source
            if local_path.is_dir():
                return self._install_from_directory(local_path, force)

            return f"Error: No se encontró el plugin '{source}'"

        except Exception as e:
            return f"Error instalando plugin: {e}"

    def _install_from_directory(self, source: Path, force: bool = False) -> str:
        """Instala plugin desde directorio local."""
        # Verificar plugin.yaml
        plugin_yaml = source / self.PLUGIN_YAML
        if not plugin_yaml.exists():
            return f"Error: No se encontró {self.PLUGIN_YAML} en {source}"

        # Leer metadatos
        with open(plugin_yaml) as f:
            meta_dict = yaml.safe_load(f)

        name = meta_dict.get("name")
        if not name:
            return "Error: plugin.yaml debe contener 'name'"

        # Verificar si ya existe
        if name in self.registry.plugins and not force:
            return f"Plugin '{name}' ya está instalado. Usa --force para reinstalar."

        # Copiar a directorio de plugins si no está ahí
        dest_path = self.plugins_dir / name
        if source != dest_path:
            try:
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                shutil.copytree(source, dest_path)
            except PermissionError:
                return f"Error: Sin permisos para escribir en {dest_path}"
            except OSError as e:
                return f"Error copiando archivos del plugin: {e}"

        # Instalar dependencias
        req_file = dest_path / "requirements.txt"
        if req_file.exists():
            deps_result = self._install_dependencies(req_file)
            if "Error" in deps_result:
                return deps_result

        # Calcular checksum
        checksum = self._calculate_checksum(dest_path)

        # Registrar
        metadata = PluginMetadata(
            name=name,
            version=meta_dict.get("version", "1.0.0"),
            description=meta_dict.get("description", ""),
            author=meta_dict.get("author", ""),
            homepage=meta_dict.get("homepage", ""),
            license=meta_dict.get("license", "MIT"),
            skills=meta_dict.get("skills", []),
            dependencies=meta_dict.get("dependencies", []),
            tags=meta_dict.get("tags", []),
            path=dest_path,
            status=PluginStatus.ENABLED,
            installed_at=datetime.now().isoformat(),
            checksum=checksum,
        )
        self.registry.plugins[name] = metadata
        self._save_registry()

        return f"Plugin '{name}' v{metadata.version} instalado correctamente."

    def _install_from_github(self, url: str, force: bool = False) -> str:
        """Instala plugin desde GitHub."""
        try:
            # Normalizar URL
            if not url.startswith("https://"):
                url = "https://" + url

            # Validar URL de GitHub para seguridad
            if not GITHUB_URL_PATTERN.match(url.rstrip("/")):
                return (
                    f"Error: URL no válida. Solo se permiten URLs de GitHub.\n"
                    f"Formato: https://github.com/usuario/repositorio\n"
                    f"URL recibida: {url}"
                )

            # Verificar que la URL no contenga caracteres peligrosos
            parsed = urlparse(url)
            if any(char in parsed.path for char in [";", "&", "|", "`", "$", "(", ")"]):
                return "Error: URL contiene caracteres no permitidos."

            # Extraer nombre del repo
            parts = url.rstrip("/").split("/")
            repo_name = parts[-1].replace(".git", "")

            # Validar nombre del repo
            if not repo_name or not re.match(r"^[\w\-\.]+$", repo_name):
                return f"Error: Nombre de repositorio inválido: {repo_name}"

            # Clonar a directorio temporal
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                clone_path = Path(tmpdir) / repo_name

                result = subprocess.run(
                    ["git", "clone", "--depth", "1", url, str(clone_path)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,  # Timeout de 2 minutos
                )

                if result.returncode != 0:
                    return f"Error clonando repositorio: {result.stderr}"

                return self._install_from_directory(clone_path, force)

        except subprocess.TimeoutExpired:
            return "Error: Timeout clonando repositorio (>2 minutos)"
        except FileNotFoundError:
            return "Error: Git no está instalado. Instala git para clonar desde GitHub."
        except Exception as e:
            return f"Error instalando desde GitHub: {e}"

    def _install_dependencies(self, req_file: Path) -> str:
        """Instala dependencias de un plugin."""
        try:
            # Leer requirements
            deps = [
                line.strip()
                for line in req_file.read_text().splitlines()
                if line.strip() and not line.startswith("#")
            ]

            if not deps:
                return "OK"

            # Instalar con pip
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet"] + deps,
                check=False,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return f"Error instalando dependencias: {result.stderr}"

            return "OK"

        except Exception as e:
            return f"Error: {e}"

    def _calculate_checksum(self, plugin_dir: Path) -> str:
        """Calcula checksum de un plugin."""
        hasher = hashlib.sha256()
        for file in sorted(plugin_dir.rglob("*.py")):
            hasher.update(file.read_bytes())
        return hasher.hexdigest()[:16]

    def uninstall_plugin(self, name: str) -> str:
        """Desinstala un plugin."""
        if name not in self.registry.plugins:
            return f"Plugin '{name}' no está instalado."

        metadata = self.registry.plugins[name]

        # Eliminar directorio
        if metadata.path and metadata.path.exists():
            try:
                shutil.rmtree(metadata.path)
            except PermissionError:
                return f"Error: Sin permisos para eliminar {metadata.path}"
            except OSError as e:
                return f"Error eliminando archivos del plugin: {e}"

        # Eliminar del registro
        del self.registry.plugins[name]
        try:
            self._save_registry()
        except OSError as e:
            return f"Error guardando registro: {e}"

        # Eliminar de skills cargados
        if name in self._loaded_skills:
            del self._loaded_skills[name]

        return f"Plugin '{name}' desinstalado correctamente."

    def enable_plugin(self, name: str) -> str:
        """Habilita un plugin."""
        if name not in self.registry.plugins:
            return f"Plugin '{name}' no está instalado."

        self.registry.plugins[name].status = PluginStatus.ENABLED
        self._save_registry()
        return f"Plugin '{name}' habilitado."

    def disable_plugin(self, name: str) -> str:
        """Deshabilita un plugin."""
        if name not in self.registry.plugins:
            return f"Plugin '{name}' no está instalado."

        self.registry.plugins[name].status = PluginStatus.DISABLED
        self._save_registry()
        return f"Plugin '{name}' deshabilitado."

    def list_plugins(self) -> str:
        """Lista todos los plugins instalados."""
        if not self.registry.plugins:
            return "No hay plugins instalados.\n\nPara crear uno: r plugin create mi_plugin"

        result = ["Plugins instalados:\n"]

        for name, meta in sorted(self.registry.plugins.items()):
            status_icon = {
                PluginStatus.ENABLED: "[+]",
                PluginStatus.DISABLED: "[-]",
                PluginStatus.ERROR: "[!]",
                PluginStatus.OUTDATED: "[~]",
            }.get(meta.status, "[?]")

            result.append(f"  {status_icon} {name} v{meta.version}")
            result.append(f"      {meta.description}")
            if meta.skills:
                result.append(f"      Skills: {', '.join(meta.skills)}")
            if meta.author:
                result.append(f"      Autor: {meta.author}")
            result.append("")

        result.append("Comandos:")
        result.append("  r plugin create <nombre>  - Crear nuevo plugin")
        result.append("  r plugin install <ruta>   - Instalar plugin")
        result.append("  r plugin enable <nombre>  - Habilitar plugin")
        result.append("  r plugin disable <nombre> - Deshabilitar plugin")
        result.append("  r plugin remove <nombre>  - Desinstalar plugin")

        return "\n".join(result)

    def get_plugin_info(self, name: str) -> str:
        """Obtiene información detallada de un plugin."""
        if name not in self.registry.plugins:
            return f"Plugin '{name}' no está instalado."

        meta = self.registry.plugins[name]

        result = [
            f"Plugin: {meta.name}",
            f"Versión: {meta.version}",
            f"Estado: {meta.status.value}",
            f"Descripción: {meta.description}",
            f"Autor: {meta.author}",
            f"Licencia: {meta.license}",
            f"Skills: {', '.join(meta.skills)}",
            f"Dependencias: {', '.join(meta.dependencies) or 'ninguna'}",
            f"Tags: {', '.join(meta.tags) or 'ninguno'}",
            f"Instalado: {meta.installed_at}",
            f"Ruta: {meta.path}",
            f"Checksum: {meta.checksum}",
        ]

        if meta.homepage:
            result.append(f"Homepage: {meta.homepage}")

        return "\n".join(result)

    def load_plugin_skills(self) -> dict[str, type[Skill]]:
        """Carga los skills de todos los plugins habilitados."""
        loaded = {}

        for name, meta in self.registry.plugins.items():
            if meta.status != PluginStatus.ENABLED:
                continue

            if not meta.path or not meta.path.exists():
                meta.status = PluginStatus.ERROR
                continue

            try:
                # Añadir al path si no está
                plugin_path = str(meta.path)
                if plugin_path not in sys.path:
                    sys.path.insert(0, str(meta.path.parent))

                # Importar módulo
                spec = importlib.util.spec_from_file_location(
                    name,
                    meta.path / "__init__.py",
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)

                # Cargar skills
                for skill_name in meta.skills:
                    if hasattr(module, skill_name):
                        skill_class = getattr(module, skill_name)
                        if isinstance(skill_class, type) and issubclass(skill_class, Skill):
                            loaded[name] = skill_class
                            self._loaded_skills[name] = skill_class

            except Exception as e:
                meta.status = PluginStatus.ERROR
                print(f"Error cargando plugin '{name}': {e}")

        self._save_registry()
        return loaded

    def get_loaded_skills(self) -> dict[str, type[Skill]]:
        """Retorna los skills ya cargados."""
        if not self._loaded_skills:
            self.load_plugin_skills()
        return self._loaded_skills

    def validate_plugin(self, plugin_dir: Path) -> tuple[bool, str]:
        """Valida la estructura de un plugin."""
        errors = []

        # Verificar plugin.yaml
        plugin_yaml = plugin_dir / self.PLUGIN_YAML
        if not plugin_yaml.exists():
            errors.append(f"Falta {self.PLUGIN_YAML}")
        else:
            try:
                with open(plugin_yaml) as f:
                    meta = yaml.safe_load(f)
                if not meta.get("name"):
                    errors.append("plugin.yaml: falta 'name'")
                if not meta.get("version"):
                    errors.append("plugin.yaml: falta 'version'")
                if not meta.get("skills"):
                    errors.append("plugin.yaml: falta 'skills'")
            except Exception as e:
                errors.append(f"plugin.yaml inválido: {e}")

        # Verificar __init__.py
        init_file = plugin_dir / "__init__.py"
        if not init_file.exists():
            errors.append("Falta __init__.py")

        # Verificar skill.py
        skill_file = plugin_dir / "skill.py"
        if not skill_file.exists():
            errors.append("Falta skill.py")

        if errors:
            return False, "Errores de validación:\n" + "\n".join(f"  - {e}" for e in errors)

        return True, "Plugin válido"
