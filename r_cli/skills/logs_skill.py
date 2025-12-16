"""
Logs Skill for R CLI.

Observability and log analysis:
- Tail and filter log files
- Summarize logs with LLM
- Explain crash loops in Docker/compose
- Diff and compare test runs or stack traces
"""

import os
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class LogsSkill(Skill):
    """Skill for log analysis and observability."""

    name = "logs"
    description = "Log analysis: tail, summarize, explain crashes, diff runs"

    TIMEOUT = 120

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="tail_logs",
                description="Tail a log file or Docker container logs with optional filtering",
                parameters={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "Log file path or Docker container name/ID",
                        },
                        "lines": {
                            "type": "integer",
                            "description": "Number of lines to return (default: 100)",
                        },
                        "filter": {
                            "type": "string",
                            "description": "Regex pattern to filter lines",
                        },
                        "level": {
                            "type": "string",
                            "enum": ["error", "warn", "info", "debug", "all"],
                            "description": "Log level filter (default: all)",
                        },
                        "since": {
                            "type": "string",
                            "description": "Time filter for Docker logs (e.g., '1h', '30m', '2024-01-01')",
                        },
                    },
                    "required": ["source"],
                },
                handler=self.tail_logs,
            ),
            Tool(
                name="summarize_logs",
                description="Analyze and summarize log content, identifying errors, warnings, and patterns",
                parameters={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "Log file path or Docker container name/ID",
                        },
                        "lines": {
                            "type": "integer",
                            "description": "Number of recent lines to analyze (default: 500)",
                        },
                        "focus": {
                            "type": "string",
                            "enum": ["errors", "warnings", "patterns", "timeline", "all"],
                            "description": "What to focus on (default: all)",
                        },
                    },
                    "required": ["source"],
                },
                handler=self.summarize_logs,
            ),
            Tool(
                name="explain_crash",
                description="Analyze crash loops or failures in Docker containers or compose services",
                parameters={
                    "type": "object",
                    "properties": {
                        "container": {
                            "type": "string",
                            "description": "Container name/ID or compose service name",
                        },
                        "compose_file": {
                            "type": "string",
                            "description": "Path to docker-compose.yml (optional)",
                        },
                        "include_events": {
                            "type": "boolean",
                            "description": "Include Docker events in analysis (default: true)",
                        },
                    },
                    "required": ["container"],
                },
                handler=self.explain_crash,
            ),
            Tool(
                name="diff_runs",
                description="Compare two test runs, stack traces, or log segments",
                parameters={
                    "type": "object",
                    "properties": {
                        "source1": {
                            "type": "string",
                            "description": "First file path or text content",
                        },
                        "source2": {
                            "type": "string",
                            "description": "Second file path or text content",
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["pytest", "stacktrace", "logs", "auto"],
                            "description": "Comparison mode (default: auto)",
                        },
                    },
                    "required": ["source1", "source2"],
                },
                handler=self.diff_runs,
            ),
            Tool(
                name="watch_logs",
                description="Get recent log activity across multiple sources",
                parameters={
                    "type": "object",
                    "properties": {
                        "sources": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of log files or container names",
                        },
                        "lines_each": {
                            "type": "integer",
                            "description": "Lines per source (default: 50)",
                        },
                        "errors_only": {
                            "type": "boolean",
                            "description": "Only show errors and warnings",
                        },
                    },
                    "required": ["sources"],
                },
                handler=self.watch_logs,
            ),
        ]

    def _is_docker_container(self, source: str) -> bool:
        """Check if source is a Docker container."""
        try:
            result = subprocess.run(
                ["docker", "inspect", source],
                check=False,
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _get_file_logs(self, path: str, lines: int = 100) -> str:
        """Read last N lines from a file."""
        try:
            p = Path(path).expanduser()
            if not p.exists():
                return f"Error: File not found: {path}"

            with open(p, errors="replace") as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except Exception as e:
            return f"Error reading file: {e}"

    def _get_docker_logs(
        self, container: str, lines: int = 100, since: Optional[str] = None
    ) -> str:
        """Get Docker container logs."""
        try:
            cmd = ["docker", "logs", "--tail", str(lines)]
            if since:
                cmd.extend(["--since", since])
            cmd.append(container)

            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
            )

            output = result.stdout + result.stderr
            if not output and result.returncode != 0:
                return f"Error: Could not get logs for container '{container}'"
            return output
        except subprocess.TimeoutExpired:
            return "Error: Timeout getting Docker logs"
        except FileNotFoundError:
            return "Error: Docker not found"

    def _filter_logs(
        self,
        logs: str,
        pattern: Optional[str] = None,
        level: str = "all",
    ) -> str:
        """Filter log lines by pattern and/or level."""
        lines = logs.split("\n")

        # Level patterns
        level_patterns = {
            "error": r"(error|exception|fatal|critical|panic|fail)",
            "warn": r"(warn|warning)",
            "info": r"(info|notice)",
            "debug": r"(debug|trace|verbose)",
        }

        filtered = []
        for line in lines:
            # Level filter
            if level != "all":
                if not re.search(level_patterns.get(level, ""), line, re.IGNORECASE):
                    continue

            # Pattern filter
            if pattern:
                try:
                    if not re.search(pattern, line, re.IGNORECASE):
                        continue
                except re.error:
                    # Invalid regex, treat as literal
                    if pattern.lower() not in line.lower():
                        continue

            filtered.append(line)

        return "\n".join(filtered)

    def tail_logs(
        self,
        source: str,
        lines: int = 100,
        filter: Optional[str] = None,
        level: str = "all",
        since: Optional[str] = None,
    ) -> str:
        """Tail logs from file or Docker container."""
        # Determine source type
        if self._is_docker_container(source):
            logs = self._get_docker_logs(source, lines, since)
        else:
            logs = self._get_file_logs(source, lines)

        if logs.startswith("Error:"):
            return logs

        # Apply filters
        if filter or level != "all":
            logs = self._filter_logs(logs, filter, level)

        if not logs.strip():
            return "No matching log entries found"

        line_count = len(logs.strip().split("\n"))
        return f"=== {line_count} log entries from {source} ===\n\n{logs}"

    def summarize_logs(
        self,
        source: str,
        lines: int = 500,
        focus: str = "all",
    ) -> str:
        """Analyze and summarize logs."""
        # Get logs
        if self._is_docker_container(source):
            logs = self._get_docker_logs(source, lines)
        else:
            logs = self._get_file_logs(source, lines)

        if logs.startswith("Error:"):
            return logs

        log_lines = logs.strip().split("\n")
        total_lines = len(log_lines)

        # Analyze
        errors = []
        warnings = []
        patterns = Counter()
        timestamps = []

        error_pattern = re.compile(r"(error|exception|fatal|critical|panic|fail)", re.I)
        warn_pattern = re.compile(r"(warn|warning)", re.I)
        timestamp_pattern = re.compile(
            r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}|\d{2}:\d{2}:\d{2})"
        )

        for line in log_lines:
            # Extract timestamp
            ts_match = timestamp_pattern.search(line)
            if ts_match:
                timestamps.append(ts_match.group(1))

            # Categorize
            if error_pattern.search(line):
                errors.append(line.strip())
                # Extract error type
                err_match = re.search(r"(\w+Error|\w+Exception|\w+Fault)", line)
                if err_match:
                    patterns[err_match.group(1)] += 1
            elif warn_pattern.search(line):
                warnings.append(line.strip())

        # Build summary
        summary = [f"=== Log Summary: {source} ===\n"]
        summary.append(f"Total lines analyzed: {total_lines}")

        if focus in ("errors", "all"):
            summary.append(f"\n## Errors ({len(errors)} found)")
            if errors:
                # Show unique errors (deduplicated)
                unique_errors = list(dict.fromkeys(errors))[:10]
                for e in unique_errors:
                    summary.append(f"  - {e[:200]}")
                if len(errors) > 10:
                    summary.append(f"  ... and {len(errors) - 10} more")
            else:
                summary.append("  No errors found")

        if focus in ("warnings", "all"):
            summary.append(f"\n## Warnings ({len(warnings)} found)")
            if warnings:
                unique_warnings = list(dict.fromkeys(warnings))[:5]
                for w in unique_warnings:
                    summary.append(f"  - {w[:200]}")
                if len(warnings) > 5:
                    summary.append(f"  ... and {len(warnings) - 5} more")
            else:
                summary.append("  No warnings found")

        if focus in ("patterns", "all") and patterns:
            summary.append("\n## Error Patterns")
            for pattern, count in patterns.most_common(10):
                summary.append(f"  - {pattern}: {count} occurrences")

        if focus in ("timeline", "all") and timestamps:
            summary.append("\n## Timeline")
            summary.append(f"  First entry: {timestamps[0]}")
            summary.append(f"  Last entry: {timestamps[-1]}")

        # Health assessment
        summary.append("\n## Health Assessment")
        if len(errors) == 0:
            summary.append("  Status: HEALTHY - No errors detected")
        elif len(errors) < 5:
            summary.append("  Status: WARNING - Few errors detected")
        else:
            error_rate = len(errors) / total_lines * 100
            summary.append(
                f"  Status: UNHEALTHY - {len(errors)} errors ({error_rate:.1f}% of logs)"
            )

        return "\n".join(summary)

    def explain_crash(
        self,
        container: str,
        compose_file: Optional[str] = None,
        include_events: bool = True,
    ) -> str:
        """Analyze crash loops in Docker containers."""
        analysis = [f"=== Crash Analysis: {container} ===\n"]

        # Get container status
        try:
            inspect_result = subprocess.run(
                ["docker", "inspect", "--format", "{{json .State}}", container],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if inspect_result.returncode == 0:
                import json

                state = json.loads(inspect_result.stdout)
                analysis.append("## Container State")
                analysis.append(f"  Status: {state.get('Status', 'unknown')}")
                analysis.append(f"  Running: {state.get('Running', False)}")
                analysis.append(f"  Exit Code: {state.get('ExitCode', 'N/A')}")
                if state.get("Error"):
                    analysis.append(f"  Error: {state.get('Error')}")
                if state.get("OOMKilled"):
                    analysis.append("  OOM Killed: YES - Container ran out of memory!")

                # Restart count
                inspect_full = subprocess.run(
                    ["docker", "inspect", "--format", "{{.RestartCount}}", container],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if inspect_full.returncode == 0:
                    restarts = inspect_full.stdout.strip()
                    analysis.append(f"  Restart Count: {restarts}")
                    if int(restarts or 0) > 5:
                        analysis.append("  WARNING: High restart count indicates crash loop!")
            else:
                analysis.append(f"Container '{container}' not found or not accessible")
                return "\n".join(analysis)

        except Exception as e:
            analysis.append(f"Error inspecting container: {e}")

        # Get recent logs
        analysis.append("\n## Recent Logs (last 50 lines)")
        logs = self._get_docker_logs(container, 50)
        error_logs = self._filter_logs(logs, level="error")
        if error_logs.strip():
            analysis.append("Errors found:")
            for line in error_logs.strip().split("\n")[:10]:
                analysis.append(f"  {line[:200]}")
        else:
            analysis.append("No obvious errors in recent logs")

        # Get Docker events if requested
        if include_events:
            try:
                events_result = subprocess.run(
                    [
                        "docker",
                        "events",
                        "--filter",
                        f"container={container}",
                        "--since",
                        "1h",
                        "--until",
                        "0s",
                        "--format",
                        "{{.Time}} {{.Action}}: {{.Actor.Attributes.exitCode}}",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if events_result.stdout.strip():
                    analysis.append("\n## Recent Events (last hour)")
                    for line in events_result.stdout.strip().split("\n")[-10:]:
                        analysis.append(f"  {line}")
            except Exception:
                pass

        # Check compose context if provided
        if compose_file:
            analysis.append("\n## Compose Context")
            try:
                result = subprocess.run(
                    ["docker", "compose", "-f", compose_file, "ps", "--format", "json"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    analysis.append("Compose services status available")
            except Exception:
                pass

        # Diagnosis
        analysis.append("\n## Possible Causes")
        if "OOMKilled" in str(analysis):
            analysis.append("  1. MEMORY: Container killed due to OOM - increase memory limits")
        if "exit code" in str(analysis).lower() or "Exit Code: 1" in str(analysis):
            analysis.append("  2. APPLICATION: App crashed - check logs for stack traces")
        if "connection refused" in logs.lower():
            analysis.append("  3. DEPENDENCY: Cannot connect to required service")
        if "permission denied" in logs.lower():
            analysis.append("  4. PERMISSIONS: File or network permission issues")

        return "\n".join(analysis)

    def diff_runs(
        self,
        source1: str,
        source2: str,
        mode: str = "auto",
    ) -> str:
        """Compare two test runs or log segments."""

        def read_source(src: str) -> str:
            """Read from file or use as content."""
            p = Path(src).expanduser()
            if p.exists():
                return p.read_text(errors="replace")
            return src

        content1 = read_source(source1)
        content2 = read_source(source2)

        # Auto-detect mode
        if mode == "auto":
            if "PASSED" in content1 or "FAILED" in content1 or "pytest" in content1.lower():
                mode = "pytest"
            elif "Traceback" in content1 or "Exception" in content1:
                mode = "stacktrace"
            else:
                mode = "logs"

        result = [f"=== Diff Analysis (mode: {mode}) ===\n"]

        if mode == "pytest":
            # Extract test results
            def extract_tests(content: str) -> dict:
                tests = {"passed": [], "failed": [], "skipped": [], "errors": []}
                for line in content.split("\n"):
                    if " PASSED" in line:
                        match = re.search(r"([\w:]+)\s+PASSED", line)
                        if match:
                            tests["passed"].append(match.group(1))
                    elif " FAILED" in line:
                        match = re.search(r"([\w:]+)\s+FAILED", line)
                        if match:
                            tests["failed"].append(match.group(1))
                    elif " SKIPPED" in line:
                        match = re.search(r"([\w:]+)\s+SKIPPED", line)
                        if match:
                            tests["skipped"].append(match.group(1))
                    elif " ERROR" in line:
                        match = re.search(r"([\w:]+)\s+ERROR", line)
                        if match:
                            tests["errors"].append(match.group(1))
                return tests

            tests1 = extract_tests(content1)
            tests2 = extract_tests(content2)

            result.append("## Run 1 Summary")
            result.append(
                f"  Passed: {len(tests1['passed'])}, Failed: {len(tests1['failed'])}, Skipped: {len(tests1['skipped'])}"
            )

            result.append("\n## Run 2 Summary")
            result.append(
                f"  Passed: {len(tests2['passed'])}, Failed: {len(tests2['failed'])}, Skipped: {len(tests2['skipped'])}"
            )

            # Find regressions (passed in 1, failed in 2)
            regressions = set(tests1["passed"]) & set(tests2["failed"])
            if regressions:
                result.append("\n## REGRESSIONS (newly failing)")
                for t in regressions:
                    result.append(f"  - {t}")

            # Find fixes (failed in 1, passed in 2)
            fixes = set(tests1["failed"]) & set(tests2["passed"])
            if fixes:
                result.append("\n## FIXES (now passing)")
                for t in fixes:
                    result.append(f"  - {t}")

            # New failures
            new_failures = set(tests2["failed"]) - set(tests1["failed"])
            if new_failures:
                result.append("\n## NEW FAILURES")
                for t in new_failures:
                    result.append(f"  - {t}")

        elif mode == "stacktrace":
            # Extract exception types and locations
            def extract_trace(content: str) -> list:
                traces = []
                current = []
                for line in content.split("\n"):
                    if "Traceback" in line:
                        if current:
                            traces.append("\n".join(current))
                        current = [line]
                    elif current:
                        current.append(line)
                        if re.match(r"^\w+Error|^\w+Exception", line):
                            traces.append("\n".join(current))
                            current = []
                return traces

            traces1 = extract_trace(content1)
            traces2 = extract_trace(content2)

            result.append(f"## Stack Traces in Source 1: {len(traces1)}")
            result.append(f"## Stack Traces in Source 2: {len(traces2)}")

            # Compare exception types
            def get_exception_type(trace: str) -> str:
                for line in trace.split("\n"):
                    if re.match(r"^\w+Error|^\w+Exception", line):
                        return line.split(":")[0]
                return "Unknown"

            types1 = Counter(get_exception_type(t) for t in traces1)
            types2 = Counter(get_exception_type(t) for t in traces2)

            if types1 != types2:
                result.append("\n## Exception Type Differences")
                all_types = set(types1.keys()) | set(types2.keys())
                for t in all_types:
                    c1, c2 = types1.get(t, 0), types2.get(t, 0)
                    if c1 != c2:
                        result.append(f"  {t}: {c1} -> {c2}")

        else:  # logs mode
            # Line-by-line diff summary
            lines1 = set(content1.strip().split("\n"))
            lines2 = set(content2.strip().split("\n"))

            only_in_1 = lines1 - lines2
            only_in_2 = lines2 - lines1
            common = lines1 & lines2

            result.append("## Line Statistics")
            result.append(f"  Source 1: {len(lines1)} unique lines")
            result.append(f"  Source 2: {len(lines2)} unique lines")
            result.append(f"  Common: {len(common)} lines")
            result.append(f"  Only in 1: {len(only_in_1)} lines")
            result.append(f"  Only in 2: {len(only_in_2)} lines")

            # Show sample differences
            if only_in_2:
                result.append("\n## New in Source 2 (sample)")
                for line in list(only_in_2)[:5]:
                    if line.strip():
                        result.append(f"  + {line[:150]}")

        return "\n".join(result)

    def watch_logs(
        self,
        sources: list[str],
        lines_each: int = 50,
        errors_only: bool = False,
    ) -> str:
        """Get recent activity from multiple log sources."""
        result = ["=== Multi-Source Log Watch ===\n"]

        for source in sources:
            result.append(f"\n## {source}")
            result.append("-" * 40)

            if self._is_docker_container(source):
                logs = self._get_docker_logs(source, lines_each)
            else:
                logs = self._get_file_logs(source, lines_each)

            if logs.startswith("Error:"):
                result.append(logs)
                continue

            if errors_only:
                logs = self._filter_logs(logs, level="error")
                if not logs.strip():
                    result.append("  (no errors)")
                    continue

            # Truncate if too long
            lines = logs.strip().split("\n")
            if len(lines) > lines_each:
                lines = lines[-lines_each:]

            for line in lines[-20:]:  # Show max 20 per source in summary
                result.append(f"  {line[:200]}")

            if len(lines) > 20:
                result.append(f"  ... ({len(lines) - 20} more lines)")

        return "\n".join(result)

    def get_prompt(self) -> str:
        return """You are a log analysis expert. Help users:
- Analyze log files and Docker container logs
- Identify errors, warnings, and patterns
- Diagnose crash loops and failures
- Compare test runs to find regressions

Use tail_logs to get recent logs with filtering.
Use summarize_logs for a high-level overview of log health.
Use explain_crash to diagnose Docker container issues.
Use diff_runs to compare pytest outputs or stack traces.
Use watch_logs to monitor multiple sources at once.
"""
