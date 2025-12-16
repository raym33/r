"""
IP Skill for R CLI.

IP address utilities:
- Validate IP addresses
- CIDR calculations
- Geolocation lookup
- Network info
"""

import json
import socket
import struct
import urllib.request
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class IPSkill(Skill):
    """Skill for IP address operations."""

    name = "ip"
    description = "IP: validate, CIDR, geolocation, network info"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="ip_validate",
                description="Validate an IP address",
                parameters={
                    "type": "object",
                    "properties": {
                        "ip": {
                            "type": "string",
                            "description": "IP address to validate",
                        },
                    },
                    "required": ["ip"],
                },
                handler=self.ip_validate,
            ),
            Tool(
                name="ip_info",
                description="Get information about an IP address",
                parameters={
                    "type": "object",
                    "properties": {
                        "ip": {
                            "type": "string",
                            "description": "IP address",
                        },
                    },
                    "required": ["ip"],
                },
                handler=self.ip_info,
            ),
            Tool(
                name="ip_geolocation",
                description="Get geolocation for an IP address",
                parameters={
                    "type": "object",
                    "properties": {
                        "ip": {
                            "type": "string",
                            "description": "IP address (empty for current)",
                        },
                    },
                },
                handler=self.ip_geolocation,
            ),
            Tool(
                name="ip_cidr",
                description="Calculate CIDR network information",
                parameters={
                    "type": "object",
                    "properties": {
                        "cidr": {
                            "type": "string",
                            "description": "CIDR notation (e.g., 192.168.1.0/24)",
                        },
                    },
                    "required": ["cidr"],
                },
                handler=self.ip_cidr,
            ),
            Tool(
                name="ip_range",
                description="List IP addresses in a range",
                parameters={
                    "type": "object",
                    "properties": {
                        "start": {
                            "type": "string",
                            "description": "Start IP address",
                        },
                        "end": {
                            "type": "string",
                            "description": "End IP address",
                        },
                    },
                    "required": ["start", "end"],
                },
                handler=self.ip_range,
            ),
            Tool(
                name="ip_to_int",
                description="Convert IP address to integer",
                parameters={
                    "type": "object",
                    "properties": {
                        "ip": {
                            "type": "string",
                            "description": "IP address",
                        },
                    },
                    "required": ["ip"],
                },
                handler=self.ip_to_int,
            ),
            Tool(
                name="int_to_ip",
                description="Convert integer to IP address",
                parameters={
                    "type": "object",
                    "properties": {
                        "number": {
                            "type": "integer",
                            "description": "Integer value",
                        },
                    },
                    "required": ["number"],
                },
                handler=self.int_to_ip,
            ),
            Tool(
                name="ip_is_private",
                description="Check if IP is private/public",
                parameters={
                    "type": "object",
                    "properties": {
                        "ip": {
                            "type": "string",
                            "description": "IP address",
                        },
                    },
                    "required": ["ip"],
                },
                handler=self.ip_is_private,
            ),
        ]

    def _ip_to_int(self, ip: str) -> int:
        """Convert IP to integer."""
        return struct.unpack("!I", socket.inet_aton(ip))[0]

    def _int_to_ip(self, num: int) -> str:
        """Convert integer to IP."""
        return socket.inet_ntoa(struct.pack("!I", num))

    def _is_valid_ipv4(self, ip: str) -> bool:
        """Check if valid IPv4."""
        try:
            socket.inet_aton(ip)
            parts = ip.split(".")
            return len(parts) == 4 and all(0 <= int(p) <= 255 for p in parts)
        except (socket.error, ValueError):
            return False

    def _is_valid_ipv6(self, ip: str) -> bool:
        """Check if valid IPv6."""
        try:
            socket.inet_pton(socket.AF_INET6, ip)
            return True
        except (socket.error, ValueError):
            return False

    def ip_validate(self, ip: str) -> str:
        """Validate IP address."""
        ipv4 = self._is_valid_ipv4(ip)
        ipv6 = self._is_valid_ipv6(ip)

        return json.dumps({
            "ip": ip,
            "valid": ipv4 or ipv6,
            "version": 4 if ipv4 else (6 if ipv6 else None),
            "type": "IPv4" if ipv4 else ("IPv6" if ipv6 else "Invalid"),
        }, indent=2)

    def ip_info(self, ip: str) -> str:
        """Get IP information."""
        if not self._is_valid_ipv4(ip):
            return f"Invalid IPv4 address: {ip}"

        try:
            # Determine class
            first_octet = int(ip.split(".")[0])
            if first_octet < 128:
                ip_class = "A"
                default_mask = "255.0.0.0"
            elif first_octet < 192:
                ip_class = "B"
                default_mask = "255.255.0.0"
            elif first_octet < 224:
                ip_class = "C"
                default_mask = "255.255.255.0"
            elif first_octet < 240:
                ip_class = "D (Multicast)"
                default_mask = "N/A"
            else:
                ip_class = "E (Reserved)"
                default_mask = "N/A"

            # Check special ranges
            is_private = self._check_private(ip)
            is_loopback = ip.startswith("127.")
            is_link_local = ip.startswith("169.254.")

            return json.dumps({
                "ip": ip,
                "class": ip_class,
                "default_mask": default_mask,
                "is_private": is_private,
                "is_loopback": is_loopback,
                "is_link_local": is_link_local,
                "binary": ".".join(format(int(o), "08b") for o in ip.split(".")),
                "integer": self._ip_to_int(ip),
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def _check_private(self, ip: str) -> bool:
        """Check if IP is private."""
        parts = [int(p) for p in ip.split(".")]

        # 10.0.0.0/8
        if parts[0] == 10:
            return True
        # 172.16.0.0/12
        if parts[0] == 172 and 16 <= parts[1] <= 31:
            return True
        # 192.168.0.0/16
        if parts[0] == 192 and parts[1] == 168:
            return True

        return False

    def ip_geolocation(self, ip: Optional[str] = None) -> str:
        """Get geolocation for IP."""
        try:
            if ip:
                url = f"http://ip-api.com/json/{ip}"
            else:
                url = "http://ip-api.com/json/"

            req = urllib.request.Request(url, headers={"User-Agent": "R-CLI/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

                if data.get("status") == "fail":
                    return f"Geolocation failed: {data.get('message')}"

                return json.dumps({
                    "ip": data.get("query"),
                    "country": data.get("country"),
                    "country_code": data.get("countryCode"),
                    "region": data.get("regionName"),
                    "city": data.get("city"),
                    "zip": data.get("zip"),
                    "latitude": data.get("lat"),
                    "longitude": data.get("lon"),
                    "timezone": data.get("timezone"),
                    "isp": data.get("isp"),
                    "org": data.get("org"),
                }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def ip_cidr(self, cidr: str) -> str:
        """Calculate CIDR network info."""
        try:
            ip, prefix = cidr.split("/")
            prefix = int(prefix)

            if not self._is_valid_ipv4(ip) or not (0 <= prefix <= 32):
                return "Invalid CIDR notation"

            ip_int = self._ip_to_int(ip)

            # Calculate mask
            mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
            wildcard = mask ^ 0xFFFFFFFF

            # Network and broadcast
            network = ip_int & mask
            broadcast = network | wildcard

            # Usable range
            first_host = network + 1 if prefix < 31 else network
            last_host = broadcast - 1 if prefix < 31 else broadcast
            num_hosts = (1 << (32 - prefix)) - 2 if prefix < 31 else (1 << (32 - prefix))

            return json.dumps({
                "cidr": cidr,
                "network": self._int_to_ip(network),
                "broadcast": self._int_to_ip(broadcast),
                "netmask": self._int_to_ip(mask),
                "wildcard": self._int_to_ip(wildcard),
                "first_host": self._int_to_ip(first_host),
                "last_host": self._int_to_ip(last_host),
                "num_hosts": num_hosts,
                "prefix": prefix,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def ip_range(self, start: str, end: str) -> str:
        """List IPs in range."""
        if not self._is_valid_ipv4(start) or not self._is_valid_ipv4(end):
            return "Invalid IP address"

        try:
            start_int = self._ip_to_int(start)
            end_int = self._ip_to_int(end)

            if start_int > end_int:
                start_int, end_int = end_int, start_int

            count = end_int - start_int + 1
            if count > 256:
                return json.dumps({
                    "start": start,
                    "end": end,
                    "count": count,
                    "note": "Too many IPs to list (max 256). Showing first and last 5.",
                    "first_5": [self._int_to_ip(start_int + i) for i in range(5)],
                    "last_5": [self._int_to_ip(end_int - 4 + i) for i in range(5)],
                }, indent=2)

            ips = [self._int_to_ip(start_int + i) for i in range(count)]
            return json.dumps({
                "start": start,
                "end": end,
                "count": count,
                "ips": ips,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def ip_to_int(self, ip: str) -> str:
        """Convert IP to integer."""
        if not self._is_valid_ipv4(ip):
            return f"Invalid IP: {ip}"

        return json.dumps({
            "ip": ip,
            "integer": self._ip_to_int(ip),
            "hex": hex(self._ip_to_int(ip)),
        }, indent=2)

    def int_to_ip(self, number: int) -> str:
        """Convert integer to IP."""
        if not (0 <= number <= 0xFFFFFFFF):
            return "Number out of range (0 - 4294967295)"

        return json.dumps({
            "integer": number,
            "ip": self._int_to_ip(number),
        }, indent=2)

    def ip_is_private(self, ip: str) -> str:
        """Check if IP is private."""
        if not self._is_valid_ipv4(ip):
            return f"Invalid IP: {ip}"

        is_private = self._check_private(ip)

        return json.dumps({
            "ip": ip,
            "is_private": is_private,
            "is_public": not is_private and not ip.startswith("127."),
            "type": "Private" if is_private else ("Loopback" if ip.startswith("127.") else "Public"),
        }, indent=2)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "validate")
        if action == "validate":
            return self.ip_validate(kwargs.get("ip", ""))
        elif action == "geo":
            return self.ip_geolocation(kwargs.get("ip"))
        return f"Unknown action: {action}"
