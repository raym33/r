"""
Network Skill for R CLI.

Network utilities:
- Ping hosts
- DNS lookups
- Port scanning
- HTTP requests
- Network info
"""

import json
import socket
import subprocess
import shutil
from typing import Optional
from urllib.parse import urlparse

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class NetworkSkill(Skill):
    """Skill for network operations."""

    name = "network"
    description = "Network: ping, DNS, ports, HTTP, network info"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="ping",
                description="Ping a host to check connectivity",
                parameters={
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string",
                            "description": "Hostname or IP address",
                        },
                        "count": {
                            "type": "integer",
                            "description": "Number of pings (default: 4)",
                        },
                    },
                    "required": ["host"],
                },
                handler=self.ping,
            ),
            Tool(
                name="dns_lookup",
                description="DNS lookup for a hostname",
                parameters={
                    "type": "object",
                    "properties": {
                        "hostname": {
                            "type": "string",
                            "description": "Hostname to lookup",
                        },
                        "record_type": {
                            "type": "string",
                            "description": "Record type: A, AAAA, MX, TXT, NS, CNAME",
                        },
                    },
                    "required": ["hostname"],
                },
                handler=self.dns_lookup,
            ),
            Tool(
                name="port_check",
                description="Check if a port is open on a host",
                parameters={
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string",
                            "description": "Hostname or IP",
                        },
                        "port": {
                            "type": "integer",
                            "description": "Port number",
                        },
                        "timeout": {
                            "type": "number",
                            "description": "Timeout in seconds (default: 2)",
                        },
                    },
                    "required": ["host", "port"],
                },
                handler=self.port_check,
            ),
            Tool(
                name="port_scan",
                description="Scan common ports on a host",
                parameters={
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string",
                            "description": "Hostname or IP",
                        },
                        "ports": {
                            "type": "string",
                            "description": "Port range (e.g., '80,443' or '20-25')",
                        },
                    },
                    "required": ["host"],
                },
                handler=self.port_scan,
            ),
            Tool(
                name="http_get",
                description="Make HTTP GET request",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to request",
                        },
                        "headers": {
                            "type": "object",
                            "description": "Optional headers",
                        },
                    },
                    "required": ["url"],
                },
                handler=self.http_get,
            ),
            Tool(
                name="whois",
                description="WHOIS lookup for a domain",
                parameters={
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "Domain to lookup",
                        },
                    },
                    "required": ["domain"],
                },
                handler=self.whois_lookup,
            ),
            Tool(
                name="local_ip",
                description="Get local network information",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.local_ip,
            ),
            Tool(
                name="public_ip",
                description="Get public IP address",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.public_ip,
            ),
        ]

    def ping(self, host: str, count: int = 4) -> str:
        """Ping a host."""
        try:
            # Use system ping command
            cmd = ["ping", "-c", str(count), host]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                # Parse output
                lines = result.stdout.strip().split("\n")
                stats_line = [l for l in lines if "packets" in l.lower()]
                time_line = [l for l in lines if "round-trip" in l.lower() or "rtt" in l.lower()]

                return json.dumps({
                    "host": host,
                    "reachable": True,
                    "stats": stats_line[0] if stats_line else None,
                    "timing": time_line[0] if time_line else None,
                }, indent=2)
            else:
                return json.dumps({
                    "host": host,
                    "reachable": False,
                    "error": result.stderr or "Host unreachable",
                }, indent=2)

        except subprocess.TimeoutExpired:
            return f"Ping timeout for {host}"
        except Exception as e:
            return f"Error: {e}"

    def dns_lookup(self, hostname: str, record_type: str = "A") -> str:
        """DNS lookup."""
        try:
            results = {"hostname": hostname, "type": record_type}

            if record_type.upper() == "A":
                # IPv4 addresses
                ips = socket.gethostbyname_ex(hostname)
                results["addresses"] = ips[2]
                results["aliases"] = ips[1]

            elif record_type.upper() == "AAAA":
                # IPv6 addresses
                infos = socket.getaddrinfo(hostname, None, socket.AF_INET6)
                results["addresses"] = list(set(info[4][0] for info in infos))

            else:
                # Use dig for other record types
                if shutil.which("dig"):
                    result = subprocess.run(
                        ["dig", "+short", record_type.upper(), hostname],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    results["records"] = result.stdout.strip().split("\n")
                else:
                    return f"dig not available for {record_type} records"

            return json.dumps(results, indent=2)

        except socket.gaierror as e:
            return f"DNS lookup failed: {e}"
        except Exception as e:
            return f"Error: {e}"

    def port_check(self, host: str, port: int, timeout: float = 2) -> str:
        """Check if port is open."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()

            is_open = result == 0

            # Common port names
            common_ports = {
                21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
                53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP",
                443: "HTTPS", 993: "IMAPS", 995: "POP3S",
                3306: "MySQL", 5432: "PostgreSQL", 6379: "Redis",
                8080: "HTTP-Alt", 27017: "MongoDB",
            }

            return json.dumps({
                "host": host,
                "port": port,
                "open": is_open,
                "service": common_ports.get(port, "unknown"),
            }, indent=2)

        except socket.gaierror:
            return f"Could not resolve hostname: {host}"
        except Exception as e:
            return f"Error: {e}"

    def port_scan(self, host: str, ports: Optional[str] = None) -> str:
        """Scan ports on host."""
        try:
            if ports:
                # Parse port specification
                port_list = []
                for part in ports.split(","):
                    if "-" in part:
                        start, end = map(int, part.split("-"))
                        port_list.extend(range(start, end + 1))
                    else:
                        port_list.append(int(part))
            else:
                # Common ports
                port_list = [21, 22, 23, 25, 53, 80, 110, 143, 443, 993, 995,
                            3306, 5432, 6379, 8080, 8443, 27017]

            open_ports = []
            for port in port_list[:100]:  # Limit to 100 ports
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                if sock.connect_ex((host, port)) == 0:
                    open_ports.append(port)
                sock.close()

            return json.dumps({
                "host": host,
                "scanned": len(port_list),
                "open_ports": open_ports,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def http_get(self, url: str, headers: Optional[dict] = None) -> str:
        """Make HTTP GET request."""
        try:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(url)
            req.add_header("User-Agent", "R-CLI/1.0")

            if headers:
                for key, value in headers.items():
                    req.add_header(key, value)

            with urllib.request.urlopen(req, timeout=10) as response:
                return json.dumps({
                    "url": url,
                    "status": response.status,
                    "headers": dict(response.headers),
                    "content_length": len(response.read()),
                }, indent=2)

        except urllib.error.HTTPError as e:
            return json.dumps({
                "url": url,
                "status": e.code,
                "error": str(e.reason),
            }, indent=2)
        except Exception as e:
            return f"Error: {e}"

    def whois_lookup(self, domain: str) -> str:
        """WHOIS lookup."""
        if not shutil.which("whois"):
            return "whois command not available"

        try:
            result = subprocess.run(
                ["whois", domain],
                capture_output=True,
                text=True,
                timeout=15,
            )

            if result.returncode == 0:
                # Extract key info
                output = result.stdout
                lines = output.split("\n")

                info = {"domain": domain}
                for line in lines:
                    line_lower = line.lower()
                    if "registrar:" in line_lower:
                        info["registrar"] = line.split(":", 1)[1].strip()
                    elif "creation date:" in line_lower:
                        info["created"] = line.split(":", 1)[1].strip()
                    elif "expiry date:" in line_lower or "expiration date:" in line_lower:
                        info["expires"] = line.split(":", 1)[1].strip()
                    elif "name server:" in line_lower:
                        if "nameservers" not in info:
                            info["nameservers"] = []
                        info["nameservers"].append(line.split(":", 1)[1].strip())

                return json.dumps(info, indent=2)
            else:
                return f"WHOIS failed: {result.stderr}"

        except subprocess.TimeoutExpired:
            return "WHOIS lookup timeout"
        except Exception as e:
            return f"Error: {e}"

    def local_ip(self) -> str:
        """Get local network info."""
        try:
            # Get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()

            # Get hostname
            hostname = socket.gethostname()

            # Get all interfaces
            interfaces = []
            try:
                import netifaces
                for iface in netifaces.interfaces():
                    addrs = netifaces.ifaddresses(iface)
                    if netifaces.AF_INET in addrs:
                        for addr in addrs[netifaces.AF_INET]:
                            interfaces.append({
                                "interface": iface,
                                "ip": addr.get("addr"),
                                "netmask": addr.get("netmask"),
                            })
            except ImportError:
                pass

            return json.dumps({
                "hostname": hostname,
                "local_ip": local_ip,
                "interfaces": interfaces if interfaces else "netifaces not installed",
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def public_ip(self) -> str:
        """Get public IP."""
        try:
            import urllib.request

            services = [
                "https://api.ipify.org",
                "https://icanhazip.com",
                "https://checkip.amazonaws.com",
            ]

            for service in services:
                try:
                    with urllib.request.urlopen(service, timeout=5) as response:
                        ip = response.read().decode().strip()
                        return json.dumps({
                            "public_ip": ip,
                            "source": service,
                        }, indent=2)
                except Exception:
                    continue

            return "Could not determine public IP"

        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "ping")
        if action == "ping":
            return self.ping(kwargs.get("host", ""))
        elif action == "dns":
            return self.dns_lookup(kwargs.get("host", ""))
        return f"Unknown action: {action}"
