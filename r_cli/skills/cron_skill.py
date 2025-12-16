"""
Cron Skill for R CLI.

Cron expression utilities:
- Parse cron expressions
- Calculate next run times
- Generate cron expressions
- Explain cron expressions
"""

import json
from datetime import datetime, timedelta
from typing import Optional, List

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class CronSkill(Skill):
    """Skill for cron operations."""

    name = "cron"
    description = "Cron: parse, explain, generate cron expressions"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="cron_explain",
                description="Explain what a cron expression means",
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Cron expression (5 or 6 fields)",
                        },
                    },
                    "required": ["expression"],
                },
                handler=self.cron_explain,
            ),
            Tool(
                name="cron_next",
                description="Calculate next run times for a cron expression",
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Cron expression",
                        },
                        "count": {
                            "type": "integer",
                            "description": "Number of next runs (default: 5)",
                        },
                    },
                    "required": ["expression"],
                },
                handler=self.cron_next,
            ),
            Tool(
                name="cron_generate",
                description="Generate cron expression from description",
                parameters={
                    "type": "object",
                    "properties": {
                        "minute": {
                            "type": "string",
                            "description": "Minute (0-59, or *)",
                        },
                        "hour": {
                            "type": "string",
                            "description": "Hour (0-23, or *)",
                        },
                        "day": {
                            "type": "string",
                            "description": "Day of month (1-31, or *)",
                        },
                        "month": {
                            "type": "string",
                            "description": "Month (1-12, or *)",
                        },
                        "weekday": {
                            "type": "string",
                            "description": "Day of week (0-6, Sun=0, or *)",
                        },
                    },
                },
                handler=self.cron_generate,
            ),
            Tool(
                name="cron_presets",
                description="Show common cron presets",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.cron_presets,
            ),
            Tool(
                name="cron_validate",
                description="Validate a cron expression",
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Cron expression to validate",
                        },
                    },
                    "required": ["expression"],
                },
                handler=self.cron_validate,
            ),
        ]

    def _parse_field(self, field: str, min_val: int, max_val: int, names: dict = None) -> List[int]:
        """Parse a single cron field into list of values."""
        values = set()

        # Handle names (e.g., MON, JAN)
        if names:
            for name, num in names.items():
                field = field.upper().replace(name, str(num))

        for part in field.split(","):
            if part == "*":
                values.update(range(min_val, max_val + 1))
            elif "/" in part:
                base, step = part.split("/")
                step = int(step)
                if base == "*":
                    start = min_val
                else:
                    start = int(base)
                values.update(range(start, max_val + 1, step))
            elif "-" in part:
                start, end = map(int, part.split("-"))
                values.update(range(start, end + 1))
            else:
                values.add(int(part))

        return sorted(v for v in values if min_val <= v <= max_val)

    def _explain_field(self, field: str, field_name: str, min_val: int, max_val: int) -> str:
        """Generate human-readable explanation for a field."""
        if field == "*":
            return f"every {field_name}"

        if "/" in field:
            base, step = field.split("/")
            if base == "*":
                return f"every {step} {field_name}s"
            else:
                return f"every {step} {field_name}s starting at {base}"

        if "-" in field:
            start, end = field.split("-")
            return f"{field_name}s {start} through {end}"

        if "," in field:
            parts = field.split(",")
            return f"{field_name}s " + ", ".join(parts)

        return f"at {field_name} {field}"

    def cron_explain(self, expression: str) -> str:
        """Explain cron expression."""
        try:
            parts = expression.strip().split()

            if len(parts) == 5:
                minute, hour, day, month, weekday = parts
            elif len(parts) == 6:
                minute, hour, day, month, weekday, _ = parts  # Ignore year
            else:
                return f"Invalid cron expression: expected 5 or 6 fields, got {len(parts)}"

            weekday_names = {
                "0": "Sunday", "1": "Monday", "2": "Tuesday", "3": "Wednesday",
                "4": "Thursday", "5": "Friday", "6": "Saturday", "7": "Sunday",
                "SUN": "0", "MON": "1", "TUE": "2", "WED": "3",
                "THU": "4", "FRI": "5", "SAT": "6",
            }

            month_names = {
                "1": "January", "2": "February", "3": "March", "4": "April",
                "5": "May", "6": "June", "7": "July", "8": "August",
                "9": "September", "10": "October", "11": "November", "12": "December",
            }

            explanation = []

            # Time
            if minute == "0" and hour != "*":
                if hour == "0":
                    explanation.append("At midnight")
                elif hour == "12":
                    explanation.append("At noon")
                else:
                    explanation.append(f"At {hour}:00")
            elif minute != "*" and hour != "*":
                explanation.append(f"At {hour}:{minute.zfill(2)}")
            else:
                if minute != "*":
                    explanation.append(self._explain_field(minute, "minute", 0, 59))
                if hour != "*":
                    explanation.append(self._explain_field(hour, "hour", 0, 23))

            # Day constraints
            if day != "*":
                explanation.append(f"on day {day} of the month")
            if month != "*":
                explanation.append(self._explain_field(month, "month", 1, 12))
            if weekday != "*":
                days = []
                for d in weekday.replace(",", " ").split():
                    if d in weekday_names:
                        days.append(weekday_names.get(d, d))
                if days:
                    explanation.append(f"on {', '.join(days)}")

            human = " ".join(explanation) if explanation else "Every minute"

            return json.dumps({
                "expression": expression,
                "fields": {
                    "minute": minute,
                    "hour": hour,
                    "day_of_month": day,
                    "month": month,
                    "day_of_week": weekday,
                },
                "description": human,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def cron_next(self, expression: str, count: int = 5) -> str:
        """Calculate next run times."""
        try:
            # Try croniter if available
            try:
                from croniter import croniter
                base = datetime.now()
                cron = croniter(expression, base)
                next_runs = [cron.get_next(datetime).isoformat() for _ in range(count)]

                return json.dumps({
                    "expression": expression,
                    "next_runs": next_runs,
                }, indent=2)

            except ImportError:
                pass

            # Fallback: simple implementation for basic expressions
            parts = expression.strip().split()
            if len(parts) < 5:
                return "Invalid cron expression"

            minute, hour, day, month, weekday = parts[:5]

            # Only handle simple cases
            if all(p in ["*", "0"] or p.isdigit() for p in [minute, hour]):
                now = datetime.now()
                runs = []

                for i in range(count * 24):  # Check next 24 iterations
                    check_time = now + timedelta(hours=i)

                    if minute != "*" and check_time.minute != int(minute):
                        continue
                    if hour != "*" and check_time.hour != int(hour):
                        continue
                    if day != "*" and check_time.day != int(day):
                        continue
                    if month != "*" and check_time.month != int(month):
                        continue
                    if weekday != "*" and check_time.weekday() != (int(weekday) - 1) % 7:
                        continue

                    runs.append(check_time.replace(minute=int(minute) if minute != "*" else 0,
                                                   second=0, microsecond=0).isoformat())
                    if len(runs) >= count:
                        break

                if runs:
                    return json.dumps({
                        "expression": expression,
                        "next_runs": runs,
                        "note": "Install croniter for accurate calculations: pip install croniter",
                    }, indent=2)

            return "Install croniter for next run calculation: pip install croniter"

        except Exception as e:
            return f"Error: {e}"

    def cron_generate(
        self,
        minute: str = "*",
        hour: str = "*",
        day: str = "*",
        month: str = "*",
        weekday: str = "*",
    ) -> str:
        """Generate cron expression."""
        expression = f"{minute} {hour} {day} {month} {weekday}"

        # Get explanation
        explain = self.cron_explain(expression)

        return explain

    def cron_presets(self) -> str:
        """Show common cron presets."""
        presets = {
            "Every minute": "* * * * *",
            "Every 5 minutes": "*/5 * * * *",
            "Every 15 minutes": "*/15 * * * *",
            "Every 30 minutes": "*/30 * * * *",
            "Every hour": "0 * * * *",
            "Every 2 hours": "0 */2 * * *",
            "Every day at midnight": "0 0 * * *",
            "Every day at noon": "0 12 * * *",
            "Every day at 6am": "0 6 * * *",
            "Every Monday": "0 0 * * 1",
            "Every weekday": "0 0 * * 1-5",
            "Every weekend": "0 0 * * 0,6",
            "First day of month": "0 0 1 * *",
            "Every Sunday at 1am": "0 1 * * 0",
            "Every 6 hours": "0 */6 * * *",
            "Every quarter (1st of Jan, Apr, Jul, Oct)": "0 0 1 1,4,7,10 *",
        }

        return json.dumps(presets, indent=2)

    def cron_validate(self, expression: str) -> str:
        """Validate cron expression."""
        try:
            parts = expression.strip().split()

            if len(parts) < 5 or len(parts) > 6:
                return json.dumps({
                    "valid": False,
                    "error": f"Expected 5 or 6 fields, got {len(parts)}",
                }, indent=2)

            ranges = [
                (0, 59, "minute"),
                (0, 23, "hour"),
                (1, 31, "day of month"),
                (1, 12, "month"),
                (0, 6, "day of week"),
            ]

            for i, (min_v, max_v, name) in enumerate(ranges):
                field = parts[i]
                try:
                    values = self._parse_field(field, min_v, max_v)
                    if not values:
                        return json.dumps({
                            "valid": False,
                            "error": f"Invalid {name}: {field}",
                        }, indent=2)
                except Exception:
                    return json.dumps({
                        "valid": False,
                        "error": f"Cannot parse {name}: {field}",
                    }, indent=2)

            return json.dumps({
                "valid": True,
                "expression": expression,
                "fields": {
                    "minute": parts[0],
                    "hour": parts[1],
                    "day_of_month": parts[2],
                    "month": parts[3],
                    "day_of_week": parts[4],
                },
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "valid": False,
                "error": str(e),
            }, indent=2)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "presets")
        if action == "presets":
            return self.cron_presets()
        elif action == "explain":
            return self.cron_explain(kwargs.get("expression", "* * * * *"))
        return f"Unknown action: {action}"
