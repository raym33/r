"""
Docker Skill for R CLI.

Docker container management:
- List containers and images
- Run containers
- View logs
- Manage volumes
"""

import subprocess
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class DockerSkill(Skill):
    """Skill for Docker operations."""

    name = "docker"
    description = "Docker management: containers, images, volumes, logs"

    TIMEOUT = 60

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="docker_ps",
                description="List Docker containers",
                parameters={
                    "type": "object",
                    "properties": {
                        "all": {
                            "type": "boolean",
                            "description": "Include stopped containers",
                        },
                    },
                },
                handler=self.docker_ps,
            ),
            Tool(
                name="docker_images",
                description="List Docker images",
                parameters={
                    "type": "object",
                    "properties": {
                        "all": {
                            "type": "boolean",
                            "description": "Include intermediate images",
                        },
                    },
                },
                handler=self.docker_images,
            ),
            Tool(
                name="docker_run",
                description="Run a Docker container",
                parameters={
                    "type": "object",
                    "properties": {
                        "image": {
                            "type": "string",
                            "description": "Image name",
                        },
                        "name": {
                            "type": "string",
                            "description": "Container name",
                        },
                        "ports": {
                            "type": "string",
                            "description": "Port mapping (e.g., 8080:80,3000:3000)",
                        },
                        "volumes": {
                            "type": "string",
                            "description": "Volume mapping (e.g., /host:/container)",
                        },
                        "env": {
                            "type": "string",
                            "description": "Environment variables (KEY=value,KEY2=value2)",
                        },
                        "detach": {
                            "type": "boolean",
                            "description": "Run in background (default: true)",
                        },
                        "command": {
                            "type": "string",
                            "description": "Command to execute",
                        },
                    },
                    "required": ["image"],
                },
                handler=self.docker_run,
            ),
            Tool(
                name="docker_stop",
                description="Stop a container",
                parameters={
                    "type": "object",
                    "properties": {
                        "container": {
                            "type": "string",
                            "description": "Container ID or name",
                        },
                    },
                    "required": ["container"],
                },
                handler=self.docker_stop,
            ),
            Tool(
                name="docker_logs",
                description="Show container logs",
                parameters={
                    "type": "object",
                    "properties": {
                        "container": {
                            "type": "string",
                            "description": "Container ID or name",
                        },
                        "tail": {
                            "type": "integer",
                            "description": "Number of lines (default: 100)",
                        },
                        "follow": {
                            "type": "boolean",
                            "description": "Follow logs in real time",
                        },
                    },
                    "required": ["container"],
                },
                handler=self.docker_logs,
            ),
            Tool(
                name="docker_exec",
                description="Execute a command in a container",
                parameters={
                    "type": "object",
                    "properties": {
                        "container": {
                            "type": "string",
                            "description": "Container ID or name",
                        },
                        "command": {
                            "type": "string",
                            "description": "Command to execute",
                        },
                    },
                    "required": ["container", "command"],
                },
                handler=self.docker_exec,
            ),
            Tool(
                name="docker_info",
                description="Show Docker and system information",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.docker_info,
            ),
        ]

    def _run_docker(self, args: list[str], timeout: Optional[int] = None) -> tuple[bool, str]:
        """Execute a docker command."""
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
                return False, result.stderr.strip() or "Unknown error"

        except subprocess.TimeoutExpired:
            return False, "Timeout executing command"
        except FileNotFoundError:
            return False, "Docker is not installed or not in PATH"
        except Exception as e:
            return False, str(e)

    def docker_ps(self, all: bool = False) -> str:
        """List containers."""
        args = ["ps", "--format", "table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}\t{{.Ports}}"]
        if all:
            args.insert(1, "-a")

        success, output = self._run_docker(args)

        if success:
            if not output or output.count("\n") == 0:
                return "No running containers."
            return f"Containers:\n\n{output}"
        return f"Error: {output}"

    def docker_images(self, all: bool = False) -> str:
        """List images."""
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
                return "No Docker images."
            return f"Images:\n\n{output}"
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
        """Run a container."""
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
            return f"Container started: {container_id}"
        return f"Error: {output}"

    def docker_stop(self, container: str) -> str:
        """Stop a container."""
        success, output = self._run_docker(["stop", container])

        if success:
            return f"Container stopped: {container}"
        return f"Error: {output}"

    def docker_logs(
        self,
        container: str,
        tail: int = 100,
        follow: bool = False,
    ) -> str:
        """Show container logs."""
        args = ["logs", "--tail", str(tail)]

        if follow:
            # Follow not supported in this context
            return (
                "Error: Follow mode is not supported in this skill. Use 'docker logs -f' directly."
            )

        args.append(container)

        success, output = self._run_docker(args)

        if success:
            if not output:
                return "No logs available."
            # Limit size
            if len(output) > 10000:
                output = output[-10000:] + "\n\n... (logs truncated)"
            return f"Logs for {container}:\n\n{output}"
        return f"Error: {output}"

    def docker_exec(self, container: str, command: str) -> str:
        """Execute command in a container."""
        # Validate command for basic security
        dangerous_patterns = ["rm -rf /", "mkfs", "dd if="]
        for pattern in dangerous_patterns:
            if pattern in command:
                return "Error: Potentially dangerous command detected"

        args = ["exec", container] + command.split()

        success, output = self._run_docker(args, timeout=30)

        if success:
            return f"Result:\n\n{output}" if output else "Command executed (no output)"
        return f"Error: {output}"

    def docker_info(self) -> str:
        """Show Docker information."""
        # Basic info
        success, version = self._run_docker(["version", "--format", "{{.Server.Version}}"])
        if not success:
            return f"Error: Docker not available - {version}"

        info = ["Docker Info\n"]
        info.append(f"Version: {version}")

        # Count resources
        _, containers = self._run_docker(["ps", "-q"])
        running = len(containers.split("\n")) if containers else 0

        _, all_containers = self._run_docker(["ps", "-aq"])
        total = len(all_containers.split("\n")) if all_containers else 0

        _, images = self._run_docker(["images", "-q"])
        num_images = len(images.split("\n")) if images else 0

        info.append(f"Containers: {running} running / {total} total")
        info.append(f"Images: {num_images}")

        # Disk usage
        success, disk = self._run_docker(
            ["system", "df", "--format", "{{.Type}}\t{{.Size}}\t{{.Reclaimable}}"]
        )
        if success and disk:
            info.append("\nDisk usage:")
            for line in disk.split("\n"):
                info.append(f"  {line}")

        return "\n".join(info)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "ps")

        if action == "ps":
            return self.docker_ps(kwargs.get("all", False))
        elif action == "images":
            return self.docker_images(kwargs.get("all", False))
        elif action == "run":
            image = kwargs.get("image", "")
            if not image:
                return "Error: image is required"
            return self.docker_run(image, **{k: v for k, v in kwargs.items() if k != "action"})
        elif action == "stop":
            return self.docker_stop(kwargs.get("container", ""))
        elif action == "logs":
            return self.docker_logs(kwargs.get("container", ""))
        elif action == "info":
            return self.docker_info()
        else:
            return f"Unrecognized action: {action}"
