#!/usr/bin/env python3
"""
R CLI - Custom Skill Example

This demonstrates how to create your own skill for R CLI.
Save this file to ~/.r-cli/skills/ to use it.
"""

from typing import Optional
from r_cli.core.agent import Skill
from r_cli.core.llm import Tool
from r_cli.core.config import Config


class WeatherSkill(Skill):
    """
    Example custom skill for weather information.

    This is a mock implementation - replace with real API calls.
    """

    name = "weather"
    description = "Get weather information (demo skill)"

    def __init__(self, config: Optional[Config] = None):
        super().__init__(config)
        # Add any skill-specific initialization here
        self.cache: dict[str, str] = {}

    def get_tools(self) -> list[Tool]:
        """Define the tools this skill provides to the LLM."""
        return [
            Tool(
                name="get_weather",
                description="Get current weather for a city",
                parameters={
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The city name",
                        },
                        "units": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "Temperature units",
                            "default": "celsius",
                        },
                    },
                    "required": ["city"],
                },
                handler=self.get_weather,
            ),
            Tool(
                name="get_forecast",
                description="Get 5-day weather forecast for a city",
                parameters={
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The city name",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days (1-5)",
                            "default": 5,
                        },
                    },
                    "required": ["city"],
                },
                handler=self.get_forecast,
            ),
        ]

    def get_weather(self, city: str, units: str = "celsius") -> str:
        """
        Get current weather for a city.

        In a real implementation, this would call a weather API.
        """
        # Mock data - replace with real API call
        mock_data = {
            "Madrid": {"temp": 22, "condition": "Sunny", "humidity": 45},
            "London": {"temp": 15, "condition": "Cloudy", "humidity": 70},
            "New York": {"temp": 18, "condition": "Partly cloudy", "humidity": 55},
            "Tokyo": {"temp": 20, "condition": "Clear", "humidity": 60},
        }

        if city not in mock_data:
            return f"Weather data not available for {city}"

        data = mock_data[city]
        temp = data["temp"]

        if units == "fahrenheit":
            temp = (temp * 9 / 5) + 32
            unit_symbol = "F"
        else:
            unit_symbol = "C"

        return f"""
Weather in {city}
Temperature: {temp}° {unit_symbol}
Condition: {data['condition']}
Humidity: {data['humidity']}%
        """.strip()

    def get_forecast(self, city: str, days: int = 5) -> str:
        """Get weather forecast."""
        days = min(max(days, 1), 5)

        # Mock forecast
        forecast = f"5-Day Forecast for {city}\n" + "=" * 30 + "\n"
        conditions = ["Sunny", "Cloudy", "Partly cloudy", "Rainy", "Clear"]

        for i in range(days):
            temp = 15 + (i * 2)
            condition = conditions[i % len(conditions)]
            forecast += f"Day {i + 1}: {temp}°C - {condition}\n"

        return forecast

    def execute(self, **kwargs) -> str:
        """Direct execution from CLI."""
        city = kwargs.get("city", "Madrid")
        units = kwargs.get("units", "celsius")
        return self.get_weather(city, units)


# Register the skill when imported
def register(agent):
    """Called by R CLI to register this skill."""
    agent.register_skill(WeatherSkill(agent.config))
