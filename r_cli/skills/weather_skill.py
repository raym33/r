"""
Weather Skill for R CLI.

Weather information:
- Current weather
- Forecast
- Uses wttr.in API (free, no key required)
"""

import json
import urllib.error
import urllib.request
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class WeatherSkill(Skill):
    """Skill for weather information."""

    name = "weather"
    description = "Weather: current conditions and forecast"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="weather_current",
                description="Get current weather for a location",
                parameters={
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name, coordinates, or airport code",
                        },
                        "units": {
                            "type": "string",
                            "description": "Units: metric (default), imperial",
                        },
                    },
                    "required": ["location"],
                },
                handler=self.weather_current,
            ),
            Tool(
                name="weather_forecast",
                description="Get weather forecast for a location",
                parameters={
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name, coordinates, or airport code",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days (1-3, default: 3)",
                        },
                        "units": {
                            "type": "string",
                            "description": "Units: metric (default), imperial",
                        },
                    },
                    "required": ["location"],
                },
                handler=self.weather_forecast,
            ),
            Tool(
                name="weather_simple",
                description="Get simple one-line weather",
                parameters={
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name",
                        },
                    },
                    "required": ["location"],
                },
                handler=self.weather_simple,
            ),
            Tool(
                name="weather_moon",
                description="Get moon phase information",
                parameters={
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "Date (YYYY-MM-DD, default: today)",
                        },
                    },
                },
                handler=self.weather_moon,
            ),
        ]

    def _fetch_weather(self, url: str) -> tuple[bool, str]:
        """Fetch weather data from wttr.in."""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "R-CLI/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return True, response.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return False, f"HTTP error: {e.code}"
        except urllib.error.URLError as e:
            return False, f"URL error: {e.reason}"
        except Exception as e:
            return False, str(e)

    def weather_current(
        self,
        location: str,
        units: str = "metric",
    ) -> str:
        """Get current weather."""
        try:
            # Clean location for URL
            location_encoded = urllib.parse.quote(location)
            unit_param = "m" if units == "metric" else "u"

            # Get JSON format
            url = f"https://wttr.in/{location_encoded}?format=j1&{unit_param}"
            success, data = self._fetch_weather(url)

            if not success:
                return f"Error: {data}"

            weather = json.loads(data)

            current = weather.get("current_condition", [{}])[0]
            area = weather.get("nearest_area", [{}])[0]

            temp_key = "temp_C" if units == "metric" else "temp_F"
            feels_key = "FeelsLikeC" if units == "metric" else "FeelsLikeF"
            wind_key = "windspeedKmph" if units == "metric" else "windspeedMiles"
            wind_unit = "km/h" if units == "metric" else "mph"
            temp_unit = "°C" if units == "metric" else "°F"

            result = {
                "location": {
                    "city": area.get("areaName", [{}])[0].get("value", "Unknown"),
                    "region": area.get("region", [{}])[0].get("value", ""),
                    "country": area.get("country", [{}])[0].get("value", ""),
                },
                "current": {
                    "condition": current.get("weatherDesc", [{}])[0].get("value", ""),
                    "temperature": f"{current.get(temp_key, 'N/A')}{temp_unit}",
                    "feels_like": f"{current.get(feels_key, 'N/A')}{temp_unit}",
                    "humidity": f"{current.get('humidity', 'N/A')}%",
                    "wind": f"{current.get(wind_key, 'N/A')} {wind_unit} {current.get('winddir16Point', '')}",
                    "visibility": f"{current.get('visibility', 'N/A')} km",
                    "uv_index": current.get("uvIndex", "N/A"),
                },
                "observation_time": current.get("observation_time", ""),
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def weather_forecast(
        self,
        location: str,
        days: int = 3,
        units: str = "metric",
    ) -> str:
        """Get weather forecast."""
        try:
            import urllib.parse
            location_encoded = urllib.parse.quote(location)
            unit_param = "m" if units == "metric" else "u"

            url = f"https://wttr.in/{location_encoded}?format=j1&{unit_param}"
            success, data = self._fetch_weather(url)

            if not success:
                return f"Error: {data}"

            weather = json.loads(data)

            temp_max_key = "maxtempC" if units == "metric" else "maxtempF"
            temp_min_key = "mintempC" if units == "metric" else "mintempF"
            temp_unit = "°C" if units == "metric" else "°F"

            forecasts = []
            for day in weather.get("weather", [])[:days]:
                forecast = {
                    "date": day.get("date"),
                    "high": f"{day.get(temp_max_key)}{temp_unit}",
                    "low": f"{day.get(temp_min_key)}{temp_unit}",
                    "condition": day.get("hourly", [{}])[4].get("weatherDesc", [{}])[0].get("value", ""),
                    "sunrise": day.get("astronomy", [{}])[0].get("sunrise", ""),
                    "sunset": day.get("astronomy", [{}])[0].get("sunset", ""),
                    "chance_of_rain": f"{day.get('hourly', [{}])[4].get('chanceofrain', '0')}%",
                }
                forecasts.append(forecast)

            return json.dumps({
                "location": location,
                "forecast": forecasts,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def weather_simple(self, location: str) -> str:
        """Get simple one-line weather."""
        try:
            import urllib.parse
            location_encoded = urllib.parse.quote(location)

            # Custom format for one-line output
            url = f"https://wttr.in/{location_encoded}?format=%l:+%c+%t+%w"
            success, data = self._fetch_weather(url)

            if not success:
                return f"Error: {data}"

            return data.strip()

        except Exception as e:
            return f"Error: {e}"

    def weather_moon(self, date: Optional[str] = None) -> str:
        """Get moon phase."""
        try:
            if date:
                url = f"https://wttr.in/Moon@{date}?format=j1"
            else:
                url = "https://wttr.in/Moon?format=j1"

            success, data = self._fetch_weather(url)

            if not success:
                return f"Error: {data}"

            weather = json.loads(data)

            # Get moon data from astronomy
            if weather.get("weather"):
                astro = weather["weather"][0].get("astronomy", [{}])[0]
                return json.dumps({
                    "date": date or "today",
                    "moon_phase": astro.get("moon_phase", "Unknown"),
                    "moon_illumination": f"{astro.get('moon_illumination', 'N/A')}%",
                    "moonrise": astro.get("moonrise", "N/A"),
                    "moonset": astro.get("moonset", "N/A"),
                }, indent=2)

            return "Could not get moon data"

        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        location = kwargs.get("location", "")
        if location:
            return self.weather_current(location)
        return "Specify a location"
