"""
SemVer Skill for R CLI.

Semantic Versioning utilities:
- Parse versions
- Compare versions
- Bump versions
- Version ranges
"""

import json
import re
from typing import Optional, Tuple

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class SemVerSkill(Skill):
    """Skill for Semantic Versioning operations."""

    name = "semver"
    description = "SemVer: parse, compare, bump semantic versions"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="semver_parse",
                description="Parse a semantic version string",
                parameters={
                    "type": "object",
                    "properties": {
                        "version": {
                            "type": "string",
                            "description": "Version string (e.g., 1.2.3-beta.1+build)",
                        },
                    },
                    "required": ["version"],
                },
                handler=self.semver_parse,
            ),
            Tool(
                name="semver_compare",
                description="Compare two versions",
                parameters={
                    "type": "object",
                    "properties": {
                        "v1": {
                            "type": "string",
                            "description": "First version",
                        },
                        "v2": {
                            "type": "string",
                            "description": "Second version",
                        },
                    },
                    "required": ["v1", "v2"],
                },
                handler=self.semver_compare,
            ),
            Tool(
                name="semver_bump",
                description="Bump version number",
                parameters={
                    "type": "object",
                    "properties": {
                        "version": {
                            "type": "string",
                            "description": "Current version",
                        },
                        "type": {
                            "type": "string",
                            "description": "Bump type: major, minor, patch, prerelease",
                        },
                        "prerelease": {
                            "type": "string",
                            "description": "Prerelease identifier (e.g., beta, alpha)",
                        },
                    },
                    "required": ["version", "type"],
                },
                handler=self.semver_bump,
            ),
            Tool(
                name="semver_satisfies",
                description="Check if version satisfies a range",
                parameters={
                    "type": "object",
                    "properties": {
                        "version": {
                            "type": "string",
                            "description": "Version to check",
                        },
                        "range": {
                            "type": "string",
                            "description": "Version range (e.g., ^1.2.0, >=1.0.0 <2.0.0)",
                        },
                    },
                    "required": ["version", "range"],
                },
                handler=self.semver_satisfies,
            ),
            Tool(
                name="semver_sort",
                description="Sort versions",
                parameters={
                    "type": "object",
                    "properties": {
                        "versions": {
                            "type": "array",
                            "description": "List of versions to sort",
                        },
                        "descending": {
                            "type": "boolean",
                            "description": "Sort descending (default: false)",
                        },
                    },
                    "required": ["versions"],
                },
                handler=self.semver_sort,
            ),
            Tool(
                name="semver_valid",
                description="Check if version is valid semver",
                parameters={
                    "type": "object",
                    "properties": {
                        "version": {
                            "type": "string",
                            "description": "Version to validate",
                        },
                    },
                    "required": ["version"],
                },
                handler=self.semver_valid,
            ),
        ]

    def _parse_version(self, version: str) -> Optional[tuple]:
        """Parse version into components."""
        # Remove leading 'v' if present
        version = version.lstrip("v")

        # SemVer regex
        pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.-]+))?(?:\+([a-zA-Z0-9.-]+))?$"
        match = re.match(pattern, version)

        if not match:
            return None

        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3))
        prerelease = match.group(4)
        build = match.group(5)

        return (major, minor, patch, prerelease, build)

    def _compare_prerelease(self, pre1: Optional[str], pre2: Optional[str]) -> int:
        """Compare prerelease versions."""
        # No prerelease > prerelease
        if pre1 is None and pre2 is None:
            return 0
        if pre1 is None:
            return 1
        if pre2 is None:
            return -1

        parts1 = pre1.split(".")
        parts2 = pre2.split(".")

        for p1, p2 in zip(parts1, parts2):
            # Numeric comparison if both are numbers
            if p1.isdigit() and p2.isdigit():
                if int(p1) < int(p2):
                    return -1
                if int(p1) > int(p2):
                    return 1
            else:
                # String comparison
                if p1 < p2:
                    return -1
                if p1 > p2:
                    return 1

        # Longer prerelease has higher precedence
        return len(parts1) - len(parts2)

    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two versions. Returns -1, 0, or 1."""
        parsed1 = self._parse_version(v1)
        parsed2 = self._parse_version(v2)

        if not parsed1 or not parsed2:
            return 0

        # Compare major.minor.patch
        for i in range(3):
            if parsed1[i] < parsed2[i]:
                return -1
            if parsed1[i] > parsed2[i]:
                return 1

        # Compare prerelease
        return self._compare_prerelease(parsed1[3], parsed2[3])

    def semver_parse(self, version: str) -> str:
        """Parse semantic version."""
        parsed = self._parse_version(version)

        if not parsed:
            return json.dumps({
                "valid": False,
                "error": "Invalid semver format",
            }, indent=2)

        major, minor, patch, prerelease, build = parsed

        return json.dumps({
            "valid": True,
            "version": version.lstrip("v"),
            "major": major,
            "minor": minor,
            "patch": patch,
            "prerelease": prerelease,
            "build": build,
        }, indent=2)

    def semver_compare(self, v1: str, v2: str) -> str:
        """Compare two versions."""
        result = self._compare_versions(v1, v2)

        comparison = "equal"
        if result < 0:
            comparison = "less"
        elif result > 0:
            comparison = "greater"

        return json.dumps({
            "v1": v1,
            "v2": v2,
            "comparison": comparison,
            "v1_is_newer": result > 0,
            "v2_is_newer": result < 0,
            "equal": result == 0,
        }, indent=2)

    def semver_bump(
        self,
        version: str,
        type: str,
        prerelease: Optional[str] = None,
    ) -> str:
        """Bump version."""
        parsed = self._parse_version(version)

        if not parsed:
            return f"Invalid version: {version}"

        major, minor, patch, pre, build = parsed

        if type == "major":
            major += 1
            minor = 0
            patch = 0
            pre = None
        elif type == "minor":
            minor += 1
            patch = 0
            pre = None
        elif type == "patch":
            patch += 1
            pre = None
        elif type == "prerelease":
            if pre:
                # Increment prerelease number
                parts = pre.split(".")
                if parts[-1].isdigit():
                    parts[-1] = str(int(parts[-1]) + 1)
                else:
                    parts.append("1")
                pre = ".".join(parts)
            else:
                pre = prerelease or "alpha.1"
        else:
            return f"Invalid bump type: {type}. Use: major, minor, patch, prerelease"

        new_version = f"{major}.{minor}.{patch}"
        if pre:
            new_version += f"-{pre}"

        return json.dumps({
            "previous": version,
            "new": new_version,
            "bump_type": type,
        }, indent=2)

    def semver_satisfies(self, version: str, range: str) -> str:
        """Check if version satisfies range."""
        parsed = self._parse_version(version)
        if not parsed:
            return json.dumps({"satisfies": False, "error": "Invalid version"}, indent=2)

        major, minor, patch, pre, _ = parsed

        # Handle common range patterns
        range = range.strip()

        # Exact match
        if not any(c in range for c in "^~><= |"):
            return json.dumps({
                "satisfies": self._compare_versions(version, range) == 0,
                "version": version,
                "range": range,
            }, indent=2)

        # Caret range (^): allows minor and patch updates
        if range.startswith("^"):
            base = range[1:]
            base_parsed = self._parse_version(base)
            if base_parsed:
                bm, bn, bp, _, _ = base_parsed
                satisfies = (
                    major == bm and
                    (minor > bn or (minor == bn and patch >= bp))
                )
                return json.dumps({
                    "satisfies": satisfies,
                    "version": version,
                    "range": range,
                    "type": "caret",
                }, indent=2)

        # Tilde range (~): allows patch updates
        if range.startswith("~"):
            base = range[1:]
            base_parsed = self._parse_version(base)
            if base_parsed:
                bm, bn, bp, _, _ = base_parsed
                satisfies = major == bm and minor == bn and patch >= bp
                return json.dumps({
                    "satisfies": satisfies,
                    "version": version,
                    "range": range,
                    "type": "tilde",
                }, indent=2)

        # Comparison operators
        satisfies = True
        for part in range.replace(",", " ").split():
            part = part.strip()
            if part.startswith(">="):
                satisfies = satisfies and self._compare_versions(version, part[2:]) >= 0
            elif part.startswith("<="):
                satisfies = satisfies and self._compare_versions(version, part[2:]) <= 0
            elif part.startswith(">"):
                satisfies = satisfies and self._compare_versions(version, part[1:]) > 0
            elif part.startswith("<"):
                satisfies = satisfies and self._compare_versions(version, part[1:]) < 0
            elif part.startswith("="):
                satisfies = satisfies and self._compare_versions(version, part[1:]) == 0

        return json.dumps({
            "satisfies": satisfies,
            "version": version,
            "range": range,
        }, indent=2)

    def semver_sort(
        self,
        versions: list,
        descending: bool = False,
    ) -> str:
        """Sort versions."""
        from functools import cmp_to_key

        valid = []
        invalid = []

        for v in versions:
            if self._parse_version(v):
                valid.append(v)
            else:
                invalid.append(v)

        sorted_versions = sorted(
            valid,
            key=cmp_to_key(self._compare_versions),
            reverse=descending,
        )

        return json.dumps({
            "sorted": sorted_versions,
            "invalid": invalid,
            "order": "descending" if descending else "ascending",
        }, indent=2)

    def semver_valid(self, version: str) -> str:
        """Validate semver."""
        parsed = self._parse_version(version)

        return json.dumps({
            "version": version,
            "valid": parsed is not None,
            "normalized": version.lstrip("v") if parsed else None,
        }, indent=2)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        if "version" in kwargs:
            return self.semver_parse(kwargs["version"])
        return "Provide a version to parse"
