"""
System Skill for R CLI.

System utilities:
- System information
- Process management
- Disk usage
- Memory info
- Environment variables
"""

import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class SystemSkill(Skill):
    """Skill for system operations."""

    name = "system"
    description = "System: info, processes, disk, memory, environment"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="system_info",
                description="Get system information",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.system_info,
            ),
            Tool(
                name="disk_usage",
                description="Get disk usage information",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to check (default: /)",
                        },
                    },
                },
                handler=self.disk_usage,
            ),
            Tool(
                name="memory_info",
                description="Get memory usage information",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.memory_info,
            ),
            Tool(
                name="cpu_info",
                description="Get CPU information",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.cpu_info,
            ),
            Tool(
                name="process_list",
                description="List running processes",
                parameters={
                    "type": "object",
                    "properties": {
                        "filter": {
                            "type": "string",
                            "description": "Filter by process name",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max processes to show",
                        },
                    },
                },
                handler=self.process_list,
            ),
            Tool(
                name="process_kill",
                description="Kill a process by PID",
                parameters={
                    "type": "object",
                    "properties": {
                        "pid": {
                            "type": "integer",
                            "description": "Process ID to kill",
                        },
                        "signal": {
                            "type": "string",
                            "description": "Signal: TERM (default), KILL, HUP",
                        },
                    },
                    "required": ["pid"],
                },
                handler=self.process_kill,
            ),
            Tool(
                name="env_get",
                description="Get environment variable",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Variable name (or empty for all)",
                        },
                    },
                },
                handler=self.env_get,
            ),
            Tool(
                name="uptime",
                description="Get system uptime",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.uptime,
            ),
            Tool(
                name="users_logged",
                description="Show logged in users",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.users_logged,
            ),
        ]

    def system_info(self) -> str:
        """Get system information."""
        try:
            info = {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "hostname": platform.node(),
                "python_version": platform.python_version(),
            }

            # macOS specific
            if platform.system() == "Darwin":
                try:
                    result = subprocess.run(
                        ["sw_vers", "-productVersion"],
                        check=False, capture_output=True, text=True
                    )
                    info["macos_version"] = result.stdout.strip()
                except Exception:
                    pass

            # Linux specific
            elif platform.system() == "Linux":
                try:
                    with open("/etc/os-release") as f:
                        for line in f:
                            if line.startswith("PRETTY_NAME="):
                                info["distro"] = line.split("=")[1].strip().strip('"')
                                break
                except Exception:
                    pass

            return json.dumps(info, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def disk_usage(self, path: str = "/") -> str:
        """Get disk usage."""
        try:
            stat = os.statvfs(path)
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bfree * stat.f_frsize
            available = stat.f_bavail * stat.f_frsize
            used = total - free

            def human_size(size: int) -> str:
                for unit in ["B", "KB", "MB", "GB", "TB"]:
                    if size < 1024:
                        return f"{size:.2f} {unit}"
                    size /= 1024
                return f"{size:.2f} PB"

            return json.dumps({
                "path": path,
                "total": human_size(total),
                "used": human_size(used),
                "available": human_size(available),
                "percent_used": f"{(used / total) * 100:.1f}%",
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def memory_info(self) -> str:
        """Get memory info."""
        try:
            # Try psutil first
            try:
                import psutil
                mem = psutil.virtual_memory()
                swap = psutil.swap_memory()

                def human_size(size: int) -> str:
                    for unit in ["B", "KB", "MB", "GB", "TB"]:
                        if size < 1024:
                            return f"{size:.2f} {unit}"
                        size /= 1024
                    return f"{size:.2f} PB"

                return json.dumps({
                    "total": human_size(mem.total),
                    "available": human_size(mem.available),
                    "used": human_size(mem.used),
                    "percent": f"{mem.percent}%",
                    "swap_total": human_size(swap.total),
                    "swap_used": human_size(swap.used),
                }, indent=2)

            except ImportError:
                pass

            # Fallback: use vm_stat on macOS
            if platform.system() == "Darwin":
                result = subprocess.run(
                    ["vm_stat"],
                    check=False, capture_output=True, text=True
                )
                return f"Memory stats (install psutil for better output):\n{result.stdout}"

            # Fallback: read /proc/meminfo on Linux
            elif platform.system() == "Linux":
                with open("/proc/meminfo") as f:
                    lines = f.readlines()[:10]
                return "Memory info:\n" + "".join(lines)

            return "psutil not installed. Run: pip install psutil"

        except Exception as e:
            return f"Error: {e}"

    def cpu_info(self) -> str:
        """Get CPU info."""
        try:
            info = {
                "processor": platform.processor(),
                "architecture": platform.machine(),
            }

            # Try psutil
            try:
                import psutil
                info["cores_physical"] = psutil.cpu_count(logical=False)
                info["cores_logical"] = psutil.cpu_count(logical=True)
                info["cpu_percent"] = f"{psutil.cpu_percent(interval=1)}%"
                info["cpu_freq"] = f"{psutil.cpu_freq().current:.0f} MHz" if psutil.cpu_freq() else "N/A"
            except ImportError:
                info["cores"] = os.cpu_count()

            # macOS specific
            if platform.system() == "Darwin":
                try:
                    result = subprocess.run(
                        ["sysctl", "-n", "machdep.cpu.brand_string"],
                        check=False, capture_output=True, text=True
                    )
                    info["cpu_model"] = result.stdout.strip()
                except Exception:
                    pass

            return json.dumps(info, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def process_list(
        self,
        filter: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """List processes."""
        try:
            # Try psutil first
            try:
                import psutil
                processes = []
                for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                    try:
                        info = proc.info
                        if filter and filter.lower() not in info["name"].lower():
                            continue
                        processes.append({
                            "pid": info["pid"],
                            "name": info["name"],
                            "cpu": f"{info['cpu_percent']:.1f}%",
                            "memory": f"{info['memory_percent']:.1f}%",
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                # Sort by CPU usage
                processes.sort(key=lambda x: float(x["cpu"].rstrip("%")), reverse=True)
                return json.dumps(processes[:limit], indent=2)

            except ImportError:
                pass

            # Fallback: use ps command
            result = subprocess.run(
                ["ps", "aux"],
                check=False, capture_output=True, text=True
            )

            lines = result.stdout.strip().split("\n")
            header = lines[0]
            processes = lines[1:limit+1]

            if filter:
                processes = [p for p in lines[1:] if filter.lower() in p.lower()][:limit]

            return f"{header}\n" + "\n".join(processes)

        except Exception as e:
            return f"Error: {e}"

    def process_kill(self, pid: int, signal: str = "TERM") -> str:
        """Kill a process."""
        try:
            import signal as sig

            signals = {
                "TERM": sig.SIGTERM,
                "KILL": sig.SIGKILL,
                "HUP": sig.SIGHUP,
                "INT": sig.SIGINT,
            }

            if signal.upper() not in signals:
                return f"Unknown signal: {signal}"

            os.kill(pid, signals[signal.upper()])
            return f"Sent {signal.upper()} to process {pid}"

        except ProcessLookupError:
            return f"Process {pid} not found"
        except PermissionError:
            return f"Permission denied to kill process {pid}"
        except Exception as e:
            return f"Error: {e}"

    def env_get(self, name: Optional[str] = None) -> str:
        """Get environment variables."""
        try:
            if name:
                value = os.environ.get(name)
                if value is None:
                    return f"Variable '{name}' not set"
                return f"{name}={value}"
            else:
                # Return common ones (not all, could be sensitive)
                common = ["PATH", "HOME", "USER", "SHELL", "LANG", "TERM", "EDITOR"]
                env = {}
                for var in common:
                    if var in os.environ:
                        env[var] = os.environ[var]
                return json.dumps(env, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def uptime(self) -> str:
        """Get system uptime."""
        try:
            # Try psutil
            try:
                from datetime import datetime

                import psutil
                boot_time = datetime.fromtimestamp(psutil.boot_time())
                uptime = datetime.now() - boot_time

                days = uptime.days
                hours, remainder = divmod(uptime.seconds, 3600)
                minutes, _ = divmod(remainder, 60)

                return json.dumps({
                    "boot_time": boot_time.isoformat(),
                    "uptime": f"{days}d {hours}h {minutes}m",
                }, indent=2)

            except ImportError:
                pass

            # Fallback: use uptime command
            result = subprocess.run(
                ["uptime"],
                check=False, capture_output=True, text=True
            )
            return result.stdout.strip()

        except Exception as e:
            return f"Error: {e}"

    def users_logged(self) -> str:
        """Show logged in users."""
        try:
            # Try psutil
            try:
                import psutil
                users = []
                for user in psutil.users():
                    users.append({
                        "name": user.name,
                        "terminal": user.terminal,
                        "host": user.host,
                        "started": user.started,
                    })
                return json.dumps(users, indent=2)

            except ImportError:
                pass

            # Fallback: use who command
            result = subprocess.run(
                ["who"],
                check=False, capture_output=True, text=True
            )
            return result.stdout.strip() or "No users logged in"

        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "info")
        if action == "info":
            return self.system_info()
        elif action == "disk":
            return self.disk_usage()
        elif action == "memory":
            return self.memory_info()
        return f"Unknown action: {action}"
