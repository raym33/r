"""
Skill de Git para R CLI.

Operaciones Git comunes:
- Estado del repositorio
- Commits y historial
- Ramas
- Diffs
"""

import subprocess
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class GitSkill(Skill):
    """Skill para operaciones Git."""

    name = "git"
    description = "Operaciones Git: status, log, diff, branches, commits"

    # Timeout para comandos git
    TIMEOUT = 30

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="git_status",
                description="Muestra el estado del repositorio Git",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Ruta del repositorio (default: directorio actual)",
                        },
                    },
                },
                handler=self.git_status,
            ),
            Tool(
                name="git_log",
                description="Muestra el historial de commits",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Ruta del repositorio",
                        },
                        "count": {
                            "type": "integer",
                            "description": "Número de commits a mostrar (default: 10)",
                        },
                        "oneline": {
                            "type": "boolean",
                            "description": "Formato compacto de una línea",
                        },
                    },
                },
                handler=self.git_log,
            ),
            Tool(
                name="git_diff",
                description="Muestra los cambios pendientes o entre commits",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Ruta del repositorio",
                        },
                        "staged": {
                            "type": "boolean",
                            "description": "Mostrar solo cambios staged",
                        },
                        "file": {
                            "type": "string",
                            "description": "Archivo específico para ver diff",
                        },
                    },
                },
                handler=self.git_diff,
            ),
            Tool(
                name="git_branches",
                description="Lista las ramas del repositorio",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Ruta del repositorio",
                        },
                        "all": {
                            "type": "boolean",
                            "description": "Incluir ramas remotas",
                        },
                    },
                },
                handler=self.git_branches,
            ),
            Tool(
                name="git_commit",
                description="Crea un commit con los cambios staged",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Ruta del repositorio",
                        },
                        "message": {
                            "type": "string",
                            "description": "Mensaje del commit",
                        },
                        "add_all": {
                            "type": "boolean",
                            "description": "Agregar todos los archivos modificados antes del commit",
                        },
                    },
                    "required": ["message"],
                },
                handler=self.git_commit,
            ),
            Tool(
                name="git_add",
                description="Agrega archivos al staging area",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Ruta del repositorio",
                        },
                        "files": {
                            "type": "string",
                            "description": "Archivos a agregar (separados por espacio, o '.' para todos)",
                        },
                    },
                    "required": ["files"],
                },
                handler=self.git_add,
            ),
            Tool(
                name="git_info",
                description="Muestra información general del repositorio",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Ruta del repositorio",
                        },
                    },
                },
                handler=self.git_info,
            ),
        ]

    def _run_git(self, args: list[str], cwd: Optional[Path] = None) -> tuple[bool, str]:
        """Ejecuta un comando git de forma segura."""
        try:
            # Comando git base
            cmd = ["git"] + args

            # Ejecutar
            result = subprocess.run(
                cmd,
                check=False,
                cwd=cwd or Path.cwd(),
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
            )

            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip() or "Error desconocido"

        except subprocess.TimeoutExpired:
            return False, "Timeout: el comando tardó demasiado"
        except FileNotFoundError:
            return False, "Git no está instalado o no está en el PATH"
        except Exception as e:
            return False, f"Error ejecutando git: {e}"

    def _get_repo_path(self, path: Optional[str]) -> Path:
        """Obtiene la ruta del repositorio."""
        if path:
            return Path(path).expanduser().resolve()
        return Path.cwd()

    def _is_git_repo(self, path: Path) -> bool:
        """Verifica si la ruta es un repositorio Git."""
        success, _ = self._run_git(["rev-parse", "--git-dir"], cwd=path)
        return success

    def git_status(self, path: Optional[str] = None) -> str:
        """Muestra el estado del repositorio."""
        repo_path = self._get_repo_path(path)

        if not self._is_git_repo(repo_path):
            return f"Error: {repo_path} no es un repositorio Git"

        success, output = self._run_git(["status", "-sb"], cwd=repo_path)

        if success:
            return f"Estado de {repo_path}:\n\n{output}"
        return f"Error: {output}"

    def git_log(
        self,
        path: Optional[str] = None,
        count: int = 10,
        oneline: bool = True,
    ) -> str:
        """Muestra el historial de commits."""
        repo_path = self._get_repo_path(path)

        if not self._is_git_repo(repo_path):
            return f"Error: {repo_path} no es un repositorio Git"

        # Construir argumentos
        args = ["log", f"-{count}"]
        if oneline:
            args.append("--oneline")
        else:
            args.extend(["--format=%h | %an | %ar | %s"])

        success, output = self._run_git(args, cwd=repo_path)

        if success:
            return f"Últimos {count} commits:\n\n{output}"
        return f"Error: {output}"

    def git_diff(
        self,
        path: Optional[str] = None,
        staged: bool = False,
        file: Optional[str] = None,
    ) -> str:
        """Muestra los cambios pendientes."""
        repo_path = self._get_repo_path(path)

        if not self._is_git_repo(repo_path):
            return f"Error: {repo_path} no es un repositorio Git"

        # Construir argumentos
        args = ["diff", "--stat"]
        if staged:
            args.append("--staged")
        if file:
            args.append("--")
            args.append(file)

        success, output = self._run_git(args, cwd=repo_path)

        if success:
            if not output:
                return "No hay cambios pendientes."

            # También obtener diff detallado (limitado)
            detail_args = ["diff"]
            if staged:
                detail_args.append("--staged")
            if file:
                detail_args.append("--")
                detail_args.append(file)

            _, detail = self._run_git(detail_args, cwd=repo_path)

            # Limitar tamaño del diff
            if len(detail) > 5000:
                detail = detail[:5000] + "\n\n... (diff truncado)"

            return f"Resumen de cambios:\n{output}\n\nDetalle:\n{detail}"
        return f"Error: {output}"

    def git_branches(self, path: Optional[str] = None, all: bool = False) -> str:
        """Lista las ramas del repositorio."""
        repo_path = self._get_repo_path(path)

        if not self._is_git_repo(repo_path):
            return f"Error: {repo_path} no es un repositorio Git"

        args = ["branch", "-v"]
        if all:
            args.append("-a")

        success, output = self._run_git(args, cwd=repo_path)

        if success:
            return f"Ramas:\n\n{output}"
        return f"Error: {output}"

    def git_commit(
        self,
        message: str,
        path: Optional[str] = None,
        add_all: bool = False,
    ) -> str:
        """Crea un commit."""
        repo_path = self._get_repo_path(path)

        if not self._is_git_repo(repo_path):
            return f"Error: {repo_path} no es un repositorio Git"

        # Si add_all, primero agregar todos los cambios
        if add_all:
            success, output = self._run_git(["add", "-A"], cwd=repo_path)
            if not success:
                return f"Error agregando archivos: {output}"

        # Verificar que hay algo que commitear
        success, status = self._run_git(["diff", "--staged", "--stat"], cwd=repo_path)
        if success and not status:
            return "No hay cambios en staging para commitear. Usa git_add primero."

        # Crear commit
        success, output = self._run_git(["commit", "-m", message], cwd=repo_path)

        if success:
            return f"✅ Commit creado:\n\n{output}"
        return f"Error creando commit: {output}"

    def git_add(self, files: str, path: Optional[str] = None) -> str:
        """Agrega archivos al staging."""
        repo_path = self._get_repo_path(path)

        if not self._is_git_repo(repo_path):
            return f"Error: {repo_path} no es un repositorio Git"

        # Parsear archivos
        file_list = files.split()

        success, output = self._run_git(["add"] + file_list, cwd=repo_path)

        if success:
            # Mostrar qué se agregó
            _, status = self._run_git(["status", "-s"], cwd=repo_path)
            return f"✅ Archivos agregados al staging:\n\n{status}"
        return f"Error: {output}"

    def git_info(self, path: Optional[str] = None) -> str:
        """Muestra información general del repositorio."""
        repo_path = self._get_repo_path(path)

        if not self._is_git_repo(repo_path):
            return f"Error: {repo_path} no es un repositorio Git"

        info = [f"📂 Repositorio: {repo_path}\n"]

        # Rama actual
        success, branch = self._run_git(["branch", "--show-current"], cwd=repo_path)
        if success:
            info.append(f"🌿 Rama actual: {branch}")

        # Remote
        success, remote = self._run_git(["remote", "-v"], cwd=repo_path)
        if success and remote:
            info.append(f"\n🔗 Remotes:\n{remote}")

        # Último commit
        success, last_commit = self._run_git(
            ["log", "-1", "--format=%h - %s (%ar)"],
            cwd=repo_path,
        )
        if success:
            info.append(f"\n📝 Último commit: {last_commit}")

        # Estadísticas
        success, stats = self._run_git(["rev-list", "--count", "HEAD"], cwd=repo_path)
        if success:
            info.append(f"📊 Total commits: {stats}")

        # Archivos sin trackear
        success, untracked = self._run_git(
            ["status", "--porcelain", "-u"],
            cwd=repo_path,
        )
        if success:
            lines = untracked.split("\n") if untracked else []
            modified = len([l for l in lines if l.startswith(" M") or l.startswith("M ")])
            added = len([l for l in lines if l.startswith("??")])
            staged = len([l for l in lines if l.startswith("A ") or l.startswith("M ")])

            if modified or added or staged:
                info.append("\n📋 Cambios pendientes:")
                if modified:
                    info.append(f"   Modificados: {modified}")
                if staged:
                    info.append(f"   En staging: {staged}")
                if added:
                    info.append(f"   Sin trackear: {added}")

        return "\n".join(info)

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        action = kwargs.get("action", "status")
        path = kwargs.get("path")

        if action == "status":
            return self.git_status(path)
        elif action == "log":
            return self.git_log(path, kwargs.get("count", 10))
        elif action == "diff":
            return self.git_diff(path, kwargs.get("staged", False))
        elif action == "branches":
            return self.git_branches(path, kwargs.get("all", False))
        elif action == "info":
            return self.git_info(path)
        elif action == "add":
            return self.git_add(kwargs.get("files", "."), path)
        elif action == "commit":
            message = kwargs.get("message", "")
            if not message:
                return "Error: Se requiere un mensaje para el commit"
            return self.git_commit(message, path, kwargs.get("add_all", False))
        else:
            return f"Acción no reconocida: {action}"
