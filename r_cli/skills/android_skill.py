"""
Android Skill for R CLI.

Android device control via bridges:
- SMS, calls, contacts
- Camera, gallery
- Apps, notifications
- Sensors, location

This skill requires the R OS Android app to provide the bridge.
When running on Android (via Chaquopy/Kivy), it uses native APIs.
When running externally, it connects via ADB or HTTP bridge.
"""

import json
import shutil
import subprocess
from typing import Any, Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class AndroidSkill(Skill):
    """Skill for Android device control."""

    name = "android"
    description = "Android: SMS, calls, camera, apps, notifications, sensors"

    def __init__(self, config=None):
        super().__init__(config)
        self._adb = shutil.which("adb")
        self._bridge_url: Optional[str] = None
        self._is_android = self._check_android()

    def _check_android(self) -> bool:
        """Check if running on Android."""
        try:
            # Check for Android-specific paths
            import os

            return os.path.exists("/system/build.prop")
        except Exception:
            return False

    def _run_adb(self, *args: str, timeout: int = 30) -> tuple[bool, str]:
        """Run ADB command."""
        if not self._adb:
            return False, "ADB not found. Install Android SDK or connect to device."

        try:
            cmd = [self._adb] + list(args)
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "ADB command timed out"
        except Exception as e:
            return False, str(e)

    def _call_bridge(self, action: str, params: dict) -> dict:
        """Call Android bridge API."""
        if self._bridge_url:
            try:
                import urllib.parse
                import urllib.request

                data = json.dumps({"action": action, "params": params}).encode()
                req = urllib.request.Request(
                    f"{self._bridge_url}/api/{action}",
                    data=data,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return json.loads(resp.read().decode())
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "No bridge connection"}

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="android_sms_send",
                description="Send an SMS message",
                parameters={
                    "type": "object",
                    "properties": {
                        "phone": {
                            "type": "string",
                            "description": "Phone number",
                        },
                        "message": {
                            "type": "string",
                            "description": "Message text",
                        },
                    },
                    "required": ["phone", "message"],
                },
                handler=self.android_sms_send,
            ),
            Tool(
                name="android_sms_list",
                description="List recent SMS messages",
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Number of messages to retrieve",
                        },
                        "folder": {
                            "type": "string",
                            "description": "Folder: 'inbox', 'sent', or 'all'",
                            "enum": ["inbox", "sent", "all"],
                        },
                    },
                },
                handler=self.android_sms_list,
            ),
            Tool(
                name="android_call",
                description="Make a phone call",
                parameters={
                    "type": "object",
                    "properties": {
                        "phone": {
                            "type": "string",
                            "description": "Phone number to call",
                        },
                    },
                    "required": ["phone"],
                },
                handler=self.android_call,
            ),
            Tool(
                name="android_contacts",
                description="List or search contacts",
                parameters={
                    "type": "object",
                    "properties": {
                        "search": {
                            "type": "string",
                            "description": "Search query (name or phone)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum contacts to return",
                        },
                    },
                },
                handler=self.android_contacts,
            ),
            Tool(
                name="android_photo",
                description="Take a photo with the camera",
                parameters={
                    "type": "object",
                    "properties": {
                        "camera": {
                            "type": "string",
                            "description": "Camera: 'back' or 'front'",
                            "enum": ["back", "front"],
                        },
                        "output": {
                            "type": "string",
                            "description": "Output file path",
                        },
                    },
                },
                handler=self.android_photo,
            ),
            Tool(
                name="android_notification",
                description="Show a notification",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Notification title",
                        },
                        "message": {
                            "type": "string",
                            "description": "Notification body",
                        },
                        "priority": {
                            "type": "string",
                            "description": "Priority: 'low', 'default', 'high'",
                            "enum": ["low", "default", "high"],
                        },
                    },
                    "required": ["title", "message"],
                },
                handler=self.android_notification,
            ),
            Tool(
                name="android_app_launch",
                description="Launch an application",
                parameters={
                    "type": "object",
                    "properties": {
                        "package": {
                            "type": "string",
                            "description": "App package name (e.g., com.whatsapp)",
                        },
                    },
                    "required": ["package"],
                },
                handler=self.android_app_launch,
            ),
            Tool(
                name="android_apps_list",
                description="List installed applications",
                parameters={
                    "type": "object",
                    "properties": {
                        "system": {
                            "type": "boolean",
                            "description": "Include system apps",
                        },
                    },
                },
                handler=self.android_apps_list,
            ),
            Tool(
                name="android_location",
                description="Get current GPS location",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.android_location,
            ),
            Tool(
                name="android_sensors",
                description="Read device sensors (accelerometer, gyroscope, etc.)",
                parameters={
                    "type": "object",
                    "properties": {
                        "sensor": {
                            "type": "string",
                            "description": "Sensor type: 'accelerometer', 'gyroscope', 'light', 'proximity', 'all'",
                        },
                    },
                },
                handler=self.android_sensors,
            ),
            Tool(
                name="android_battery",
                description="Get battery information",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.android_battery,
            ),
            Tool(
                name="android_volume",
                description="Get or set volume",
                parameters={
                    "type": "object",
                    "properties": {
                        "stream": {
                            "type": "string",
                            "description": "Stream: 'media', 'ring', 'alarm', 'notification'",
                            "enum": ["media", "ring", "alarm", "notification"],
                        },
                        "level": {
                            "type": "integer",
                            "description": "Volume level (0-100). Omit to get current.",
                        },
                    },
                },
                handler=self.android_volume,
            ),
            Tool(
                name="android_screen",
                description="Control screen (on/off, brightness)",
                parameters={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "Action: 'on', 'off', 'brightness'",
                            "enum": ["on", "off", "brightness"],
                        },
                        "value": {
                            "type": "integer",
                            "description": "Brightness value (0-255) if action is 'brightness'",
                        },
                    },
                    "required": ["action"],
                },
                handler=self.android_screen,
            ),
            Tool(
                name="android_clipboard",
                description="Get or set clipboard content",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to set. Omit to get current clipboard.",
                        },
                    },
                },
                handler=self.android_clipboard,
            ),
            Tool(
                name="android_info",
                description="Get device information",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.android_info,
            ),
            Tool(
                name="android_connect",
                description="Connect to Android device or bridge",
                parameters={
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "description": "Connection method: 'adb' or 'bridge'",
                            "enum": ["adb", "bridge"],
                        },
                        "address": {
                            "type": "string",
                            "description": "Device address (IP:port for wireless ADB or bridge URL)",
                        },
                    },
                    "required": ["method"],
                },
                handler=self.android_connect,
            ),
        ]

    def android_sms_send(self, phone: str, message: str) -> str:
        """Send an SMS."""
        if self._is_android:
            # Native Android - would use SmsManager
            return json.dumps(
                {
                    "success": False,
                    "error": "Native Android SMS requires R OS app bridge",
                }
            )

        # Via ADB
        if self._adb:
            # URI encode the message
            import urllib.parse

            encoded = urllib.parse.quote(message)
            success, output = self._run_adb(
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.SENDTO",
                "-d",
                f"sms:{phone}",
                "--es",
                "sms_body",
                f'"{message}"',
            )
            return json.dumps(
                {
                    "success": success,
                    "phone": phone,
                    "message": "SMS intent sent" if success else output,
                    "note": "Opens SMS app with pre-filled message",
                }
            )

        return self._bridge_result("sms_send", {"phone": phone, "message": message})

    def android_sms_list(
        self,
        limit: int = 10,
        folder: str = "inbox",
    ) -> str:
        """List SMS messages."""
        if self._adb:
            success, output = self._run_adb(
                "shell",
                "content",
                "query",
                "--uri",
                "content://sms",
                "--projection",
                "address:body:date",
                "--limit",
                str(limit),
            )
            if success:
                messages = []
                # Parse content query output
                for line in output.split("\n"):
                    if "Row:" in line:
                        continue
                    if "address=" in line:
                        parts = line.split(", ")
                        msg = {}
                        for part in parts:
                            if "=" in part:
                                key, val = part.split("=", 1)
                                msg[key.strip()] = val.strip()
                        if msg:
                            messages.append(msg)

                return json.dumps(
                    {
                        "success": True,
                        "count": len(messages),
                        "messages": messages[:limit],
                    }
                )

        return self._bridge_result("sms_list", {"limit": limit, "folder": folder})

    def android_call(self, phone: str) -> str:
        """Make a phone call."""
        if self._adb:
            success, output = self._run_adb(
                "shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{phone}"
            )
            return json.dumps(
                {
                    "success": success,
                    "phone": phone,
                    "message": "Call initiated" if success else output,
                }
            )

        return self._bridge_result("call", {"phone": phone})

    def android_contacts(
        self,
        search: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """List or search contacts."""
        if self._adb:
            success, output = self._run_adb(
                "shell",
                "content",
                "query",
                "--uri",
                "content://contacts/phones",
                "--projection",
                "display_name:number",
            )
            if success:
                contacts = []
                for line in output.split("\n"):
                    if "display_name=" in line:
                        parts = line.split(", ")
                        contact = {}
                        for part in parts:
                            if "=" in part:
                                key, val = part.split("=", 1)
                                contact[key.strip()] = val.strip()
                        if contact:
                            if search is None or search.lower() in str(contact).lower():
                                contacts.append(contact)

                return json.dumps(
                    {
                        "success": True,
                        "count": len(contacts[:limit]),
                        "contacts": contacts[:limit],
                    }
                )

        return self._bridge_result("contacts", {"search": search, "limit": limit})

    def android_photo(
        self,
        camera: str = "back",
        output: Optional[str] = None,
    ) -> str:
        """Take a photo."""
        if self._adb:
            output_path = output or "/sdcard/DCIM/r_cli_photo.jpg"
            success, out = self._run_adb(
                "shell",
                "am",
                "start",
                "-a",
                "android.media.action.IMAGE_CAPTURE",
                "--ez",
                "android.intent.extra.USE_FRONT_CAMERA",
                "true" if camera == "front" else "false",
            )
            return json.dumps(
                {
                    "success": success,
                    "message": "Camera app opened" if success else out,
                    "note": "Use android_photo via bridge for automated capture",
                }
            )

        return self._bridge_result("photo", {"camera": camera, "output": output})

    def android_notification(
        self,
        title: str,
        message: str,
        priority: str = "default",
    ) -> str:
        """Show a notification."""
        # ADB can't create notifications directly
        # This requires the bridge app
        return self._bridge_result(
            "notification",
            {
                "title": title,
                "message": message,
                "priority": priority,
            },
        )

    def android_app_launch(self, package: str) -> str:
        """Launch an app."""
        if self._adb:
            success, output = self._run_adb(
                "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"
            )
            return json.dumps(
                {
                    "success": success,
                    "package": package,
                    "message": "App launched" if success else output,
                }
            )

        return self._bridge_result("app_launch", {"package": package})

    def android_apps_list(self, system: bool = False) -> str:
        """List installed apps."""
        if self._adb:
            flag = "-f" if system else "-3"  # -3 = third party only
            success, output = self._run_adb("shell", "pm", "list", "packages", flag)
            if success:
                apps = []
                for line in output.split("\n"):
                    if line.startswith("package:"):
                        apps.append(line.replace("package:", "").strip())

                return json.dumps(
                    {
                        "success": True,
                        "count": len(apps),
                        "apps": sorted(apps),
                    }
                )

        return self._bridge_result("apps_list", {"system": system})

    def android_location(self) -> str:
        """Get GPS location."""
        if self._adb:
            success, output = self._run_adb("shell", "dumpsys", "location")
            if success:
                # Parse location from dumpsys
                location = {"available": True}
                for line in output.split("\n"):
                    if "last location=" in line.lower():
                        location["raw"] = line.strip()
                        break

                return json.dumps(location, indent=2)

        return self._bridge_result("location", {})

    def android_sensors(self, sensor: str = "all") -> str:
        """Read sensors."""
        if self._adb:
            success, output = self._run_adb("shell", "dumpsys", "sensorservice")
            if success:
                sensors = []
                for line in output.split("\n"):
                    if "Sensor" in line and "=" in line:
                        sensors.append(line.strip())

                return json.dumps(
                    {
                        "success": True,
                        "sensor_count": len(sensors),
                        "raw_output": output[:2000],  # Truncate
                    }
                )

        return self._bridge_result("sensors", {"sensor": sensor})

    def android_battery(self) -> str:
        """Get battery info."""
        if self._adb:
            success, output = self._run_adb("shell", "dumpsys", "battery")
            if success:
                battery = {}
                for line in output.split("\n"):
                    line = line.strip()
                    if ":" in line:
                        key, val = line.split(":", 1)
                        battery[key.strip().lower().replace(" ", "_")] = val.strip()

                return json.dumps(
                    {
                        "success": True,
                        "level": battery.get("level"),
                        "status": battery.get("status"),
                        "health": battery.get("health"),
                        "plugged": battery.get("plugged"),
                        "temperature": battery.get("temperature"),
                    }
                )

        return self._bridge_result("battery", {})

    def android_volume(
        self,
        stream: str = "media",
        level: Optional[int] = None,
    ) -> str:
        """Get or set volume."""
        if self._adb:
            stream_map = {
                "media": "3",
                "ring": "2",
                "alarm": "4",
                "notification": "5",
            }
            stream_id = stream_map.get(stream, "3")

            if level is not None:
                # Set volume (0-15 scale typically)
                adb_level = int((level / 100) * 15)
                success, output = self._run_adb(
                    "shell", "media", "volume", "--stream", stream_id, "--set", str(adb_level)
                )
                return json.dumps(
                    {
                        "success": success,
                        "stream": stream,
                        "level": level,
                    }
                )

            # Get volume
            success, output = self._run_adb(
                "shell", "media", "volume", "--stream", stream_id, "--get"
            )
            return json.dumps(
                {
                    "success": success,
                    "stream": stream,
                    "raw": output.strip() if success else None,
                }
            )

        return self._bridge_result("volume", {"stream": stream, "level": level})

    def android_screen(
        self,
        action: str,
        value: Optional[int] = None,
    ) -> str:
        """Control screen."""
        if self._adb:
            if action == "on":
                success, output = self._run_adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
            elif action == "off":
                success, output = self._run_adb("shell", "input", "keyevent", "KEYCODE_SLEEP")
            elif action == "brightness" and value is not None:
                success, output = self._run_adb(
                    "shell", "settings", "put", "system", "screen_brightness", str(value)
                )
            else:
                return json.dumps({"success": False, "error": f"Unknown action: {action}"})

            return json.dumps(
                {
                    "success": success,
                    "action": action,
                    "value": value,
                }
            )

        return self._bridge_result("screen", {"action": action, "value": value})

    def android_clipboard(self, text: Optional[str] = None) -> str:
        """Get or set clipboard."""
        if self._adb:
            if text is not None:
                # Set clipboard
                success, output = self._run_adb(
                    "shell", "am", "broadcast", "-a", "clipper.set", "-e", "text", f'"{text}"'
                )
                return json.dumps(
                    {
                        "success": success,
                        "action": "set",
                        "note": "Requires Clipper app for full clipboard access",
                    }
                )

            # Get clipboard is tricky via ADB
            return json.dumps(
                {
                    "success": False,
                    "error": "Getting clipboard requires bridge app",
                }
            )

        return self._bridge_result("clipboard", {"text": text})

    def android_info(self) -> str:
        """Get device information."""
        if self._adb:
            info = {"connected": True}

            # Get device model
            success, output = self._run_adb("shell", "getprop", "ro.product.model")
            if success:
                info["model"] = output.strip()

            # Get Android version
            success, output = self._run_adb("shell", "getprop", "ro.build.version.release")
            if success:
                info["android_version"] = output.strip()

            # Get device name
            success, output = self._run_adb("shell", "getprop", "ro.product.device")
            if success:
                info["device"] = output.strip()

            # Get serial
            success, output = self._run_adb("get-serialno")
            if success:
                info["serial"] = output.strip()

            return json.dumps(info, indent=2)

        return json.dumps(
            {
                "is_android": self._is_android,
                "adb_available": self._adb is not None,
                "bridge_url": self._bridge_url,
            },
            indent=2,
        )

    def android_connect(
        self,
        method: str,
        address: Optional[str] = None,
    ) -> str:
        """Connect to Android device."""
        if method == "adb":
            if address:
                # Wireless ADB
                success, output = self._run_adb("connect", address)
                return json.dumps(
                    {
                        "success": success,
                        "method": "adb",
                        "address": address,
                        "message": output.strip(),
                    }
                )
            else:
                # Check existing connection
                success, output = self._run_adb("devices")
                return json.dumps(
                    {
                        "success": success,
                        "method": "adb",
                        "devices": output.strip(),
                    }
                )

        elif method == "bridge":
            self._bridge_url = address or "http://localhost:8080"
            # Test connection
            result = self._call_bridge("ping", {})
            return json.dumps(
                {
                    "success": result.get("success", False),
                    "method": "bridge",
                    "url": self._bridge_url,
                    "message": result.get("message", "Bridge configured"),
                }
            )

        return json.dumps({"success": False, "error": f"Unknown method: {method}"})

    def _bridge_result(self, action: str, params: dict) -> str:
        """Helper to return bridge result or error."""
        if self._bridge_url:
            result = self._call_bridge(action, params)
            return json.dumps(result, indent=2)

        return json.dumps(
            {
                "success": False,
                "error": "Not connected. Use android_connect first.",
                "available_methods": ["adb", "bridge"],
                "adb_installed": self._adb is not None,
            }
        )

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        return self.android_info()
