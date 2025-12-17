"""
WiFi Skill for R CLI.

WiFi network management:
- Scan networks
- Connect/disconnect
- Manage saved networks
- Hotspot mode
"""

import json
import platform
import shutil
import subprocess
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class WiFiSkill(Skill):
    """Skill for WiFi operations."""

    name = "wifi"
    description = "WiFi: scan networks, connect, manage connections"

    def __init__(self, config=None):
        super().__init__(config)
        self._system = platform.system().lower()
        self._nmcli = shutil.which("nmcli")  # Linux NetworkManager
        self._iwconfig = shutil.which("iwconfig")  # Linux wireless
        self._networksetup = shutil.which("networksetup")  # macOS

    def _run_command(self, cmd: list[str], timeout: int = 30) -> tuple[bool, str]:
        """Run a shell command."""
        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="wifi_scan",
                description="Scan for available WiFi networks",
                parameters={
                    "type": "object",
                    "properties": {
                        "interface": {
                            "type": "string",
                            "description": "WiFi interface name (auto-detected if not specified)",
                        },
                    },
                },
                handler=self.wifi_scan,
            ),
            Tool(
                name="wifi_connect",
                description="Connect to a WiFi network",
                parameters={
                    "type": "object",
                    "properties": {
                        "ssid": {
                            "type": "string",
                            "description": "Network name (SSID)",
                        },
                        "password": {
                            "type": "string",
                            "description": "Network password",
                        },
                        "interface": {
                            "type": "string",
                            "description": "WiFi interface name",
                        },
                    },
                    "required": ["ssid"],
                },
                handler=self.wifi_connect,
            ),
            Tool(
                name="wifi_disconnect",
                description="Disconnect from current WiFi network",
                parameters={
                    "type": "object",
                    "properties": {
                        "interface": {
                            "type": "string",
                            "description": "WiFi interface name",
                        },
                    },
                },
                handler=self.wifi_disconnect,
            ),
            Tool(
                name="wifi_status",
                description="Get current WiFi connection status",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.wifi_status,
            ),
            Tool(
                name="wifi_saved",
                description="List saved WiFi networks",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.wifi_saved,
            ),
            Tool(
                name="wifi_forget",
                description="Forget a saved WiFi network",
                parameters={
                    "type": "object",
                    "properties": {
                        "ssid": {
                            "type": "string",
                            "description": "Network name to forget",
                        },
                    },
                    "required": ["ssid"],
                },
                handler=self.wifi_forget,
            ),
            Tool(
                name="wifi_toggle",
                description="Turn WiFi on or off",
                parameters={
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "description": "Power state: 'on' or 'off'",
                            "enum": ["on", "off"],
                        },
                    },
                    "required": ["state"],
                },
                handler=self.wifi_toggle,
            ),
            Tool(
                name="wifi_hotspot",
                description="Create a WiFi hotspot (access point)",
                parameters={
                    "type": "object",
                    "properties": {
                        "ssid": {
                            "type": "string",
                            "description": "Hotspot network name",
                        },
                        "password": {
                            "type": "string",
                            "description": "Hotspot password (min 8 chars)",
                        },
                        "action": {
                            "type": "string",
                            "description": "Action: 'start' or 'stop'",
                            "enum": ["start", "stop"],
                        },
                    },
                    "required": ["action"],
                },
                handler=self.wifi_hotspot,
            ),
            Tool(
                name="wifi_info",
                description="Get detailed WiFi interface information",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.wifi_info,
            ),
        ]

    def _get_interface(self) -> Optional[str]:
        """Auto-detect WiFi interface."""
        if self._system == "linux":
            success, output = self._run_command(["iwconfig"])
            if success:
                for line in output.split("\n"):
                    if "IEEE 802.11" in line:
                        return line.split()[0]
            # Try nmcli
            if self._nmcli:
                success, output = self._run_command(
                    [self._nmcli, "-t", "-f", "DEVICE,TYPE", "device"]
                )
                if success:
                    for line in output.split("\n"):
                        if ":wifi" in line:
                            return line.split(":")[0]
        elif self._system == "darwin":
            # macOS - usually en0 or en1
            success, output = self._run_command([self._networksetup, "-listallhardwareports"])
            if success:
                lines = output.split("\n")
                for i, line in enumerate(lines):
                    if "Wi-Fi" in line and i + 1 < len(lines):
                        device_line = lines[i + 1]
                        if "Device:" in device_line:
                            return device_line.split(":")[1].strip()
        return None

    def wifi_scan(self, interface: Optional[str] = None) -> str:
        """Scan for WiFi networks."""
        networks = []

        if self._system == "linux" and self._nmcli:
            success, output = self._run_command(
                [self._nmcli, "-t", "-f", "SSID,SIGNAL,SECURITY,BSSID", "device", "wifi", "list"]
            )
            if success:
                for line in output.strip().split("\n"):
                    if line:
                        parts = line.split(":")
                        if len(parts) >= 3 and parts[0]:
                            networks.append(
                                {
                                    "ssid": parts[0],
                                    "signal": int(parts[1]) if parts[1].isdigit() else 0,
                                    "security": parts[2] if len(parts) > 2 else "Open",
                                    "bssid": parts[3] if len(parts) > 3 else None,
                                }
                            )

        elif self._system == "darwin":
            # macOS airport scan
            airport = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
            success, output = self._run_command([airport, "-s"])
            if success:
                lines = output.strip().split("\n")[1:]  # Skip header
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        # Parse macOS airport output
                        ssid = parts[0]
                        signal = (
                            int(parts[1])
                            if len(parts) > 1 and parts[1].lstrip("-").isdigit()
                            else 0
                        )
                        networks.append(
                            {
                                "ssid": ssid,
                                "signal": signal,
                                "security": "Unknown",
                            }
                        )

        # Sort by signal strength
        networks.sort(key=lambda x: x.get("signal", 0), reverse=True)

        return json.dumps(
            {
                "success": True,
                "networks_found": len(networks),
                "networks": networks,
            },
            indent=2,
        )

    def wifi_connect(
        self,
        ssid: str,
        password: Optional[str] = None,
        interface: Optional[str] = None,
    ) -> str:
        """Connect to a WiFi network."""
        interface = interface or self._get_interface()

        if self._system == "linux" and self._nmcli:
            cmd = [self._nmcli, "device", "wifi", "connect", ssid]
            if password:
                cmd.extend(["password", password])
            if interface:
                cmd.extend(["ifname", interface])

            success, output = self._run_command(cmd, timeout=60)

            return json.dumps(
                {
                    "success": success,
                    "ssid": ssid,
                    "message": "Connected" if success else output,
                }
            )

        elif self._system == "darwin":
            cmd = [self._networksetup, "-setairportnetwork", interface or "en0", ssid]
            if password:
                cmd.append(password)

            success, output = self._run_command(cmd, timeout=30)

            return json.dumps(
                {
                    "success": success,
                    "ssid": ssid,
                    "message": "Connected" if success else output,
                }
            )

        return json.dumps(
            {
                "success": False,
                "error": f"Unsupported platform: {self._system}",
            }
        )

    def wifi_disconnect(self, interface: Optional[str] = None) -> str:
        """Disconnect from WiFi."""
        interface = interface or self._get_interface()

        if self._system == "linux" and self._nmcli:
            success, output = self._run_command(
                [self._nmcli, "device", "disconnect", interface or "wlan0"]
            )
        elif self._system == "darwin":
            success, output = self._run_command(
                [self._networksetup, "-setairportpower", interface or "en0", "off"]
            )
            # Turn back on but disconnected
            self._run_command([self._networksetup, "-setairportpower", interface or "en0", "on"])
        else:
            return json.dumps({"success": False, "error": "Unsupported platform"})

        return json.dumps(
            {
                "success": success,
                "message": "Disconnected" if success else output,
            }
        )

    def wifi_status(self) -> str:
        """Get WiFi status."""
        status = {
            "connected": False,
            "ssid": None,
            "signal": None,
            "ip_address": None,
        }

        if self._system == "linux" and self._nmcli:
            success, output = self._run_command(
                [self._nmcli, "-t", "-f", "ACTIVE,SSID,SIGNAL", "device", "wifi"]
            )
            if success:
                for line in output.split("\n"):
                    if line.startswith("yes:"):
                        parts = line.split(":")
                        status["connected"] = True
                        status["ssid"] = parts[1] if len(parts) > 1 else None
                        status["signal"] = (
                            int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
                        )

            # Get IP
            success, output = self._run_command(["hostname", "-I"])
            if success:
                status["ip_address"] = output.strip().split()[0] if output.strip() else None

        elif self._system == "darwin":
            airport = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
            success, output = self._run_command([airport, "-I"])
            if success:
                for line in output.split("\n"):
                    line = line.strip()
                    if "SSID:" in line:
                        status["ssid"] = line.split(":")[1].strip()
                        status["connected"] = True
                    elif "agrCtlRSSI:" in line:
                        try:
                            status["signal"] = int(line.split(":")[1].strip())
                        except ValueError:
                            pass

            # Get IP
            success, output = self._run_command(["ipconfig", "getifaddr", "en0"])
            if success:
                status["ip_address"] = output.strip()

        return json.dumps(status, indent=2)

    def wifi_saved(self) -> str:
        """List saved networks."""
        networks = []

        if self._system == "linux" and self._nmcli:
            success, output = self._run_command(
                [self._nmcli, "-t", "-f", "NAME,TYPE", "connection", "show"]
            )
            if success:
                for line in output.split("\n"):
                    if ":802-11-wireless" in line:
                        networks.append(line.split(":")[0])

        elif self._system == "darwin":
            success, output = self._run_command(
                [self._networksetup, "-listpreferredwirelessnetworks", "en0"]
            )
            if success:
                for line in output.split("\n")[1:]:  # Skip header
                    if line.strip():
                        networks.append(line.strip())

        return json.dumps(
            {
                "success": True,
                "count": len(networks),
                "networks": networks,
            },
            indent=2,
        )

    def wifi_forget(self, ssid: str) -> str:
        """Forget a saved network."""
        if self._system == "linux" and self._nmcli:
            success, output = self._run_command([self._nmcli, "connection", "delete", ssid])
        elif self._system == "darwin":
            success, output = self._run_command(
                [self._networksetup, "-removepreferredwirelessnetwork", "en0", ssid]
            )
        else:
            return json.dumps({"success": False, "error": "Unsupported platform"})

        return json.dumps(
            {
                "success": success,
                "ssid": ssid,
                "message": "Network forgotten" if success else output,
            }
        )

    def wifi_toggle(self, state: str) -> str:
        """Toggle WiFi power."""
        interface = self._get_interface()

        if self._system == "linux" and self._nmcli:
            success, output = self._run_command([self._nmcli, "radio", "wifi", state])
        elif self._system == "darwin":
            success, output = self._run_command(
                [self._networksetup, "-setairportpower", interface or "en0", state]
            )
        else:
            return json.dumps({"success": False, "error": "Unsupported platform"})

        return json.dumps(
            {
                "success": success,
                "wifi": state,
                "message": f"WiFi turned {state}" if success else output,
            }
        )

    def wifi_hotspot(
        self,
        action: str,
        ssid: Optional[str] = None,
        password: Optional[str] = None,
    ) -> str:
        """Manage WiFi hotspot."""
        if self._system != "linux" or not self._nmcli:
            return json.dumps(
                {
                    "success": False,
                    "error": "Hotspot only supported on Linux with NetworkManager",
                }
            )

        if action == "start":
            if not ssid:
                ssid = "R-OS-Hotspot"
            if not password:
                password = "r-os-12345"

            # Create hotspot
            success, output = self._run_command(
                [
                    self._nmcli,
                    "device",
                    "wifi",
                    "hotspot",
                    "ssid",
                    ssid,
                    "password",
                    password,
                ]
            )

            return json.dumps(
                {
                    "success": success,
                    "action": "start",
                    "ssid": ssid,
                    "password": password if success else None,
                    "message": "Hotspot started" if success else output,
                }
            )

        elif action == "stop":
            # Find and disconnect hotspot connection
            success, output = self._run_command([self._nmcli, "connection", "down", "Hotspot"])

            return json.dumps(
                {
                    "success": success,
                    "action": "stop",
                    "message": "Hotspot stopped" if success else output,
                }
            )

        return json.dumps({"success": False, "error": f"Unknown action: {action}"})

    def wifi_info(self) -> str:
        """Get WiFi interface info."""
        info = {
            "platform": self._system,
            "interface": self._get_interface(),
            "tools": {
                "nmcli": self._nmcli is not None,
                "iwconfig": self._iwconfig is not None,
                "networksetup": self._networksetup is not None,
            },
        }

        # Get current status
        status = json.loads(self.wifi_status())
        info.update(status)

        return json.dumps(info, indent=2)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        return self.wifi_status()
