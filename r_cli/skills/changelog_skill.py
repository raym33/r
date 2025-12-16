"""
Changelog Skill for R CLI.

Changelog utilities:
- Parse CHANGELOG.md
- Generate changelog entries
- Keep a Changelog format
"""

import json
import re
from datetime import datetime
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class ChangelogSkill(Skill):
    """Skill for Changelog operations."""

    name = "changelog"
    description = "Changelog: parse and generate changelogs"

    CHANGE_TYPES = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="changelog_parse",
                description="Parse a CHANGELOG.md file",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Changelog content",
                        },
                    },
                    "required": ["content"],
                },
                handler=self.changelog_parse,
            ),
            Tool(
                name="changelog_generate",
                description="Generate changelog entry",
                parameters={
                    "type": "object",
                    "properties": {
                        "version": {
                            "type": "string",
                            "description": "Version number",
                        },
                        "changes": {
                            "type": "object",
                            "description": "Changes by type (Added, Changed, Fixed, etc.)",
                        },
                        "date": {
                            "type": "string",
                            "description": "Release date (default: today)",
                        },
                    },
                    "required": ["version", "changes"],
                },
                handler=self.changelog_generate,
            ),
            Tool(
                name="changelog_init",
                description="Initialize a new CHANGELOG.md",
                parameters={
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "Project name",
                        },
                        "repo_url": {
                            "type": "string",
                            "description": "Repository URL for compare links",
                        },
                    },
                    "required": ["project_name"],
                },
                handler=self.changelog_init,
            ),
            Tool(
                name="changelog_latest",
                description="Get latest version from changelog",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Changelog content",
                        },
                    },
                    "required": ["content"],
                },
                handler=self.changelog_latest,
            ),
            Tool(
                name="changelog_unreleased",
                description="Get unreleased changes",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Changelog content",
                        },
                    },
                    "required": ["content"],
                },
                handler=self.changelog_unreleased,
            ),
            Tool(
                name="changelog_add_entry",
                description="Add entry to changelog",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Existing changelog content",
                        },
                        "type": {
                            "type": "string",
                            "description": "Change type: Added, Changed, Fixed, etc.",
                        },
                        "entry": {
                            "type": "string",
                            "description": "Change description",
                        },
                    },
                    "required": ["content", "type", "entry"],
                },
                handler=self.changelog_add_entry,
            ),
        ]

    def _parse_version_section(self, content: str) -> list[dict]:
        """Parse changelog into version sections."""
        versions = []

        # Match version headers: ## [1.0.0] - 2024-01-01 or ## [Unreleased]
        version_pattern = r"##\s*\[([^\]]+)\](?:\s*-\s*(\d{4}-\d{2}-\d{2}))?"

        sections = re.split(version_pattern, content)

        # sections[0] is header before first version
        i = 1
        while i < len(sections):
            version = sections[i]
            date = sections[i + 1] if i + 1 < len(sections) else None
            body = sections[i + 2] if i + 2 < len(sections) else ""

            # Parse change types
            changes = {}
            current_type = None

            for line in body.split("\n"):
                line = line.strip()

                # Check for change type header
                type_match = re.match(r"###\s*(\w+)", line)
                if type_match:
                    current_type = type_match.group(1)
                    changes[current_type] = []
                elif line.startswith("- ") and current_type:
                    changes[current_type].append(line[2:])

            versions.append({
                "version": version,
                "date": date,
                "changes": changes,
            })

            i += 3

        return versions

    def changelog_parse(self, content: str) -> str:
        """Parse changelog content."""
        versions = self._parse_version_section(content)

        # Count changes
        total_changes = 0
        change_counts = dict.fromkeys(self.CHANGE_TYPES, 0)

        for v in versions:
            for change_type, entries in v.get("changes", {}).items():
                count = len(entries)
                total_changes += count
                if change_type in change_counts:
                    change_counts[change_type] += count

        return json.dumps({
            "version_count": len(versions),
            "total_changes": total_changes,
            "change_counts": change_counts,
            "versions": versions,
        }, indent=2)

    def changelog_generate(
        self,
        version: str,
        changes: dict,
        date: Optional[str] = None,
    ) -> str:
        """Generate changelog entry."""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        lines = [f"## [{version}] - {date}", ""]

        for change_type in self.CHANGE_TYPES:
            if changes.get(change_type):
                lines.append(f"### {change_type}")
                for entry in changes[change_type]:
                    lines.append(f"- {entry}")
                lines.append("")

        return "\n".join(lines)

    def changelog_init(
        self,
        project_name: str,
        repo_url: Optional[str] = None,
    ) -> str:
        """Initialize new changelog."""
        lines = [
            "# Changelog",
            "",
            f"All notable changes to {project_name} will be documented in this file.",
            "",
            "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),",
            "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).",
            "",
            "## [Unreleased]",
            "",
            "### Added",
            "",
            "### Changed",
            "",
            "### Fixed",
            "",
        ]

        if repo_url:
            lines.extend([
                "",
                f"[Unreleased]: {repo_url}/compare/v0.0.0...HEAD",
            ])

        return "\n".join(lines)

    def changelog_latest(self, content: str) -> str:
        """Get latest version."""
        versions = self._parse_version_section(content)

        # Skip unreleased
        for v in versions:
            if v["version"].lower() != "unreleased":
                return json.dumps({
                    "version": v["version"],
                    "date": v["date"],
                    "changes": v["changes"],
                }, indent=2)

        return json.dumps({"version": None, "message": "No released versions found"}, indent=2)

    def changelog_unreleased(self, content: str) -> str:
        """Get unreleased changes."""
        versions = self._parse_version_section(content)

        for v in versions:
            if v["version"].lower() == "unreleased":
                return json.dumps({
                    "has_unreleased": True,
                    "changes": v["changes"],
                }, indent=2)

        return json.dumps({
            "has_unreleased": False,
            "changes": {},
        }, indent=2)

    def changelog_add_entry(
        self,
        content: str,
        type: str,
        entry: str,
    ) -> str:
        """Add entry to unreleased section."""
        if type not in self.CHANGE_TYPES:
            return f"Invalid change type: {type}. Use: {', '.join(self.CHANGE_TYPES)}"

        # Find unreleased section
        unreleased_match = re.search(r"(## \[Unreleased\].*?)(## \[|$)", content, re.DOTALL)

        if not unreleased_match:
            return "No [Unreleased] section found"

        unreleased_section = unreleased_match.group(1)

        # Find or create the type section
        type_pattern = rf"(### {type}\n)"
        type_match = re.search(type_pattern, unreleased_section)

        if type_match:
            # Add after the type header
            insert_pos = unreleased_match.start() + type_match.end()
            new_content = content[:insert_pos] + f"- {entry}\n" + content[insert_pos:]
        else:
            # Create new type section
            section_end = unreleased_match.end(1)
            new_section = f"\n### {type}\n- {entry}\n"
            new_content = content[:section_end] + new_section + content[section_end:]

        return new_content

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        if "content" in kwargs:
            return self.changelog_parse(kwargs["content"])
        return "Provide changelog content to parse"
