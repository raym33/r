"""
Skill de SSH para R CLI.

Conexiones SSH remotas:
- Ejecutar comandos remotos
- Gestionar conexiones
- Transferir archivos (SCP)
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class SSHSkill(Skill):
    """Skill para operaciones SSH."""

    name = "ssh"
    description = "SSH: ejecutar comandos remotos, transferir archivos"

    TIMEOUT = 60

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="ssh_exec",
                description="Ejecuta un comando en un servidor remoto via SSH",
                parameters={
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string",
                            "description": "Host o user@host",
                        },
                        "command": {
                            "type": "string",
                            "description": "Comando a ejecutar",
                        },
                        "port": {
                            "type": "integer",
                            "description": "Puerto SSH (default: 22)",
                        },
                        "identity_file": {
                            "type": "string",
                            "description": "Ruta a la clave privada SSH",
                        },
                    },
                    "required": ["host", "command"],
                },
                handler=self.ssh_exec,
            ),
            Tool(
                name="scp_upload",
                description="Sube un archivo a un servidor remoto",
                parameters={
                    "type": "object",
                    "properties": {
                        "local_path": {
                            "type": "string",
                            "description": "Ruta del archivo local",
                        },
                        "remote_path": {
                            "type": "string",
                            "description": "Destino remoto (user@host:/path)",
                        },
                        "port": {
                            "type": "integer",
                            "description": "Puerto SSH (default: 22)",
                        },
                        "identity_file": {
                            "type": "string",
                            "description": "Ruta a la clave privada SSH",
                        },
                    },
                    "required": ["local_path", "remote_path"],
                },
                handler=self.scp_upload,
            ),
            Tool(
                name="scp_download",
                description="Descarga un archivo de un servidor remoto",
                parameters={
                    "type": "object",
                    "properties": {
                        "remote_path": {
                            "type": "string",
                            "description": "Origen remoto (user@host:/path)",
                        },
                        "local_path": {
                            "type": "string",
                            "description": "Destino local",
                        },
                        "port": {
                            "type": "integer",
                            "description": "Puerto SSH (default: 22)",
                        },
                        "identity_file": {
                            "type": "string",
                            "description": "Ruta a la clave privada SSH",
                        },
                    },
                    "required": ["remote_path"],
                },
                handler=self.scp_download,
            ),
            Tool(
                name="ssh_test",
                description="Prueba la conexión SSH a un servidor",
                parameters={
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string",
                            "description": "Host o user@host",
                        },
                        "port": {
                            "type": "integer",
                            "description": "Puerto SSH (default: 22)",
                        },
                    },
                    "required": ["host"],
                },
                handler=self.ssh_test,
            ),
            Tool(
                name="ssh_keygen",
                description="Genera un nuevo par de claves SSH",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Nombre del archivo de clave (default: id_rsa)",
                        },
                        "type": {
                            "type": "string",
                            "enum": ["rsa", "ed25519", "ecdsa"],
                            "description": "Tipo de clave (default: ed25519)",
                        },
                        "comment": {
                            "type": "string",
                            "description": "Comentario para la clave",
                        },
                    },
                },
                handler=self.ssh_keygen,
            ),
            Tool(
                name="list_ssh_keys",
                description="Lista las claves SSH disponibles",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.list_ssh_keys,
            ),
        ]

    def _build_ssh_args(
        self,
        host: str,
        port: int = 22,
        identity_file: Optional[str] = None,
    ) -> list[str]:
        """Construye argumentos comunes de SSH."""
        args = []

        if port != 22:
            args.extend(["-p", str(port)])

        if identity_file:
            key_path = Path(identity_file).expanduser()
            if key_path.exists():
                args.extend(["-i", str(key_path)])

        # Opciones de seguridad
        args.extend(
            [
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-o",
                "ConnectTimeout=10",
                "-o",
                "BatchMode=yes",
            ]
        )

        return args

    def ssh_exec(
        self,
        host: str,
        command: str,
        port: int = 22,
        identity_file: Optional[str] = None,
    ) -> str:
        """Ejecuta un comando remoto via SSH."""
        try:
            # Validar comando para seguridad básica
            dangerous_patterns = ["rm -rf /", "mkfs", "dd if=/dev/zero", "> /dev/sda"]
            for pattern in dangerous_patterns:
                if pattern in command:
                    return "Error: Comando potencialmente destructivo detectado"

            args = ["ssh"] + self._build_ssh_args(host, port, identity_file)
            args.append(host)
            args.append(command)

            result = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
            )

            output = result.stdout.strip()
            if result.returncode != 0:
                error = result.stderr.strip()
                if "Permission denied" in error:
                    return "Error: Permiso denegado. Verifica tu clave SSH o credenciales."
                elif "Connection refused" in error:
                    return f"Error: Conexión rechazada a {host}:{port}"
                elif "Host key verification failed" in error:
                    return "Error: Verificación de host fallida. Ejecuta 'ssh-keygen -R hostname' si confías en el servidor."
                return f"Error: {error}"

            if not output:
                return "Comando ejecutado (sin output)"

            # Limitar tamaño
            if len(output) > 10000:
                output = output[:10000] + "\n\n... (output truncado)"

            return f"Resultado:\n\n{output}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout ejecutando comando remoto"
        except FileNotFoundError:
            return "Error: SSH no está instalado"
        except Exception as e:
            return f"Error: {e}"

    def scp_upload(
        self,
        local_path: str,
        remote_path: str,
        port: int = 22,
        identity_file: Optional[str] = None,
    ) -> str:
        """Sube un archivo via SCP."""
        try:
            path = Path(local_path).expanduser()

            if not path.exists():
                return f"Error: Archivo local no encontrado: {local_path}"

            # Verificar tamaño
            if path.is_file() and path.stat().st_size > 100 * 1024 * 1024:  # 100MB
                return "Error: Archivo muy grande (>100MB). Usa rsync para archivos grandes."

            args = ["scp", "-r"]

            if port != 22:
                args.extend(["-P", str(port)])

            if identity_file:
                key_path = Path(identity_file).expanduser()
                if key_path.exists():
                    args.extend(["-i", str(key_path)])

            args.extend(
                [
                    "-o",
                    "StrictHostKeyChecking=accept-new",
                    "-o",
                    "ConnectTimeout=10",
                ]
            )

            args.extend([str(path), remote_path])

            result = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutos para transferencia
            )

            if result.returncode == 0:
                return f"✅ Archivo subido: {path.name} -> {remote_path}"
            else:
                return f"Error: {result.stderr.strip()}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout en la transferencia"
        except Exception as e:
            return f"Error: {e}"

    def scp_download(
        self,
        remote_path: str,
        local_path: Optional[str] = None,
        port: int = 22,
        identity_file: Optional[str] = None,
    ) -> str:
        """Descarga un archivo via SCP."""
        try:
            # Determinar destino local
            if local_path:
                dest = Path(local_path).expanduser()
            else:
                # Extraer nombre del archivo remoto
                filename = remote_path.split(":")[-1].split("/")[-1]
                dest = Path(self.output_dir) / filename

            dest.parent.mkdir(parents=True, exist_ok=True)

            args = ["scp", "-r"]

            if port != 22:
                args.extend(["-P", str(port)])

            if identity_file:
                key_path = Path(identity_file).expanduser()
                if key_path.exists():
                    args.extend(["-i", str(key_path)])

            args.extend(
                [
                    "-o",
                    "StrictHostKeyChecking=accept-new",
                    "-o",
                    "ConnectTimeout=10",
                ]
            )

            args.extend([remote_path, str(dest)])

            result = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                return f"✅ Archivo descargado: {dest}"
            else:
                return f"Error: {result.stderr.strip()}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout en la transferencia"
        except Exception as e:
            return f"Error: {e}"

    def ssh_test(self, host: str, port: int = 22) -> str:
        """Prueba la conexión SSH."""
        try:
            args = ["ssh"] + self._build_ssh_args(host, port)
            args.extend([host, "echo 'SSH OK'"])

            result = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )

            if result.returncode == 0:
                return f"✅ Conexión SSH exitosa a {host}:{port}"
            else:
                error = result.stderr.strip()
                if "Permission denied" in error:
                    return f"❌ Autenticación fallida para {host}"
                elif "Connection refused" in error:
                    return f"❌ Conexión rechazada en {host}:{port}"
                elif "Connection timed out" in error:
                    return f"❌ Timeout conectando a {host}"
                return f"❌ Error: {error}"

        except subprocess.TimeoutExpired:
            return f"❌ Timeout conectando a {host}:{port}"
        except Exception as e:
            return f"❌ Error: {e}"

    def ssh_keygen(
        self,
        name: str = "id_ed25519",
        type: str = "ed25519",
        comment: Optional[str] = None,
    ) -> str:
        """Genera un par de claves SSH."""
        try:
            ssh_dir = Path.home() / ".ssh"
            ssh_dir.mkdir(mode=0o700, exist_ok=True)

            key_path = ssh_dir / name

            if key_path.exists():
                return f"Error: La clave ya existe: {key_path}\nUsa un nombre diferente."

            args = [
                "ssh-keygen",
                "-t",
                type,
                "-f",
                str(key_path),
                "-N",
                "",  # Sin passphrase
            ]

            if comment:
                args.extend(["-C", comment])

            result = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                # Leer clave pública
                pub_key = (key_path.with_suffix(".pub")).read_text().strip()

                return f"""✅ Par de claves generado:

Clave privada: {key_path}
Clave pública: {key_path}.pub

Clave pública (para copiar a servidores):
{pub_key}

Para agregar a un servidor:
  ssh-copy-id -i {key_path}.pub user@host
"""
            else:
                return f"Error generando claves: {result.stderr}"

        except Exception as e:
            return f"Error: {e}"

    def list_ssh_keys(self) -> str:
        """Lista las claves SSH disponibles."""
        try:
            ssh_dir = Path.home() / ".ssh"

            if not ssh_dir.exists():
                return "No existe el directorio ~/.ssh"

            keys = []
            for f in ssh_dir.iterdir():
                if f.suffix == ".pub":
                    private_key = f.with_suffix("")
                    if private_key.exists():
                        # Leer tipo de clave
                        content = f.read_text().strip()
                        key_type = content.split()[0] if content else "unknown"
                        keys.append((private_key.name, key_type))

            if not keys:
                return "No se encontraron claves SSH.\n\nGenera una con:\n  ssh-keygen -t ed25519"

            result = ["🔑 Claves SSH disponibles:\n"]
            for name, key_type in sorted(keys):
                result.append(f"  {name} ({key_type})")

            result.append(f"\nUbicación: {ssh_dir}")

            return "\n".join(result)

        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        action = kwargs.get("action", "list_keys")

        if action == "exec":
            host = kwargs.get("host", "")
            command = kwargs.get("command", "")
            if not host or not command:
                return "Error: Se requiere host y command"
            return self.ssh_exec(host, command)
        elif action == "upload":
            return self.scp_upload(kwargs.get("local", ""), kwargs.get("remote", ""))
        elif action == "download":
            return self.scp_download(kwargs.get("remote", ""))
        elif action == "test":
            return self.ssh_test(kwargs.get("host", ""))
        elif action == "keygen":
            return self.ssh_keygen(kwargs.get("name", "id_ed25519"))
        elif action == "list_keys":
            return self.list_ssh_keys()
        else:
            return f"Acción no reconocida: {action}"
