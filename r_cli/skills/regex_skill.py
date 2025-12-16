"""
Regex Skill for R CLI.

Regular expression utilities:
- Test and debug patterns
- Find and replace
- Extract matches
- Explain patterns
"""

import json
import re
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class RegexSkill(Skill):
    """Skill for regular expressions."""

    name = "regex"
    description = "Regex: test patterns, find/replace, extract matches"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="regex_test",
                description="Test if a pattern matches text",
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Regular expression pattern",
                        },
                        "text": {
                            "type": "string",
                            "description": "Text to test against",
                        },
                        "flags": {
                            "type": "string",
                            "description": "Flags: i (ignore case), m (multiline), s (dotall)",
                        },
                    },
                    "required": ["pattern", "text"],
                },
                handler=self.regex_test,
            ),
            Tool(
                name="regex_find_all",
                description="Find all matches in text",
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Regular expression pattern",
                        },
                        "text": {
                            "type": "string",
                            "description": "Text to search",
                        },
                        "flags": {
                            "type": "string",
                            "description": "Flags: i, m, s",
                        },
                    },
                    "required": ["pattern", "text"],
                },
                handler=self.regex_find_all,
            ),
            Tool(
                name="regex_replace",
                description="Replace matches with replacement string",
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Pattern to match",
                        },
                        "replacement": {
                            "type": "string",
                            "description": "Replacement string (use \\1, \\2 for groups)",
                        },
                        "text": {
                            "type": "string",
                            "description": "Text to modify",
                        },
                        "count": {
                            "type": "integer",
                            "description": "Max replacements (0 = all)",
                        },
                    },
                    "required": ["pattern", "replacement", "text"],
                },
                handler=self.regex_replace,
            ),
            Tool(
                name="regex_split",
                description="Split text by pattern",
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Pattern to split on",
                        },
                        "text": {
                            "type": "string",
                            "description": "Text to split",
                        },
                    },
                    "required": ["pattern", "text"],
                },
                handler=self.regex_split,
            ),
            Tool(
                name="regex_groups",
                description="Extract named/numbered groups from matches",
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Pattern with groups",
                        },
                        "text": {
                            "type": "string",
                            "description": "Text to search",
                        },
                    },
                    "required": ["pattern", "text"],
                },
                handler=self.regex_groups,
            ),
            Tool(
                name="regex_escape",
                description="Escape special regex characters in a string",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to escape",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.regex_escape,
            ),
        ]

    def _get_flags(self, flags_str: Optional[str]) -> int:
        """Convert flag string to re flags."""
        if not flags_str:
            return 0
        flags = 0
        if "i" in flags_str.lower():
            flags |= re.IGNORECASE
        if "m" in flags_str.lower():
            flags |= re.MULTILINE
        if "s" in flags_str.lower():
            flags |= re.DOTALL
        return flags

    def regex_test(
        self,
        pattern: str,
        text: str,
        flags: Optional[str] = None,
    ) -> str:
        """Test if pattern matches."""
        try:
            regex = re.compile(pattern, self._get_flags(flags))
            match = regex.search(text)

            if match:
                return json.dumps({
                    "matches": True,
                    "match": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "groups": match.groups(),
                }, indent=2)
            else:
                return json.dumps({"matches": False}, indent=2)

        except re.error as e:
            return f"Invalid regex: {e}"

    def regex_find_all(
        self,
        pattern: str,
        text: str,
        flags: Optional[str] = None,
    ) -> str:
        """Find all matches."""
        try:
            regex = re.compile(pattern, self._get_flags(flags))
            matches = []

            for match in regex.finditer(text):
                matches.append({
                    "match": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "groups": match.groups() if match.groups() else None,
                })

            return json.dumps({
                "count": len(matches),
                "matches": matches,
            }, indent=2)

        except re.error as e:
            return f"Invalid regex: {e}"

    def regex_replace(
        self,
        pattern: str,
        replacement: str,
        text: str,
        count: int = 0,
    ) -> str:
        """Replace matches."""
        try:
            result = re.sub(pattern, replacement, text, count=count)
            changes = len(re.findall(pattern, text))
            return json.dumps({
                "result": result,
                "replacements": min(changes, count) if count > 0 else changes,
            }, indent=2, ensure_ascii=False)
        except re.error as e:
            return f"Invalid regex: {e}"

    def regex_split(self, pattern: str, text: str) -> str:
        """Split by pattern."""
        try:
            parts = re.split(pattern, text)
            return json.dumps(parts, indent=2, ensure_ascii=False)
        except re.error as e:
            return f"Invalid regex: {e}"

    def regex_groups(self, pattern: str, text: str) -> str:
        """Extract groups from matches."""
        try:
            regex = re.compile(pattern)
            results = []

            for match in regex.finditer(text):
                result = {
                    "full_match": match.group(),
                    "groups": list(match.groups()),
                }
                if match.groupdict():
                    result["named_groups"] = match.groupdict()
                results.append(result)

            return json.dumps(results, indent=2, ensure_ascii=False)

        except re.error as e:
            return f"Invalid regex: {e}"

    def regex_escape(self, text: str) -> str:
        """Escape special characters."""
        return re.escape(text)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "test")
        if action == "test":
            return self.regex_test(
                kwargs.get("pattern", ""),
                kwargs.get("text", ""),
            )
        return f"Unknown action: {action}"
