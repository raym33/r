"""
GPIO Skill for R CLI.

Raspberry Pi GPIO control:
- Pin setup and configuration
- Digital read/write
- PWM control
- Event detection
"""

import json
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool

# Try to import RPi.GPIO, gracefully handle if not on Pi
try:
    from RPi import GPIO

    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    GPIO = None


class GPIOSkill(Skill):
    """Skill for Raspberry Pi GPIO operations."""

    name = "gpio"
    description = "GPIO: Raspberry Pi pin control, digital I/O, PWM"

    # Common pin mappings (BCM mode)
    COMMON_PINS = {
        "led": 17,
        "button": 27,
        "buzzer": 22,
        "relay": 23,
        "servo": 18,
        "motor_a": 24,
        "motor_b": 25,
    }

    def __init__(self, config=None):
        super().__init__(config)
        self._initialized = False
        self._pwm_instances = {}

    def _ensure_gpio(self) -> bool:
        """Initialize GPIO if available."""
        if not GPIO_AVAILABLE:
            return False
        if not self._initialized:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            self._initialized = True
        return True

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="gpio_setup",
                description="Configure a GPIO pin as input or output",
                parameters={
                    "type": "object",
                    "properties": {
                        "pin": {
                            "type": "integer",
                            "description": "GPIO pin number (BCM mode)",
                        },
                        "mode": {
                            "type": "string",
                            "description": "Pin mode: 'input' or 'output'",
                            "enum": ["input", "output"],
                        },
                        "pull": {
                            "type": "string",
                            "description": "Pull resistor: 'up', 'down', or 'none'",
                            "enum": ["up", "down", "none"],
                        },
                    },
                    "required": ["pin", "mode"],
                },
                handler=self.gpio_setup,
            ),
            Tool(
                name="gpio_write",
                description="Set a GPIO pin HIGH (1) or LOW (0)",
                parameters={
                    "type": "object",
                    "properties": {
                        "pin": {
                            "type": "integer",
                            "description": "GPIO pin number (BCM mode)",
                        },
                        "value": {
                            "type": "integer",
                            "description": "Value: 1 (HIGH) or 0 (LOW)",
                            "enum": [0, 1],
                        },
                    },
                    "required": ["pin", "value"],
                },
                handler=self.gpio_write,
            ),
            Tool(
                name="gpio_read",
                description="Read the current state of a GPIO pin",
                parameters={
                    "type": "object",
                    "properties": {
                        "pin": {
                            "type": "integer",
                            "description": "GPIO pin number (BCM mode)",
                        },
                    },
                    "required": ["pin"],
                },
                handler=self.gpio_read,
            ),
            Tool(
                name="gpio_pwm_start",
                description="Start PWM output on a pin",
                parameters={
                    "type": "object",
                    "properties": {
                        "pin": {
                            "type": "integer",
                            "description": "GPIO pin number (BCM mode)",
                        },
                        "frequency": {
                            "type": "number",
                            "description": "PWM frequency in Hz",
                        },
                        "duty_cycle": {
                            "type": "number",
                            "description": "Duty cycle (0-100)",
                        },
                    },
                    "required": ["pin", "frequency", "duty_cycle"],
                },
                handler=self.gpio_pwm_start,
            ),
            Tool(
                name="gpio_pwm_stop",
                description="Stop PWM output on a pin",
                parameters={
                    "type": "object",
                    "properties": {
                        "pin": {
                            "type": "integer",
                            "description": "GPIO pin number (BCM mode)",
                        },
                    },
                    "required": ["pin"],
                },
                handler=self.gpio_pwm_stop,
            ),
            Tool(
                name="gpio_pwm_duty",
                description="Change PWM duty cycle",
                parameters={
                    "type": "object",
                    "properties": {
                        "pin": {
                            "type": "integer",
                            "description": "GPIO pin number (BCM mode)",
                        },
                        "duty_cycle": {
                            "type": "number",
                            "description": "New duty cycle (0-100)",
                        },
                    },
                    "required": ["pin", "duty_cycle"],
                },
                handler=self.gpio_pwm_duty,
            ),
            Tool(
                name="gpio_cleanup",
                description="Clean up GPIO resources",
                parameters={
                    "type": "object",
                    "properties": {
                        "pin": {
                            "type": "integer",
                            "description": "Specific pin to clean up (optional, cleans all if not specified)",
                        },
                    },
                },
                handler=self.gpio_cleanup,
            ),
            Tool(
                name="gpio_info",
                description="Get GPIO pin information and status",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.gpio_info,
            ),
            Tool(
                name="gpio_servo",
                description="Control a servo motor (simplified interface)",
                parameters={
                    "type": "object",
                    "properties": {
                        "pin": {
                            "type": "integer",
                            "description": "GPIO pin number (BCM mode)",
                        },
                        "angle": {
                            "type": "number",
                            "description": "Servo angle (0-180 degrees)",
                        },
                    },
                    "required": ["pin", "angle"],
                },
                handler=self.gpio_servo,
            ),
            Tool(
                name="gpio_blink",
                description="Blink an LED on a pin",
                parameters={
                    "type": "object",
                    "properties": {
                        "pin": {
                            "type": "integer",
                            "description": "GPIO pin number (BCM mode)",
                        },
                        "times": {
                            "type": "integer",
                            "description": "Number of blinks",
                        },
                        "interval": {
                            "type": "number",
                            "description": "Interval in seconds",
                        },
                    },
                    "required": ["pin"],
                },
                handler=self.gpio_blink,
            ),
        ]

    def gpio_setup(
        self,
        pin: int,
        mode: str,
        pull: str = "none",
    ) -> str:
        """Configure a GPIO pin."""
        if not self._ensure_gpio():
            return json.dumps(
                {
                    "success": False,
                    "error": "GPIO not available. Are you running on a Raspberry Pi?",
                }
            )

        try:
            gpio_mode = GPIO.OUT if mode == "output" else GPIO.IN

            if mode == "input":
                pull_map = {
                    "up": GPIO.PUD_UP,
                    "down": GPIO.PUD_DOWN,
                    "none": GPIO.PUD_OFF,
                }
                GPIO.setup(pin, gpio_mode, pull_up_down=pull_map.get(pull, GPIO.PUD_OFF))
            else:
                GPIO.setup(pin, gpio_mode)

            return json.dumps(
                {
                    "success": True,
                    "pin": pin,
                    "mode": mode,
                    "pull": pull if mode == "input" else None,
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def gpio_write(self, pin: int, value: int) -> str:
        """Write to a GPIO pin."""
        if not self._ensure_gpio():
            return json.dumps(
                {
                    "success": False,
                    "error": "GPIO not available",
                }
            )

        try:
            GPIO.output(pin, GPIO.HIGH if value else GPIO.LOW)
            return json.dumps(
                {
                    "success": True,
                    "pin": pin,
                    "value": value,
                    "state": "HIGH" if value else "LOW",
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def gpio_read(self, pin: int) -> str:
        """Read from a GPIO pin."""
        if not self._ensure_gpio():
            return json.dumps(
                {
                    "success": False,
                    "error": "GPIO not available",
                }
            )

        try:
            value = GPIO.input(pin)
            return json.dumps(
                {
                    "success": True,
                    "pin": pin,
                    "value": value,
                    "state": "HIGH" if value else "LOW",
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def gpio_pwm_start(
        self,
        pin: int,
        frequency: float,
        duty_cycle: float,
    ) -> str:
        """Start PWM on a pin."""
        if not self._ensure_gpio():
            return json.dumps(
                {
                    "success": False,
                    "error": "GPIO not available",
                }
            )

        try:
            # Setup pin as output first
            GPIO.setup(pin, GPIO.OUT)

            # Create PWM instance
            pwm = GPIO.PWM(pin, frequency)
            pwm.start(duty_cycle)
            self._pwm_instances[pin] = pwm

            return json.dumps(
                {
                    "success": True,
                    "pin": pin,
                    "frequency": frequency,
                    "duty_cycle": duty_cycle,
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def gpio_pwm_stop(self, pin: int) -> str:
        """Stop PWM on a pin."""
        if pin in self._pwm_instances:
            self._pwm_instances[pin].stop()
            del self._pwm_instances[pin]
            return json.dumps({"success": True, "pin": pin, "stopped": True})
        return json.dumps({"success": False, "error": f"No PWM running on pin {pin}"})

    def gpio_pwm_duty(self, pin: int, duty_cycle: float) -> str:
        """Change PWM duty cycle."""
        if pin in self._pwm_instances:
            self._pwm_instances[pin].ChangeDutyCycle(duty_cycle)
            return json.dumps(
                {
                    "success": True,
                    "pin": pin,
                    "duty_cycle": duty_cycle,
                }
            )
        return json.dumps({"success": False, "error": f"No PWM running on pin {pin}"})

    def gpio_cleanup(self, pin: Optional[int] = None) -> str:
        """Clean up GPIO resources."""
        if not GPIO_AVAILABLE:
            return json.dumps({"success": True, "message": "GPIO not available"})

        try:
            # Stop all PWM
            for p, pwm in list(self._pwm_instances.items()):
                if pin is None or p == pin:
                    pwm.stop()
                    del self._pwm_instances[p]

            if pin is not None:
                GPIO.cleanup(pin)
            else:
                GPIO.cleanup()
                self._initialized = False

            return json.dumps(
                {
                    "success": True,
                    "cleaned": "all" if pin is None else pin,
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def gpio_info(self) -> str:
        """Get GPIO information."""
        info = {
            "available": GPIO_AVAILABLE,
            "initialized": self._initialized,
            "mode": "BCM",
            "active_pwm": list(self._pwm_instances.keys()),
            "common_pins": self.COMMON_PINS,
        }

        if GPIO_AVAILABLE:
            info["pi_revision"] = GPIO.RPI_INFO.get("P1_REVISION", "unknown")
            info["pi_type"] = GPIO.RPI_INFO.get("TYPE", "unknown")

        return json.dumps(info, indent=2)

    def gpio_servo(self, pin: int, angle: float) -> str:
        """Control a servo motor."""
        if not self._ensure_gpio():
            return json.dumps(
                {
                    "success": False,
                    "error": "GPIO not available",
                }
            )

        try:
            # Servo typically uses 50Hz, duty cycle 2-12% for 0-180 degrees
            angle = max(0, min(180, angle))
            duty_cycle = 2 + (angle / 180) * 10  # 2% = 0°, 12% = 180°

            GPIO.setup(pin, GPIO.OUT)

            if pin not in self._pwm_instances:
                pwm = GPIO.PWM(pin, 50)  # 50Hz for servo
                pwm.start(duty_cycle)
                self._pwm_instances[pin] = pwm
            else:
                self._pwm_instances[pin].ChangeDutyCycle(duty_cycle)

            return json.dumps(
                {
                    "success": True,
                    "pin": pin,
                    "angle": angle,
                    "duty_cycle": round(duty_cycle, 2),
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def gpio_blink(
        self,
        pin: int,
        times: int = 3,
        interval: float = 0.5,
    ) -> str:
        """Blink an LED."""
        if not self._ensure_gpio():
            return json.dumps(
                {
                    "success": False,
                    "error": "GPIO not available",
                }
            )

        import time

        try:
            GPIO.setup(pin, GPIO.OUT)

            for _ in range(times):
                GPIO.output(pin, GPIO.HIGH)
                time.sleep(interval)
                GPIO.output(pin, GPIO.LOW)
                time.sleep(interval)

            return json.dumps(
                {
                    "success": True,
                    "pin": pin,
                    "blinks": times,
                    "interval": interval,
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        return self.gpio_info()

    def __del__(self):
        """Cleanup on destruction."""
        if GPIO_AVAILABLE and self._initialized:
            try:
                GPIO.cleanup()
            except Exception:
                pass
