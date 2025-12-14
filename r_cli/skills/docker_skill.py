"""
Skill de Docker para R CLI.

Gestión de contenedores Docker:
- Listar contenedores e imágenes
- Ejecutar contenedores
- Ver logs
- Gestionar volúmenes
"""

import json
import subprocess
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class DockerSkill(Skill):
    """Skill para operaciones Docker."""

    name = "docker"
    description = "Gestión de Docker: contenedores, imágenes, volúmenes, logs"

    TIMEOUT = 60

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="docker_ps",
                description="Lista los contenedores Docker",
                parameters={
                    "type": "object",
                    "properties": {
                        "all": {
                            "type": "boolean",
                            "description": "Incluir contenedores detenidos",
                        },
                    },
                },
                handler=self.docker_ps,
            ),
            Tool(
                name="docker_images",
                description="Lista las imágenes Docker",
                parameters={
                    "type": "object",
                    "properties": {
                        "all": {
                            "type": "boolean",
                            "description": "Incluir imágenes intermedias",
                        },
                    },
                },
                handler=self.docker_images,
            ),
            Tool(
                name="docker_run",
                description="Ejecuta un contenedor Docker",
                parameters={
                    "type": "object",
                    "properties": {
                        "image": {
                            "type": "string",
                            "description": "Nombre de la imagen",
                        },
                        "name": {
                            "type": "string",
                            "description": "Nombre del contenedor",
                        },
                        "ports": {
                            "type": "string",
                            "description": "Mapeo de puertos (ej: 8080:80,3000:3000)",
                        },
                        "volumes": {
                            "type": "string",
                            "description": "Mapeo de volúmenes (ej: /host:/container)",
                        },
                        "env": {
                            "type": "string",
                            "description": "Variables de entorno (KEY=value,KEY2=value2)",
                        },
                        "detach": {
                            "type": "boolean",
                            "description": "Ejecutar en background (default: true)",
                        },
                        "command": {
                            "type": "string",
                            "description": "Comando a ejecutar",
                        },
                    },
                    "required": ["image"],
                },
                handler=self.docker_run,
            ),
            Tool(
                name="docker_stop",
                description="Detiene un contenedor",
                parameters={
                    "type": "object",
                    "properties": {
                        "container": {
                            "type": "string",
                            "description": "ID o nombre del contenedor",
                        },
                    },
                    "required": ["container"],
                },
                handler=self.docker_stop,
            ),
            Tool(
                name="docker_logs",
                description="Muestra los logs de un contenedor",
                parameters={
                    "type": "object",
                    "properties": {
                        "container": {
                            "type": "string",
                            "description": "ID o nombre del contenedor",
                        },
                        "tail": {
                            "type": "integer",
                            "description": "Número de líneas (default: 100)",
                        },
                        "follow": {
                            "type": "boolean",
                            "description": "Seguir logs en tiempo real",
                        },
                    },
                    "required": ["container"],
                },
                handler=self.docker_logs,
            ),
            Tool(
                name="docker_exec",
                description="Ejecuta un comando en un contenedor",
                parameters={
                    "type": "object",
                    "properties": {
                        "container": {
                            "type": "string",
                            "description": "ID o nombre del contenedor",
                        },
                        "command": {
                            "type": "string",
                            "description": "Comando a ejecutar",
                        },
                    },
                    "required": ["container", "command"],
                },
                handler=self.docker_exec,
            ),
            Tool(
                name="docker_info",
                description="Muestra información de Docker y el sistema",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.docker_info,
            ),
        ]

    def _run_docker(self, args: list[str], timeout: Optional[int] = None) -> tuple[bool, str]:
        """Ejecuta un comando docker."""
        try:
            cmd = ["docker"] + args
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout or self.TIMEOUT,
            )

            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip() or "Error desconocido"

        except subprocess.TimeoutExpired:
            return False, "Timeout ejecutando comando"
        except FileNotFoundError:
            return False, "Docker no está instalado o no está en el PATH"
        except Exception as e:
            return False, str(e)

    def docker_ps(self, all: bool = False) -> str:
        """Lista contenedores."""
        args = ["ps", "--format", "table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}\t{{.Ports}}"]
        if all:
            args.insert(1, "-a")

        success, output = self._run_docker(args)

        if success:
            if not output or output.count("\n") == 0:
                return "No hay contenedores en ejecución."
            return f"🐳 Contenedores:\n\n{output}"
        return f"Error: {output}"

    def docker_images(self, all: bool = False) -> str:
        """Lista imágenes."""
        args = [
            "images",
            "--format",
            "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}",
        ]
        if all:
            args.insert(1, "-a")

        success, output = self._run_docker(args)

        if success:
            if not output or output.count("\n") == 0:
                return "No hay imágenes Docker."
            return f"🐳 Imágenes:\n\n{output}"
        return f"Error: {output}"

    def docker_run(
        self,
        image: str,
        name: Optional[str] = None,
        ports: Optional[str] = None,
        volumes: Optional[str] = None,
        env: Optional[str] = None,
        detach: bool = True,
        command: Optional[str] = None,
    ) -> str:
        """Ejecuta un contenedor."""
        args = ["run"]

        if detach:
            args.append("-d")

        if name:
            args.extend(["--name", name])

        if ports:
            for port in ports.split(","):
                args.extend(["-p", port.strip()])

        if volumes:
            for vol in volumes.split(","):
                args.extend(["-v", vol.strip()])

        if env:
            for e in env.split(","):
                args.extend(["-e", e.strip()])

        args.append(image)

        if command:
            args.extend(command.split())

        success, output = self._run_docker(args, timeout=120)

        if success:
            container_id = output[:12] if len(output) >= 12 else output
            return f"✅ Contenedor iniciado: {container_id}"
        return f"Error: {output}"

    def docker_stop(self, container: str) -> str:
        """Detiene un contenedor."""
        success, output = self._run_docker(["stop", container])

        if success:
            return f"✅ Contenedor detenido: {container}"
        return f"Error: {output}"

    def docker_logs(
        self,
        container: str,
        tail: int = 100,
        follow: bool = False,
    ) -> str:
        """Muestra logs de un contenedor."""
        args = ["logs", "--tail", str(tail)]

        if follow:
            # No soportamos follow en este contexto
            return "Error: El modo follow no está soportado en este skill. Usa 'docker logs -f' directamente."

        args.append(container)

        success, output = self._run_docker(args)

        if success:
            if not output:
                return "No hay logs disponibles."
            # Limitar tamaño
            if len(output) > 10000:
                output = output[-10000:] + "\n\n... (logs truncados)"
            return f"📋 Logs de {container}:\n\n{output}"
        return f"Error: {output}"

    def docker_exec(self, container: str, command: str) -> str:
        """Ejecuta comando en un contenedor."""
        # Validar comando para seguridad básica
        dangerous_patterns = ["rm -rf /", "mkfs", "dd if="]
        for pattern in dangerous_patterns:
            if pattern in command:
                return "Error: Comando potencialmente peligroso detectado"

        args = ["exec", container] + command.split()

        success, output = self._run_docker(args, timeout=30)

        if success:
            return f"Resultado:\n\n{output}" if output else "Comando ejecutado (sin output)"
        return f"Error: {output}"

    def docker_info(self) -> str:
        """Muestra información de Docker."""
        # Info básica
        success, version = self._run_docker(["version", "--format", "{{.Server.Version}}"])
        if not success:
            return f"Error: Docker no disponible - {version}"

        info = ["🐳 Docker Info\n"]
        info.append(f"Versión: {version}")

        # Contar recursos
        _, containers = self._run_docker(["ps", "-q"])
        running = len(containers.split("\n")) if containers else 0

        _, all_containers = self._run_docker(["ps", "-aq"])
        total = len(all_containers.split("\n")) if all_containers else 0

        _, images = self._run_docker(["images", "-q"])
        num_images = len(images.split("\n")) if images else 0

        info.append(f"Contenedores: {running} corriendo / {total} total")
        info.append(f"Imágenes: {num_images}")

        # Uso de disco
        success, disk = self._run_docker(
            ["system", "df", "--format", "{{.Type}}\t{{.Size}}\t{{.Reclaimable}}"]
        )
        if success and disk:
            info.append("\nUso de disco:")
            for line in disk.split("\n"):
                info.append(f"  {line}")

        return "\n".join(info)

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        action = kwargs.get("action", "ps")

        if action == "ps":
            return self.docker_ps(kwargs.get("all", False))
        elif action == "images":
            return self.docker_images(kwargs.get("all", False))
        elif action == "run":
            image = kwargs.get("image", "")
            if not image:
                return "Error: Se requiere una imagen"
            return self.docker_run(image, **{k: v for k, v in kwargs.items() if k != "action"})
        elif action == "stop":
            return self.docker_stop(kwargs.get("container", ""))
        elif action == "logs":
            return self.docker_logs(kwargs.get("container", ""))
        elif action == "info":
            return self.docker_info()
        else:
            return f"Acción no reconocida: {action}"
