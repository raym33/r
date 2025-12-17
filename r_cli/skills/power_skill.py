"""
Power Skill for R CLI.

System power management:
- Shutdown, reboot, sleep
- Screen brightness
- Volume control
- Battery status
"""

import json
import platform
import shutil
import subprocess
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class PowerSkill(Skill):
    """Skill for system power and hardware control."""

    name = "power"
    description = "Power: shutdown, reboot, sleep, brightness, volume, battery"

    def __init__(self, config=None):
        super().__init__(config)
        self._system = platform.system().lower()

    def _run_command(
        self,
        cmd: list[str],
        timeout: int = 10,
        check: bool = False,
    ) -> tuple[bool, str]:
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
                name="power_shutdown",
                description="Shutdown the system",
                parameters={
                    "type": "object",
                    "properties": {
                        "delay": {
                            "type": "integer",
                            "description": "Delay in minutes before shutdown (default: 0)",
                        },
                        "message": {
                            "type": "string",
                            "description": "Broadcast message to users",
                        },
                    },
                },
                handler=self.power_shutdown,
            ),
            Tool(
                name="power_reboot",
                description="Reboot the system",
                parameters={
                    "type": "object",
                    "properties": {
                        "delay": {
                            "type": "integer",
                            "description": "Delay in minutes before reboot (default: 0)",
                        },
                    },
                },
                handler=self.power_reboot,
            ),
            Tool(
                name="power_sleep",
                description="Put the system to sleep/suspend",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.power_sleep,
            ),
            Tool(
                name="power_cancel",
                description="Cancel a scheduled shutdown or reboot",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.power_cancel,
            ),
            Tool(
                name="power_brightness",
                description="Get or set screen brightness",
                parameters={
                    "type": "object",
                    "properties": {
                        "level": {
                            "type": "integer",
                            "description": "Brightness level (0-100). Omit to get current level.",
                        },
                    },
                },
                handler=self.power_brightness,
            ),
            Tool(
                name="power_volume",
                description="Get or set system volume",
                parameters={
                    "type": "object",
                    "properties": {
                        "level": {
                            "type": "integer",
                            "description": "Volume level (0-100). Omit to get current level.",
                        },
                        "mute": {
                            "type": "boolean",
                            "description": "Mute or unmute",
                        },
                    },
                },
                handler=self.power_volume,
            ),
            Tool(
                name="power_battery",
                description="Get battery status and information",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.power_battery,
            ),
            Tool(
                name="power_info",
                description="Get power and system status overview",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.power_info,
            ),
            Tool(
                name="power_lock",
                description="Lock the screen",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.power_lock,
            ),
            Tool(
                name="power_logout",
                description="Log out current user",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.power_logout,
            ),
        ]

    def power_shutdown(
        self,
        delay: int = 0,
        message: Optional[str] = None,
    ) -> str:
        """Shutdown the system."""
        if self._system == "linux":
            cmd = ["sudo", "shutdown", "-h"]
            if delay > 0:
                cmd.append(f"+{delay}")
            else:
                cmd.append("now")
            if message:
                cmd.append(message)
        elif self._system == "darwin":
            cmd = ["sudo", "shutdown", "-h"]
            if delay > 0:
                cmd.append(f"+{delay}")
            else:
                cmd.append("now")
        elif self._system == "windows":
            cmd = ["shutdown", "/s", "/t", str(delay * 60)]
        else:
            return json.dumps({"success": False, "error": "Unsupported platform"})

        return json.dumps(
            {
                "success": True,
                "action": "shutdown",
                "delay_minutes": delay,
                "command": " ".join(cmd),
                "warning": "System will shutdown. Run power_cancel to abort.",
            }
        )

    def power_reboot(self, delay: int = 0) -> str:
        """Reboot the system."""
        if self._system == "linux" or self._system == "darwin":
            cmd = ["sudo", "shutdown", "-r"]
            if delay > 0:
                cmd.append(f"+{delay}")
            else:
                cmd.append("now")
        elif self._system == "windows":
            cmd = ["shutdown", "/r", "/t", str(delay * 60)]
        else:
            return json.dumps({"success": False, "error": "Unsupported platform"})

        return json.dumps(
            {
                "success": True,
                "action": "reboot",
                "delay_minutes": delay,
                "command": " ".join(cmd),
                "warning": "System will reboot. Run power_cancel to abort.",
            }
        )

    def power_sleep(self) -> str:
        """Put system to sleep."""
        if self._system == "linux":
            cmd = ["systemctl", "suspend"]
        elif self._system == "darwin":
            cmd = ["pmset", "sleepnow"]
        elif self._system == "windows":
            cmd = ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]
        else:
            return json.dumps({"success": False, "error": "Unsupported platform"})

        success, output = self._run_command(cmd)

        return json.dumps(
            {
                "success": success,
                "action": "sleep",
                "message": "System entering sleep mode" if success else output,
            }
        )

    def power_cancel(self) -> str:
        """Cancel scheduled shutdown/reboot."""
        if self._system == "linux" or self._system == "darwin":
            cmd = ["sudo", "shutdown", "-c"]
        elif self._system == "windows":
            cmd = ["shutdown", "/a"]
        else:
            return json.dumps({"success": False, "error": "Unsupported platform"})

        success, output = self._run_command(cmd)

        return json.dumps(
            {
                "success": success,
                "action": "cancel",
                "message": "Scheduled shutdown cancelled" if success else output,
            }
        )

    def power_brightness(self, level: Optional[int] = None) -> str:
        """Get or set screen brightness."""
        if self._system == "linux":
            # Try different methods
            brightness_file = "/sys/class/backlight/*/brightness"
            max_file = "/sys/class/backlight/*/max_brightness"

            # Check if we're on Raspberry Pi with no backlight control
            import glob

            backlight_dirs = glob.glob("/sys/class/backlight/*/brightness")

            if not backlight_dirs:
                return json.dumps(
                    {
                        "success": False,
                        "error": "No backlight control available (common on Raspberry Pi with HDMI)",
                        "suggestion": "Use external monitor controls or vcgencmd for Pi display",
                    }
                )

            if level is not None:
                # Set brightness
                for bf in backlight_dirs:
                    try:
                        max_bf = bf.replace("brightness", "max_brightness")
                        with open(max_bf) as f:
                            max_val = int(f.read().strip())
                        new_val = int((level / 100) * max_val)
                        with open(bf, "w") as f:
                            f.write(str(new_val))
                        return json.dumps(
                            {
                                "success": True,
                                "brightness": level,
                            }
                        )
                    except PermissionError:
                        return json.dumps(
                            {
                                "success": False,
                                "error": "Permission denied. Try running with sudo.",
                            }
                        )
                    except Exception as e:
                        continue

            else:
                # Get brightness
                for bf in backlight_dirs:
                    try:
                        with open(bf) as f:
                            current = int(f.read().strip())
                        max_bf = bf.replace("brightness", "max_brightness")
                        with open(max_bf) as f:
                            max_val = int(f.read().strip())
                        level = int((current / max_val) * 100)
                        return json.dumps(
                            {
                                "success": True,
                                "brightness": level,
                                "raw": current,
                                "max": max_val,
                            }
                        )
                    except Exception:
                        continue

        elif self._system == "darwin":
            if level is not None:
                # Set brightness using AppleScript
                script = f'tell application "System Events" to set value of slider 1 of group 1 of window "Display" of application process "System Preferences" to {level / 100}'
                # Alternative: use brightness command if available
                brightness_cmd = shutil.which("brightness")
                if brightness_cmd:
                    success, output = self._run_command([brightness_cmd, str(level / 100)])
                    return json.dumps(
                        {
                            "success": success,
                            "brightness": level,
                        }
                    )
                else:
                    return json.dumps(
                        {
                            "success": False,
                            "error": "Install brightness command: brew install brightness",
                        }
                    )
            else:
                # Get brightness
                brightness_cmd = shutil.which("brightness")
                if brightness_cmd:
                    success, output = self._run_command([brightness_cmd, "-l"])
                    if success:
                        # Parse output
                        for line in output.split("\n"):
                            if "brightness" in line.lower():
                                try:
                                    val = float(line.split()[-1])
                                    return json.dumps(
                                        {
                                            "success": True,
                                            "brightness": int(val * 100),
                                        }
                                    )
                                except (ValueError, IndexError):
                                    pass

        return json.dumps(
            {
                "success": False,
                "error": "Could not get/set brightness",
            }
        )

    def power_volume(
        self,
        level: Optional[int] = None,
        mute: Optional[bool] = None,
    ) -> str:
        """Get or set system volume."""
        if self._system == "linux":
            # Use amixer
            if mute is not None:
                cmd = ["amixer", "set", "Master", "mute" if mute else "unmute"]
                success, _ = self._run_command(cmd)
                if not success:
                    # Try pulseaudio
                    cmd = ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if mute else "0"]
                    success, _ = self._run_command(cmd)

            if level is not None:
                cmd = ["amixer", "set", "Master", f"{level}%"]
                success, _ = self._run_command(cmd)
                if not success:
                    # Try pulseaudio
                    cmd = ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"]
                    success, _ = self._run_command(cmd)

            # Get current volume
            success, output = self._run_command(["amixer", "get", "Master"])
            if success:
                # Parse volume from output like "[75%]"
                import re

                match = re.search(r"\[(\d+)%\]", output)
                current = int(match.group(1)) if match else None
                muted = "[off]" in output
                return json.dumps(
                    {
                        "success": True,
                        "volume": current,
                        "muted": muted,
                    }
                )

        elif self._system == "darwin":
            if mute is not None:
                cmd = ["osascript", "-e", f"set volume output muted {'true' if mute else 'false'}"]
                self._run_command(cmd)

            if level is not None:
                # macOS volume is 0-100
                cmd = ["osascript", "-e", f"set volume output volume {level}"]
                self._run_command(cmd)

            # Get current volume
            success, output = self._run_command(
                ["osascript", "-e", "output volume of (get volume settings)"]
            )
            success2, output2 = self._run_command(
                ["osascript", "-e", "output muted of (get volume settings)"]
            )

            return json.dumps(
                {
                    "success": True,
                    "volume": int(output.strip()) if success and output.strip().isdigit() else None,
                    "muted": output2.strip().lower() == "true" if success2 else None,
                }
            )

        return json.dumps(
            {
                "success": False,
                "error": "Could not control volume",
            }
        )

    def power_battery(self) -> str:
        """Get battery status."""
        battery = {
            "has_battery": False,
            "percentage": None,
            "charging": None,
            "time_remaining": None,
        }

        if self._system == "linux":
            # Check /sys/class/power_supply
            import glob

            bat_paths = glob.glob("/sys/class/power_supply/BAT*")

            if bat_paths:
                battery["has_battery"] = True
                bat_path = bat_paths[0]

                try:
                    with open(f"{bat_path}/capacity") as f:
                        battery["percentage"] = int(f.read().strip())
                except Exception:
                    pass

                try:
                    with open(f"{bat_path}/status") as f:
                        status = f.read().strip()
                        battery["charging"] = status == "Charging"
                        battery["status"] = status
                except Exception:
                    pass

        elif self._system == "darwin":
            success, output = self._run_command(["pmset", "-g", "batt"])
            if success:
                battery["has_battery"] = "Battery" in output
                # Parse output like "99%; charging; 0:30 remaining"
                import re

                match = re.search(r"(\d+)%", output)
                if match:
                    battery["percentage"] = int(match.group(1))
                battery["charging"] = "charging" in output.lower()
                battery["ac_power"] = "AC Power" in output

                # Time remaining
                time_match = re.search(r"(\d+:\d+) remaining", output)
                if time_match:
                    battery["time_remaining"] = time_match.group(1)

        return json.dumps(battery, indent=2)

    def power_info(self) -> str:
        """Get system power info."""
        info = {
            "platform": self._system,
            "battery": json.loads(self.power_battery()),
        }

        # Uptime
        if self._system == "linux" or self._system == "darwin":
            success, output = self._run_command(["uptime"])
            if success:
                info["uptime"] = output.strip()

        return json.dumps(info, indent=2)

    def power_lock(self) -> str:
        """Lock the screen."""
        if self._system == "linux":
            # Try various lockers
            for locker in [
                "loginctl lock-session",
                "gnome-screensaver-command -l",
                "xdg-screensaver lock",
            ]:
                success, _ = self._run_command(locker.split())
                if success:
                    return json.dumps({"success": True, "action": "lock"})

        elif self._system == "darwin":
            cmd = ["pmset", "displaysleepnow"]
            success, output = self._run_command(cmd)
            return json.dumps(
                {
                    "success": success,
                    "action": "lock",
                }
            )

        return json.dumps({"success": False, "error": "Could not lock screen"})

    def power_logout(self) -> str:
        """Log out current user."""
        if self._system == "linux":
            # Try various methods
            for cmd in [
                ["gnome-session-quit", "--logout"],
                ["loginctl", "terminate-user", "$USER"],
            ]:
                success, _ = self._run_command(cmd)
                if success:
                    break

        elif self._system == "darwin":
            cmd = ["osascript", "-e", 'tell application "System Events" to log out']
            success, output = self._run_command(cmd)

        return json.dumps(
            {
                "success": True,
                "action": "logout",
                "warning": "User session will end",
            }
        )

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        return self.power_info()
