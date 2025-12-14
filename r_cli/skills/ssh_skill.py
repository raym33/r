"""
SSH Skill for R CLI.

Remote SSH connections:
- Execute remote commands
- Manage connections
- Transfer files (SCP)
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class SSHSkill(Skill):
    """Skill for SSH operations."""

    name = "ssh"
    description = "SSH: execute remote commands, transfer files"

    TIMEOUT = 60

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="ssh_exec",
                description="Execute a command on a remote server via SSH",
                parameters={
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string",
                            "description": "Host or user@host",
                        },
                        "command": {
                            "type": "string",
                            "description": "Command to execute",
                        },
                        "port": {
                            "type": "integer",
                            "description": "SSH port (default: 22)",
                        },
                        "identity_file": {
                            "type": "string",
                            "description": "Path to SSH private key",
                        },
                    },
                    "required": ["host", "command"],
                },
                handler=self.ssh_exec,
            ),
            Tool(
                name="scp_upload",
                description="Upload a file to a remote server",
                parameters={
                    "type": "object",
                    "properties": {
                        "local_path": {
                            "type": "string",
                            "description": "Local file path",
                        },
                        "remote_path": {
                            "type": "string",
                            "description": "Remote destination (user@host:/path)",
                        },
                        "port": {
                            "type": "integer",
                            "description": "SSH port (default: 22)",
                        },
                        "identity_file": {
                            "type": "string",
                            "description": "Path to SSH private key",
                        },
                    },
                    "required": ["local_path", "remote_path"],
                },
                handler=self.scp_upload,
            ),
            Tool(
                name="scp_download",
                description="Download a file from a remote server",
                parameters={
                    "type": "object",
                    "properties": {
                        "remote_path": {
                            "type": "string",
                            "description": "Remote source (user@host:/path)",
                        },
                        "local_path": {
                            "type": "string",
                            "description": "Local destination",
                        },
                        "port": {
                            "type": "integer",
                            "description": "SSH port (default: 22)",
                        },
                        "identity_file": {
                            "type": "string",
                            "description": "Path to SSH private key",
                        },
                    },
                    "required": ["remote_path"],
                },
                handler=self.scp_download,
            ),
            Tool(
                name="ssh_test",
                description="Test SSH connection to a server",
                parameters={
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string",
                            "description": "Host or user@host",
                        },
                        "port": {
                            "type": "integer",
                            "description": "SSH port (default: 22)",
                        },
                    },
                    "required": ["host"],
                },
                handler=self.ssh_test,
            ),
            Tool(
                name="ssh_keygen",
                description="Generate a new SSH key pair",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Key file name (default: id_rsa)",
                        },
                        "type": {
                            "type": "string",
                            "enum": ["rsa", "ed25519", "ecdsa"],
                            "description": "Key type (default: ed25519)",
                        },
                        "comment": {
                            "type": "string",
                            "description": "Comment for the key",
                        },
                    },
                },
                handler=self.ssh_keygen,
            ),
            Tool(
                name="list_ssh_keys",
                description="List available SSH keys",
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
        """Build common SSH arguments."""
        args = []

        if port != 22:
            args.extend(["-p", str(port)])

        if identity_file:
            key_path = Path(identity_file).expanduser()
            if key_path.exists():
                args.extend(["-i", str(key_path)])

        # Security options
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
        """Execute a remote command via SSH."""
        try:
            # Validate command for basic security
            dangerous_patterns = ["rm -rf /", "mkfs", "dd if=/dev/zero", "> /dev/sda"]
            for pattern in dangerous_patterns:
                if pattern in command:
                    return "Error: Potentially destructive command detected"

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
                    return "Error: Permission denied. Check your SSH key or credentials."
                elif "Connection refused" in error:
                    return f"Error: Connection refused at {host}:{port}"
                elif "Host key verification failed" in error:
                    return "Error: Host key verification failed. Run 'ssh-keygen -R hostname' if you trust the server."
                return f"Error: {error}"

            if not output:
                return "Command executed (no output)"

            # Limit size
            if len(output) > 10000:
                output = output[:10000] + "\n\n... (output truncated)"

            return f"Result:\n\n{output}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout executing remote command"
        except FileNotFoundError:
            return "Error: SSH is not installed"
        except Exception as e:
            return f"Error: {e}"

    def scp_upload(
        self,
        local_path: str,
        remote_path: str,
        port: int = 22,
        identity_file: Optional[str] = None,
    ) -> str:
        """Upload a file via SCP."""
        try:
            path = Path(local_path).expanduser()

            if not path.exists():
                return f"Error: Local file not found: {local_path}"

            # Check size
            if path.is_file() and path.stat().st_size > 100 * 1024 * 1024:  # 100MB
                return "Error: File too large (>100MB). Use rsync for large files."

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
                timeout=300,  # 5 minutes for transfer
            )

            if result.returncode == 0:
                return f"File uploaded: {path.name} -> {remote_path}"
            else:
                return f"Error: {result.stderr.strip()}"

        except subprocess.TimeoutExpired:
            return "Error: Transfer timeout"
        except Exception as e:
            return f"Error: {e}"

    def scp_download(
        self,
        remote_path: str,
        local_path: Optional[str] = None,
        port: int = 22,
        identity_file: Optional[str] = None,
    ) -> str:
        """Download a file via SCP."""
        try:
            # Determine local destination
            if local_path:
                dest = Path(local_path).expanduser()
            else:
                # Extract filename from remote path
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
                return f"File downloaded: {dest}"
            else:
                return f"Error: {result.stderr.strip()}"

        except subprocess.TimeoutExpired:
            return "Error: Transfer timeout"
        except Exception as e:
            return f"Error: {e}"

    def ssh_test(self, host: str, port: int = 22) -> str:
        """Test SSH connection."""
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
                return f"SSH connection successful to {host}:{port}"
            else:
                error = result.stderr.strip()
                if "Permission denied" in error:
                    return f"Authentication failed for {host}"
                elif "Connection refused" in error:
                    return f"Connection refused at {host}:{port}"
                elif "Connection timed out" in error:
                    return f"Timeout connecting to {host}"
                return f"Error: {error}"

        except subprocess.TimeoutExpired:
            return f"Timeout connecting to {host}:{port}"
        except Exception as e:
            return f"Error: {e}"

    def ssh_keygen(
        self,
        name: str = "id_ed25519",
        type: str = "ed25519",
        comment: Optional[str] = None,
    ) -> str:
        """Generate an SSH key pair."""
        try:
            ssh_dir = Path.home() / ".ssh"
            ssh_dir.mkdir(mode=0o700, exist_ok=True)

            key_path = ssh_dir / name

            if key_path.exists():
                return f"Error: Key already exists: {key_path}\nUse a different name."

            args = [
                "ssh-keygen",
                "-t",
                type,
                "-f",
                str(key_path),
                "-N",
                "",  # No passphrase
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
                # Read public key
                pub_key = (key_path.with_suffix(".pub")).read_text().strip()

                return f"""Key pair generated:

Private key: {key_path}
Public key: {key_path}.pub

Public key (to copy to servers):
{pub_key}

To add to a server:
  ssh-copy-id -i {key_path}.pub user@host
"""
            else:
                return f"Error generating keys: {result.stderr}"

        except Exception as e:
            return f"Error: {e}"

    def list_ssh_keys(self) -> str:
        """List available SSH keys."""
        try:
            ssh_dir = Path.home() / ".ssh"

            if not ssh_dir.exists():
                return "Directory ~/.ssh does not exist"

            keys = []
            for f in ssh_dir.iterdir():
                if f.suffix == ".pub":
                    private_key = f.with_suffix("")
                    if private_key.exists():
                        # Read key type
                        content = f.read_text().strip()
                        key_type = content.split()[0] if content else "unknown"
                        keys.append((private_key.name, key_type))

            if not keys:
                return "No SSH keys found.\n\nGenerate one with:\n  ssh-keygen -t ed25519"

            result = ["Available SSH keys:\n"]
            for name, key_type in sorted(keys):
                result.append(f"  {name} ({key_type})")

            result.append(f"\nLocation: {ssh_dir}")

            return "\n".join(result)

        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "list_keys")

        if action == "exec":
            host = kwargs.get("host", "")
            command = kwargs.get("command", "")
            if not host or not command:
                return "Error: host and command required"
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
            return f"Unrecognized action: {action}"
