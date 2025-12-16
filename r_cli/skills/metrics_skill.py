"""
Metrics Skill for R CLI.

System metrics collection:
- CPU, memory, disk usage
- Network statistics
- Process metrics
- Historical data
"""

import json
import os
import platform
import time
from datetime import datetime
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class MetricsSkill(Skill):
    """Skill for system metrics collection."""

    name = "metrics"
    description = "Metrics: CPU, memory, disk, network statistics"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="metrics_cpu",
                description="Get CPU usage metrics",
                parameters={
                    "type": "object",
                    "properties": {
                        "interval": {
                            "type": "number",
                            "description": "Measurement interval in seconds (default: 1)",
                        },
                    },
                },
                handler=self.metrics_cpu,
            ),
            Tool(
                name="metrics_memory",
                description="Get memory usage metrics",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.metrics_memory,
            ),
            Tool(
                name="metrics_disk",
                description="Get disk usage metrics",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to check (default: /)",
                        },
                    },
                },
                handler=self.metrics_disk,
            ),
            Tool(
                name="metrics_network",
                description="Get network I/O statistics",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.metrics_network,
            ),
            Tool(
                name="metrics_processes",
                description="Get top processes by resource usage",
                parameters={
                    "type": "object",
                    "properties": {
                        "sort_by": {
                            "type": "string",
                            "description": "Sort by: cpu, memory (default: cpu)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of processes (default: 10)",
                        },
                    },
                },
                handler=self.metrics_processes,
            ),
            Tool(
                name="metrics_summary",
                description="Get overall system metrics summary",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.metrics_summary,
            ),
            Tool(
                name="metrics_load",
                description="Get system load averages",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.metrics_load,
            ),
            Tool(
                name="metrics_uptime",
                description="Get system uptime and boot time",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.metrics_uptime,
            ),
        ]

    def _human_size(self, size: int) -> str:
        """Convert bytes to human readable."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"

    def _try_psutil(self):
        """Try to import psutil."""
        try:
            import psutil
            return psutil
        except ImportError:
            return None

    def metrics_cpu(self, interval: float = 1) -> str:
        """Get CPU metrics."""
        psutil = self._try_psutil()

        if psutil:
            try:
                # Get CPU percent
                cpu_percent = psutil.cpu_percent(interval=interval)
                per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)

                # CPU times
                cpu_times = psutil.cpu_times()

                # CPU frequency
                try:
                    freq = psutil.cpu_freq()
                    freq_info = {
                        "current": f"{freq.current:.0f} MHz",
                        "min": f"{freq.min:.0f} MHz" if freq.min else None,
                        "max": f"{freq.max:.0f} MHz" if freq.max else None,
                    }
                except Exception:
                    freq_info = None

                return json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "cpu_percent": cpu_percent,
                    "per_cpu": per_cpu,
                    "cores_logical": psutil.cpu_count(logical=True),
                    "cores_physical": psutil.cpu_count(logical=False),
                    "frequency": freq_info,
                    "times": {
                        "user": cpu_times.user,
                        "system": cpu_times.system,
                        "idle": cpu_times.idle,
                    },
                }, indent=2)

            except Exception as e:
                return f"Error: {e}"

        # Fallback
        return json.dumps({
            "timestamp": datetime.now().isoformat(),
            "cores": os.cpu_count(),
            "note": "Install psutil for detailed metrics: pip install psutil",
        }, indent=2)

    def metrics_memory(self) -> str:
        """Get memory metrics."""
        psutil = self._try_psutil()

        if psutil:
            try:
                mem = psutil.virtual_memory()
                swap = psutil.swap_memory()

                return json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "virtual": {
                        "total": self._human_size(mem.total),
                        "available": self._human_size(mem.available),
                        "used": self._human_size(mem.used),
                        "free": self._human_size(mem.free),
                        "percent": mem.percent,
                    },
                    "swap": {
                        "total": self._human_size(swap.total),
                        "used": self._human_size(swap.used),
                        "free": self._human_size(swap.free),
                        "percent": swap.percent,
                    },
                }, indent=2)

            except Exception as e:
                return f"Error: {e}"

        return json.dumps({
            "timestamp": datetime.now().isoformat(),
            "note": "Install psutil for memory metrics: pip install psutil",
        }, indent=2)

    def metrics_disk(self, path: str = "/") -> str:
        """Get disk metrics."""
        psutil = self._try_psutil()

        if psutil:
            try:
                usage = psutil.disk_usage(path)

                # Get all partitions
                partitions = []
                for part in psutil.disk_partitions():
                    try:
                        part_usage = psutil.disk_usage(part.mountpoint)
                        partitions.append({
                            "device": part.device,
                            "mountpoint": part.mountpoint,
                            "fstype": part.fstype,
                            "total": self._human_size(part_usage.total),
                            "used": self._human_size(part_usage.used),
                            "free": self._human_size(part_usage.free),
                            "percent": part_usage.percent,
                        })
                    except Exception:
                        pass

                return json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "path": path,
                    "total": self._human_size(usage.total),
                    "used": self._human_size(usage.used),
                    "free": self._human_size(usage.free),
                    "percent": usage.percent,
                    "partitions": partitions,
                }, indent=2)

            except Exception as e:
                return f"Error: {e}"

        # Fallback using os.statvfs
        try:
            stat = os.statvfs(path)
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bfree * stat.f_frsize
            used = total - free

            return json.dumps({
                "timestamp": datetime.now().isoformat(),
                "path": path,
                "total": self._human_size(total),
                "used": self._human_size(used),
                "free": self._human_size(free),
                "percent": f"{(used / total) * 100:.1f}%",
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def metrics_network(self) -> str:
        """Get network metrics."""
        psutil = self._try_psutil()

        if psutil:
            try:
                net_io = psutil.net_io_counters()

                # Per interface
                per_nic = {}
                for nic, counters in psutil.net_io_counters(pernic=True).items():
                    per_nic[nic] = {
                        "bytes_sent": self._human_size(counters.bytes_sent),
                        "bytes_recv": self._human_size(counters.bytes_recv),
                        "packets_sent": counters.packets_sent,
                        "packets_recv": counters.packets_recv,
                    }

                return json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "total": {
                        "bytes_sent": self._human_size(net_io.bytes_sent),
                        "bytes_recv": self._human_size(net_io.bytes_recv),
                        "packets_sent": net_io.packets_sent,
                        "packets_recv": net_io.packets_recv,
                        "errors_in": net_io.errin,
                        "errors_out": net_io.errout,
                    },
                    "per_interface": per_nic,
                }, indent=2)

            except Exception as e:
                return f"Error: {e}"

        return json.dumps({
            "timestamp": datetime.now().isoformat(),
            "note": "Install psutil for network metrics: pip install psutil",
        }, indent=2)

    def metrics_processes(
        self,
        sort_by: str = "cpu",
        limit: int = 10,
    ) -> str:
        """Get top processes."""
        psutil = self._try_psutil()

        if psutil:
            try:
                processes = []
                for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                    try:
                        info = proc.info
                        processes.append({
                            "pid": info["pid"],
                            "name": info["name"],
                            "cpu_percent": info["cpu_percent"],
                            "memory_percent": round(info["memory_percent"], 2),
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                # Sort
                if sort_by == "memory":
                    processes.sort(key=lambda x: x["memory_percent"], reverse=True)
                else:
                    processes.sort(key=lambda x: x["cpu_percent"], reverse=True)

                return json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "sort_by": sort_by,
                    "total_processes": len(processes),
                    "top": processes[:limit],
                }, indent=2)

            except Exception as e:
                return f"Error: {e}"

        return json.dumps({
            "timestamp": datetime.now().isoformat(),
            "note": "Install psutil for process metrics: pip install psutil",
        }, indent=2)

    def metrics_summary(self) -> str:
        """Get overall metrics summary."""
        psutil = self._try_psutil()

        summary = {
            "timestamp": datetime.now().isoformat(),
            "system": platform.system(),
            "hostname": platform.node(),
        }

        if psutil:
            try:
                # CPU
                summary["cpu"] = {
                    "percent": psutil.cpu_percent(interval=0.5),
                    "cores": psutil.cpu_count(),
                }

                # Memory
                mem = psutil.virtual_memory()
                summary["memory"] = {
                    "percent": mem.percent,
                    "used": self._human_size(mem.used),
                    "total": self._human_size(mem.total),
                }

                # Disk
                disk = psutil.disk_usage("/")
                summary["disk"] = {
                    "percent": disk.percent,
                    "used": self._human_size(disk.used),
                    "total": self._human_size(disk.total),
                }

                # Load
                if hasattr(os, "getloadavg"):
                    load = os.getloadavg()
                    summary["load"] = {
                        "1min": round(load[0], 2),
                        "5min": round(load[1], 2),
                        "15min": round(load[2], 2),
                    }

            except Exception as e:
                summary["error"] = str(e)
        else:
            summary["note"] = "Install psutil for detailed metrics"

        return json.dumps(summary, indent=2)

    def metrics_load(self) -> str:
        """Get system load averages."""
        try:
            if hasattr(os, "getloadavg"):
                load = os.getloadavg()
                cores = os.cpu_count() or 1

                return json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "load_1min": round(load[0], 2),
                    "load_5min": round(load[1], 2),
                    "load_15min": round(load[2], 2),
                    "cores": cores,
                    "load_per_core": {
                        "1min": round(load[0] / cores, 2),
                        "5min": round(load[1] / cores, 2),
                        "15min": round(load[2] / cores, 2),
                    },
                }, indent=2)
            else:
                return "Load average not available on this platform"

        except Exception as e:
            return f"Error: {e}"

    def metrics_uptime(self) -> str:
        """Get system uptime."""
        psutil = self._try_psutil()

        if psutil:
            try:
                boot_time = datetime.fromtimestamp(psutil.boot_time())
                uptime = datetime.now() - boot_time

                days = uptime.days
                hours, remainder = divmod(uptime.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)

                return json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "boot_time": boot_time.isoformat(),
                    "uptime": f"{days}d {hours}h {minutes}m {seconds}s",
                    "uptime_seconds": int(uptime.total_seconds()),
                }, indent=2)

            except Exception as e:
                return f"Error: {e}"

        # Fallback: try uptime command
        import subprocess
        try:
            result = subprocess.run(["uptime"], check=False, capture_output=True, text=True)
            return result.stdout.strip()
        except Exception:
            return "Uptime not available. Install psutil for this feature."

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "summary")
        if action == "summary":
            return self.metrics_summary()
        elif action == "cpu":
            return self.metrics_cpu()
        elif action == "memory":
            return self.metrics_memory()
        return f"Unknown action: {action}"
