"""
iCal Skill for R CLI.

iCalendar (ICS) utilities:
- Parse ICS files
- Generate calendar events
- Export to ICS format
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class ICalSkill(Skill):
    """Skill for iCalendar operations."""

    name = "ical"
    description = "iCal: parse and generate ICS calendar files"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="ical_parse",
                description="Parse an ICS calendar file",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "ICS file content",
                        },
                    },
                    "required": ["content"],
                },
                handler=self.ical_parse,
            ),
            Tool(
                name="ical_create_event",
                description="Create a calendar event",
                parameters={
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Event title",
                        },
                        "start": {
                            "type": "string",
                            "description": "Start datetime (ISO format)",
                        },
                        "end": {
                            "type": "string",
                            "description": "End datetime (ISO format)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Event description",
                        },
                        "location": {
                            "type": "string",
                            "description": "Event location",
                        },
                    },
                    "required": ["summary", "start"],
                },
                handler=self.ical_create_event,
            ),
            Tool(
                name="ical_generate",
                description="Generate ICS file from events",
                parameters={
                    "type": "object",
                    "properties": {
                        "events": {
                            "type": "array",
                            "description": "List of events",
                        },
                        "calendar_name": {
                            "type": "string",
                            "description": "Calendar name",
                        },
                    },
                    "required": ["events"],
                },
                handler=self.ical_generate,
            ),
            Tool(
                name="ical_to_json",
                description="Convert ICS to JSON",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "ICS content",
                        },
                    },
                    "required": ["content"],
                },
                handler=self.ical_to_json,
            ),
        ]

    def _parse_datetime(self, value: str) -> Optional[datetime]:
        """Parse iCal datetime format."""
        value = value.replace("Z", "")

        formats = [
            "%Y%m%dT%H%M%S",
            "%Y%m%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    def _format_datetime(self, dt: datetime) -> str:
        """Format datetime for iCal."""
        return dt.strftime("%Y%m%dT%H%M%SZ")

    def _unfold_lines(self, content: str) -> list[str]:
        """Unfold wrapped lines in ICS."""
        lines = []
        current = ""

        for line in content.replace("\r\n", "\n").split("\n"):
            if line.startswith((" ", "\t")):
                current += line[1:]
            else:
                if current:
                    lines.append(current)
                current = line

        if current:
            lines.append(current)

        return lines

    def ical_parse(self, content: str) -> str:
        """Parse ICS content."""
        lines = self._unfold_lines(content)

        events = []
        current_event = None

        for line in lines:
            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.split(";")[0]  # Remove parameters

            if key == "BEGIN" and value == "VEVENT":
                current_event = {}
            elif key == "END" and value == "VEVENT":
                if current_event:
                    events.append(current_event)
                current_event = None
            elif current_event is not None:
                if key == "DTSTART":
                    dt = self._parse_datetime(value)
                    current_event["start"] = dt.isoformat() if dt else value
                elif key == "DTEND":
                    dt = self._parse_datetime(value)
                    current_event["end"] = dt.isoformat() if dt else value
                elif key == "SUMMARY":
                    current_event["summary"] = value
                elif key == "DESCRIPTION":
                    current_event["description"] = value.replace("\\n", "\n")
                elif key == "LOCATION":
                    current_event["location"] = value
                elif key == "UID":
                    current_event["uid"] = value
                elif key == "STATUS":
                    current_event["status"] = value
                elif key == "RRULE":
                    current_event["recurrence"] = value

        return json.dumps({
            "event_count": len(events),
            "events": events,
        }, indent=2)

    def ical_create_event(
        self,
        summary: str,
        start: str,
        end: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
    ) -> str:
        """Create single event ICS."""
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", ""))
        except ValueError:
            return f"Invalid start datetime: {start}"

        if end:
            try:
                end_dt = datetime.fromisoformat(end.replace("Z", ""))
            except ValueError:
                return f"Invalid end datetime: {end}"
        else:
            end_dt = start_dt + timedelta(hours=1)

        uid = f"{uuid.uuid4()}@r-cli"
        now = datetime.utcnow()

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//R-CLI//EN",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{self._format_datetime(now)}",
            f"DTSTART:{self._format_datetime(start_dt)}",
            f"DTEND:{self._format_datetime(end_dt)}",
            f"SUMMARY:{summary}",
        ]

        if description:
            escaped_newline = "\\n"
            lines.append(f"DESCRIPTION:{description.replace(chr(10), escaped_newline)}")
        if location:
            lines.append(f"LOCATION:{location}")

        lines.extend([
            "END:VEVENT",
            "END:VCALENDAR",
        ])

        return "\r\n".join(lines)

    def ical_generate(
        self,
        events: list,
        calendar_name: str = "R-CLI Calendar",
    ) -> str:
        """Generate ICS from events list."""
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//R-CLI//EN",
            f"X-WR-CALNAME:{calendar_name}",
        ]

        now = datetime.utcnow()

        for event in events:
            if isinstance(event, str):
                event = {"summary": event}

            uid = event.get("uid", f"{uuid.uuid4()}@r-cli")
            summary = event.get("summary", "Untitled")

            start = event.get("start")
            if start:
                try:
                    start_dt = datetime.fromisoformat(start.replace("Z", ""))
                except ValueError:
                    start_dt = now
            else:
                start_dt = now

            end = event.get("end")
            if end:
                try:
                    end_dt = datetime.fromisoformat(end.replace("Z", ""))
                except ValueError:
                    end_dt = start_dt + timedelta(hours=1)
            else:
                end_dt = start_dt + timedelta(hours=1)

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{self._format_datetime(now)}",
                f"DTSTART:{self._format_datetime(start_dt)}",
                f"DTEND:{self._format_datetime(end_dt)}",
                f"SUMMARY:{summary}",
            ])

            if "description" in event:
                desc = event["description"].replace("\n", "\\n")
                lines.append(f"DESCRIPTION:{desc}")
            if "location" in event:
                lines.append(f"LOCATION:{event['location']}")

            lines.append("END:VEVENT")

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)

    def ical_to_json(self, content: str) -> str:
        """Convert ICS to JSON."""
        return self.ical_parse(content)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        if "content" in kwargs:
            return self.ical_parse(kwargs["content"])
        return "Provide ICS content to parse"
