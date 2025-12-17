"""
Bluetooth Skill for R CLI.

Bluetooth device management:
- Scan for devices
- Pair/unpair devices
- Connect/disconnect
- Send/receive data
"""

import json
import shutil
import subprocess
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class BluetoothSkill(Skill):
    """Skill for Bluetooth operations."""

    name = "bluetooth"
    description = "Bluetooth: scan, pair, connect, and manage devices"

    def __init__(self, config=None):
        super().__init__(config)
        self._bluetoothctl = shutil.which("bluetoothctl")
        self._hcitool = shutil.which("hcitool")

    def _run_bluetoothctl(self, *commands: str, timeout: int = 10) -> tuple[bool, str]:
        """Run bluetoothctl commands."""
        if not self._bluetoothctl:
            return False, "bluetoothctl not found. Install bluez package."

        try:
            # Build command sequence
            cmd_input = "\n".join(commands) + "\nexit\n"
            result = subprocess.run(
                [self._bluetoothctl],
                check=False,
                input=cmd_input,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return True, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    def _parse_devices(self, output: str) -> list[dict]:
        """Parse device list from bluetoothctl output."""
        devices = []
        for line in output.split("\n"):
            if "Device" in line:
                parts = line.split()
                if len(parts) >= 3:
                    mac_idx = next(
                        (i for i, p in enumerate(parts) if ":" in p and len(p) == 17), None
                    )
                    if mac_idx is not None:
                        mac = parts[mac_idx]
                        name = (
                            " ".join(parts[mac_idx + 1 :])
                            if mac_idx + 1 < len(parts)
                            else "Unknown"
                        )
                        devices.append({"mac": mac, "name": name})
        return devices

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="bluetooth_scan",
                description="Scan for nearby Bluetooth devices",
                parameters={
                    "type": "object",
                    "properties": {
                        "duration": {
                            "type": "integer",
                            "description": "Scan duration in seconds (default: 10)",
                        },
                    },
                },
                handler=self.bluetooth_scan,
            ),
            Tool(
                name="bluetooth_devices",
                description="List paired/known Bluetooth devices",
                parameters={
                    "type": "object",
                    "properties": {
                        "paired_only": {
                            "type": "boolean",
                            "description": "Show only paired devices",
                        },
                    },
                },
                handler=self.bluetooth_devices,
            ),
            Tool(
                name="bluetooth_pair",
                description="Pair with a Bluetooth device",
                parameters={
                    "type": "object",
                    "properties": {
                        "mac": {
                            "type": "string",
                            "description": "Device MAC address (XX:XX:XX:XX:XX:XX)",
                        },
                    },
                    "required": ["mac"],
                },
                handler=self.bluetooth_pair,
            ),
            Tool(
                name="bluetooth_unpair",
                description="Remove a paired Bluetooth device",
                parameters={
                    "type": "object",
                    "properties": {
                        "mac": {
                            "type": "string",
                            "description": "Device MAC address",
                        },
                    },
                    "required": ["mac"],
                },
                handler=self.bluetooth_unpair,
            ),
            Tool(
                name="bluetooth_connect",
                description="Connect to a paired Bluetooth device",
                parameters={
                    "type": "object",
                    "properties": {
                        "mac": {
                            "type": "string",
                            "description": "Device MAC address",
                        },
                    },
                    "required": ["mac"],
                },
                handler=self.bluetooth_connect,
            ),
            Tool(
                name="bluetooth_disconnect",
                description="Disconnect from a Bluetooth device",
                parameters={
                    "type": "object",
                    "properties": {
                        "mac": {
                            "type": "string",
                            "description": "Device MAC address",
                        },
                    },
                    "required": ["mac"],
                },
                handler=self.bluetooth_disconnect,
            ),
            Tool(
                name="bluetooth_trust",
                description="Trust a device for automatic connection",
                parameters={
                    "type": "object",
                    "properties": {
                        "mac": {
                            "type": "string",
                            "description": "Device MAC address",
                        },
                    },
                    "required": ["mac"],
                },
                handler=self.bluetooth_trust,
            ),
            Tool(
                name="bluetooth_info",
                description="Get Bluetooth adapter information",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.bluetooth_info,
            ),
            Tool(
                name="bluetooth_power",
                description="Turn Bluetooth adapter on or off",
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
                handler=self.bluetooth_power,
            ),
            Tool(
                name="bluetooth_discoverable",
                description="Set Bluetooth discoverable mode",
                parameters={
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "description": "Discoverable state: 'on' or 'off'",
                            "enum": ["on", "off"],
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Discoverable timeout in seconds (0 = forever)",
                        },
                    },
                    "required": ["state"],
                },
                handler=self.bluetooth_discoverable,
            ),
        ]

    def bluetooth_scan(self, duration: int = 10) -> str:
        """Scan for Bluetooth devices."""
        success, output = self._run_bluetoothctl(
            "power on",
            "scan on",
            f"# Scanning for {duration} seconds...",
        )

        if not success:
            return json.dumps({"success": False, "error": output})

        # Wait for scan
        import time

        time.sleep(duration)

        # Stop scan and get devices
        success, output = self._run_bluetoothctl("scan off", "devices")

        if not success:
            return json.dumps({"success": False, "error": output})

        devices = self._parse_devices(output)

        return json.dumps(
            {
                "success": True,
                "duration": duration,
                "devices_found": len(devices),
                "devices": devices,
            },
            indent=2,
        )

    def bluetooth_devices(self, paired_only: bool = False) -> str:
        """List Bluetooth devices."""
        cmd = "paired-devices" if paired_only else "devices"
        success, output = self._run_bluetoothctl(cmd)

        if not success:
            return json.dumps({"success": False, "error": output})

        devices = self._parse_devices(output)

        return json.dumps(
            {
                "success": True,
                "type": "paired" if paired_only else "all",
                "count": len(devices),
                "devices": devices,
            },
            indent=2,
        )

    def bluetooth_pair(self, mac: str) -> str:
        """Pair with a device."""
        success, output = self._run_bluetoothctl(
            "power on",
            f"pair {mac}",
            timeout=30,
        )

        paired = "Pairing successful" in output or "already paired" in output.lower()

        return json.dumps(
            {
                "success": paired,
                "mac": mac,
                "message": "Device paired" if paired else "Pairing failed",
                "output": output if not paired else None,
            }
        )

    def bluetooth_unpair(self, mac: str) -> str:
        """Remove a paired device."""
        success, output = self._run_bluetoothctl(f"remove {mac}")

        removed = "Device has been removed" in output or success

        return json.dumps(
            {
                "success": removed,
                "mac": mac,
                "message": "Device removed" if removed else "Failed to remove device",
            }
        )

    def bluetooth_connect(self, mac: str) -> str:
        """Connect to a device."""
        success, output = self._run_bluetoothctl(
            f"connect {mac}",
            timeout=15,
        )

        connected = "Connection successful" in output or "Connected: yes" in output

        return json.dumps(
            {
                "success": connected,
                "mac": mac,
                "message": "Connected" if connected else "Connection failed",
                "output": output if not connected else None,
            }
        )

    def bluetooth_disconnect(self, mac: str) -> str:
        """Disconnect from a device."""
        success, output = self._run_bluetoothctl(f"disconnect {mac}")

        disconnected = "Successful disconnected" in output or success

        return json.dumps(
            {
                "success": disconnected,
                "mac": mac,
                "message": "Disconnected" if disconnected else "Failed to disconnect",
            }
        )

    def bluetooth_trust(self, mac: str) -> str:
        """Trust a device."""
        success, output = self._run_bluetoothctl(f"trust {mac}")

        trusted = "trust succeeded" in output.lower() or success

        return json.dumps(
            {
                "success": trusted,
                "mac": mac,
                "message": "Device trusted" if trusted else "Failed to trust device",
            }
        )

    def bluetooth_info(self) -> str:
        """Get adapter information."""
        success, output = self._run_bluetoothctl("show")

        if not success:
            return json.dumps({"success": False, "error": output})

        # Parse adapter info
        info = {
            "available": True,
            "bluetoothctl": self._bluetoothctl is not None,
        }

        for line in output.split("\n"):
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower().replace(" ", "_")
                value = value.strip()
                if key in ["name", "alias", "address", "powered", "discoverable", "pairable"]:
                    info[key] = value

        return json.dumps(info, indent=2)

    def bluetooth_power(self, state: str) -> str:
        """Control Bluetooth power."""
        success, output = self._run_bluetoothctl(f"power {state}")

        return json.dumps(
            {
                "success": success,
                "power": state,
                "message": f"Bluetooth powered {state}"
                if success
                else "Failed to change power state",
            }
        )

    def bluetooth_discoverable(
        self,
        state: str,
        timeout: Optional[int] = None,
    ) -> str:
        """Set discoverable mode."""
        commands = [f"discoverable {state}"]
        if timeout is not None:
            commands.append(f"discoverable-timeout {timeout}")

        success, output = self._run_bluetoothctl(*commands)

        return json.dumps(
            {
                "success": success,
                "discoverable": state,
                "timeout": timeout,
            }
        )

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        return self.bluetooth_info()
