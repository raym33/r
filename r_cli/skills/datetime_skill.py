"""
DateTime Skill for R CLI.

Date and time utilities:
- Parse and format dates
- Timezone conversion
- Date arithmetic
- Countdown/age calculation
"""

import json
from datetime import datetime, timedelta
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class DateTimeSkill(Skill):
    """Skill for date/time operations."""

    name = "datetime"
    description = "DateTime: parse, format, timezone, arithmetic, countdown"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="datetime_now",
                description="Get current date/time",
                parameters={
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "description": "Timezone (e.g., 'UTC', 'US/Eastern', 'Europe/London')",
                        },
                        "format": {
                            "type": "string",
                            "description": "Output format (strftime)",
                        },
                    },
                },
                handler=self.datetime_now,
            ),
            Tool(
                name="datetime_parse",
                description="Parse a date string",
                parameters={
                    "type": "object",
                    "properties": {
                        "date_string": {
                            "type": "string",
                            "description": "Date string to parse",
                        },
                        "format": {
                            "type": "string",
                            "description": "Input format (strftime), auto-detect if not specified",
                        },
                    },
                    "required": ["date_string"],
                },
                handler=self.datetime_parse,
            ),
            Tool(
                name="datetime_format",
                description="Format a date to string",
                parameters={
                    "type": "object",
                    "properties": {
                        "date_string": {
                            "type": "string",
                            "description": "Date to format (ISO format or timestamp)",
                        },
                        "format": {
                            "type": "string",
                            "description": "Output format (strftime)",
                        },
                    },
                    "required": ["date_string", "format"],
                },
                handler=self.datetime_format,
            ),
            Tool(
                name="datetime_add",
                description="Add time to a date",
                parameters={
                    "type": "object",
                    "properties": {
                        "date_string": {
                            "type": "string",
                            "description": "Starting date (ISO format or 'now')",
                        },
                        "days": {"type": "integer", "description": "Days to add"},
                        "hours": {"type": "integer", "description": "Hours to add"},
                        "minutes": {"type": "integer", "description": "Minutes to add"},
                        "weeks": {"type": "integer", "description": "Weeks to add"},
                    },
                    "required": ["date_string"],
                },
                handler=self.datetime_add,
            ),
            Tool(
                name="datetime_diff",
                description="Calculate difference between two dates",
                parameters={
                    "type": "object",
                    "properties": {
                        "date1": {
                            "type": "string",
                            "description": "First date",
                        },
                        "date2": {
                            "type": "string",
                            "description": "Second date",
                        },
                    },
                    "required": ["date1", "date2"],
                },
                handler=self.datetime_diff,
            ),
            Tool(
                name="datetime_timezone",
                description="Convert between timezones",
                parameters={
                    "type": "object",
                    "properties": {
                        "date_string": {
                            "type": "string",
                            "description": "Date to convert",
                        },
                        "from_tz": {
                            "type": "string",
                            "description": "Source timezone",
                        },
                        "to_tz": {
                            "type": "string",
                            "description": "Target timezone",
                        },
                    },
                    "required": ["date_string", "from_tz", "to_tz"],
                },
                handler=self.datetime_timezone,
            ),
            Tool(
                name="datetime_countdown",
                description="Countdown to a date",
                parameters={
                    "type": "object",
                    "properties": {
                        "target_date": {
                            "type": "string",
                            "description": "Target date",
                        },
                    },
                    "required": ["target_date"],
                },
                handler=self.datetime_countdown,
            ),
            Tool(
                name="datetime_age",
                description="Calculate age from birthdate",
                parameters={
                    "type": "object",
                    "properties": {
                        "birthdate": {
                            "type": "string",
                            "description": "Birth date",
                        },
                    },
                    "required": ["birthdate"],
                },
                handler=self.datetime_age,
            ),
            Tool(
                name="datetime_weekday",
                description="Get day of week for a date",
                parameters={
                    "type": "object",
                    "properties": {
                        "date_string": {
                            "type": "string",
                            "description": "Date to check",
                        },
                    },
                    "required": ["date_string"],
                },
                handler=self.datetime_weekday,
            ),
            Tool(
                name="timestamp_convert",
                description="Convert between timestamp and datetime",
                parameters={
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "string",
                            "description": "Timestamp (seconds/ms) or datetime string",
                        },
                    },
                    "required": ["value"],
                },
                handler=self.timestamp_convert,
            ),
        ]

    def _parse_date(self, date_string: str) -> datetime:
        """Parse date string with multiple formats."""
        if date_string.lower() == "now":
            return datetime.now()

        # Try common formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%B %d, %Y",
            "%d %B %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue

        # Try ISO format
        try:
            return datetime.fromisoformat(date_string.replace("Z", "+00:00"))
        except ValueError:
            pass

        raise ValueError(f"Could not parse date: {date_string}")

    def datetime_now(
        self,
        timezone: Optional[str] = None,
        format: Optional[str] = None,
    ) -> str:
        """Get current datetime."""
        try:
            now = datetime.now()

            if timezone:
                try:
                    from zoneinfo import ZoneInfo
                    now = datetime.now(ZoneInfo(timezone))
                except ImportError:
                    return "zoneinfo not available (Python 3.9+ required)"
                except Exception as e:
                    return f"Invalid timezone: {timezone}"

            if format:
                return now.strftime(format)

            return json.dumps({
                "iso": now.isoformat(),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "timestamp": int(now.timestamp()),
                "weekday": now.strftime("%A"),
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def datetime_parse(
        self,
        date_string: str,
        format: Optional[str] = None,
    ) -> str:
        """Parse date string."""
        try:
            if format:
                dt = datetime.strptime(date_string, format)
            else:
                dt = self._parse_date(date_string)

            return json.dumps({
                "iso": dt.isoformat(),
                "year": dt.year,
                "month": dt.month,
                "day": dt.day,
                "hour": dt.hour,
                "minute": dt.minute,
                "second": dt.second,
                "weekday": dt.strftime("%A"),
                "timestamp": int(dt.timestamp()),
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def datetime_format(self, date_string: str, format: str) -> str:
        """Format date."""
        try:
            dt = self._parse_date(date_string)
            return dt.strftime(format)
        except Exception as e:
            return f"Error: {e}"

    def datetime_add(
        self,
        date_string: str,
        days: int = 0,
        hours: int = 0,
        minutes: int = 0,
        weeks: int = 0,
    ) -> str:
        """Add time to date."""
        try:
            dt = self._parse_date(date_string)
            delta = timedelta(days=days, hours=hours, minutes=minutes, weeks=weeks)
            result = dt + delta

            return json.dumps({
                "original": dt.isoformat(),
                "result": result.isoformat(),
                "added": {
                    "days": days,
                    "hours": hours,
                    "minutes": minutes,
                    "weeks": weeks,
                },
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def datetime_diff(self, date1: str, date2: str) -> str:
        """Calculate date difference."""
        try:
            dt1 = self._parse_date(date1)
            dt2 = self._parse_date(date2)
            diff = dt2 - dt1

            total_seconds = abs(diff.total_seconds())
            days = abs(diff.days)
            hours = int((total_seconds % 86400) / 3600)
            minutes = int((total_seconds % 3600) / 60)

            return json.dumps({
                "date1": dt1.isoformat(),
                "date2": dt2.isoformat(),
                "difference": {
                    "total_days": days,
                    "total_hours": int(total_seconds / 3600),
                    "total_minutes": int(total_seconds / 60),
                    "total_seconds": int(total_seconds),
                    "breakdown": f"{days}d {hours}h {minutes}m",
                },
                "date2_is_after": dt2 > dt1,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def datetime_timezone(
        self,
        date_string: str,
        from_tz: str,
        to_tz: str,
    ) -> str:
        """Convert timezone."""
        try:
            from zoneinfo import ZoneInfo

            dt = self._parse_date(date_string)
            dt_from = dt.replace(tzinfo=ZoneInfo(from_tz))
            dt_to = dt_from.astimezone(ZoneInfo(to_tz))

            return json.dumps({
                "original": f"{dt_from.strftime('%Y-%m-%d %H:%M:%S')} {from_tz}",
                "converted": f"{dt_to.strftime('%Y-%m-%d %H:%M:%S')} {to_tz}",
            }, indent=2)

        except ImportError:
            return "zoneinfo not available"
        except Exception as e:
            return f"Error: {e}"

    def datetime_countdown(self, target_date: str) -> str:
        """Countdown to date."""
        try:
            target = self._parse_date(target_date)
            now = datetime.now()
            diff = target - now

            if diff.total_seconds() < 0:
                return json.dumps({
                    "target": target.isoformat(),
                    "status": "past",
                    "elapsed": str(abs(diff)),
                }, indent=2)

            days = diff.days
            hours = diff.seconds // 3600
            minutes = (diff.seconds % 3600) // 60
            seconds = diff.seconds % 60

            return json.dumps({
                "target": target.isoformat(),
                "countdown": f"{days}d {hours}h {minutes}m {seconds}s",
                "total_days": days,
                "total_hours": int(diff.total_seconds() / 3600),
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def datetime_age(self, birthdate: str) -> str:
        """Calculate age."""
        try:
            birth = self._parse_date(birthdate)
            today = datetime.now()

            age_years = today.year - birth.year
            if (today.month, today.day) < (birth.month, birth.day):
                age_years -= 1

            # Days until next birthday
            next_birthday = birth.replace(year=today.year)
            if next_birthday < today:
                next_birthday = next_birthday.replace(year=today.year + 1)
            days_to_birthday = (next_birthday - today).days

            return json.dumps({
                "birthdate": birth.strftime("%Y-%m-%d"),
                "age_years": age_years,
                "days_to_birthday": days_to_birthday,
                "total_days": (today - birth).days,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def datetime_weekday(self, date_string: str) -> str:
        """Get weekday."""
        try:
            dt = self._parse_date(date_string)
            return json.dumps({
                "date": dt.strftime("%Y-%m-%d"),
                "weekday": dt.strftime("%A"),
                "weekday_number": dt.weekday(),  # Monday = 0
                "iso_weekday": dt.isoweekday(),  # Monday = 1
                "week_of_year": dt.isocalendar()[1],
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def timestamp_convert(self, value: str) -> str:
        """Convert timestamp/datetime."""
        try:
            # Try as timestamp
            try:
                ts = float(value)
                # Detect milliseconds
                if ts > 1e12:
                    ts = ts / 1000
                dt = datetime.fromtimestamp(ts)
                return json.dumps({
                    "timestamp": int(ts),
                    "datetime": dt.isoformat(),
                    "formatted": dt.strftime("%Y-%m-%d %H:%M:%S"),
                }, indent=2)
            except ValueError:
                pass

            # Try as datetime string
            dt = self._parse_date(value)
            return json.dumps({
                "datetime": dt.isoformat(),
                "timestamp": int(dt.timestamp()),
                "timestamp_ms": int(dt.timestamp() * 1000),
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        return self.datetime_now()
