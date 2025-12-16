"""
CSV Skill for R CLI.

CSV data manipulation:
- Read and write CSV files
- Filter and transform data
- Aggregate and statistics
- Convert to/from JSON
"""

import csv
import io
import json
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class CSVSkill(Skill):
    """Skill for CSV manipulation."""

    name = "csv"
    description = "CSV: read, write, filter, aggregate and transform tabular data"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="csv_read",
                description="Read a CSV file and return as JSON array",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to CSV file",
                        },
                        "delimiter": {
                            "type": "string",
                            "description": "Field delimiter (default: ,)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum rows to return",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.csv_read,
            ),
            Tool(
                name="csv_write",
                description="Write data to a CSV file",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Output file path",
                        },
                        "data": {
                            "type": "string",
                            "description": "JSON array of objects to write",
                        },
                        "delimiter": {
                            "type": "string",
                            "description": "Field delimiter (default: ,)",
                        },
                    },
                    "required": ["file_path", "data"],
                },
                handler=self.csv_write,
            ),
            Tool(
                name="csv_filter",
                description="Filter CSV rows by condition",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to CSV file",
                        },
                        "column": {
                            "type": "string",
                            "description": "Column to filter on",
                        },
                        "operator": {
                            "type": "string",
                            "description": "Operator: eq, ne, gt, lt, gte, lte, contains",
                        },
                        "value": {
                            "type": "string",
                            "description": "Value to compare",
                        },
                    },
                    "required": ["file_path", "column", "operator", "value"],
                },
                handler=self.csv_filter,
            ),
            Tool(
                name="csv_stats",
                description="Get statistics for a CSV column",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to CSV file",
                        },
                        "column": {
                            "type": "string",
                            "description": "Column to analyze (optional, analyzes all if not specified)",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.csv_stats,
            ),
            Tool(
                name="csv_to_json",
                description="Convert CSV to JSON",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "CSV content as string",
                        },
                        "delimiter": {
                            "type": "string",
                            "description": "Field delimiter (default: ,)",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.csv_to_json,
            ),
            Tool(
                name="csv_from_json",
                description="Convert JSON array to CSV",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "JSON array of objects",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.csv_from_json,
            ),
            Tool(
                name="csv_columns",
                description="Get column names from a CSV file",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to CSV file",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.csv_columns,
            ),
            Tool(
                name="csv_aggregate",
                description="Aggregate CSV data (sum, avg, count, min, max)",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to CSV file",
                        },
                        "group_by": {
                            "type": "string",
                            "description": "Column to group by",
                        },
                        "agg_column": {
                            "type": "string",
                            "description": "Column to aggregate",
                        },
                        "operation": {
                            "type": "string",
                            "description": "Operation: sum, avg, count, min, max",
                        },
                    },
                    "required": ["file_path", "agg_column", "operation"],
                },
                handler=self.csv_aggregate,
            ),
        ]

    def csv_read(
        self,
        file_path: str,
        delimiter: str = ",",
        limit: Optional[int] = None,
    ) -> str:
        """Read CSV file and return as JSON."""
        try:
            path = Path(file_path).expanduser()
            if not path.exists():
                return f"Error: File not found: {file_path}"

            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                rows = []
                for i, row in enumerate(reader):
                    if limit and i >= limit:
                        break
                    rows.append(dict(row))

            return json.dumps(rows, indent=2, ensure_ascii=False)

        except Exception as e:
            return f"Error reading CSV: {e}"

    def csv_write(
        self,
        file_path: str,
        data: str,
        delimiter: str = ",",
    ) -> str:
        """Write JSON data to CSV file."""
        try:
            rows = json.loads(data)
            if not rows:
                return "Error: No data to write"

            path = Path(file_path).expanduser()
            fieldnames = list(rows[0].keys())

            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
                writer.writeheader()
                writer.writerows(rows)

            return f"Written {len(rows)} rows to {file_path}"

        except json.JSONDecodeError as e:
            return f"Error parsing JSON: {e}"
        except Exception as e:
            return f"Error writing CSV: {e}"

    def csv_filter(
        self,
        file_path: str,
        column: str,
        operator: str,
        value: str,
    ) -> str:
        """Filter CSV rows by condition."""
        try:
            path = Path(file_path).expanduser()
            if not path.exists():
                return f"Error: File not found: {file_path}"

            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if not rows:
                return "[]"

            if column not in rows[0]:
                return f"Error: Column '{column}' not found"

            def compare(row_value: str) -> bool:
                try:
                    # Try numeric comparison
                    rv = float(row_value) if row_value else 0
                    v = float(value)
                    if operator == "gt":
                        return rv > v
                    elif operator == "lt":
                        return rv < v
                    elif operator == "gte":
                        return rv >= v
                    elif operator == "lte":
                        return rv <= v
                except ValueError:
                    pass

                # String comparison
                if operator == "eq":
                    return row_value == value
                elif operator == "ne":
                    return row_value != value
                elif operator == "contains":
                    return value.lower() in row_value.lower()

                return False

            filtered = [row for row in rows if compare(row.get(column, ""))]
            return json.dumps(filtered, indent=2, ensure_ascii=False)

        except Exception as e:
            return f"Error filtering CSV: {e}"

    def csv_stats(self, file_path: str, column: Optional[str] = None) -> str:
        """Get statistics for CSV columns."""
        try:
            path = Path(file_path).expanduser()
            if not path.exists():
                return f"Error: File not found: {file_path}"

            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if not rows:
                return "No data"

            stats = {
                "total_rows": len(rows),
                "columns": list(rows[0].keys()),
            }

            columns_to_analyze = [column] if column else rows[0].keys()

            for col in columns_to_analyze:
                if col not in rows[0]:
                    continue

                values = [row.get(col, "") for row in rows]
                numeric_values = []

                for v in values:
                    try:
                        numeric_values.append(float(v))
                    except (ValueError, TypeError):
                        pass

                col_stats = {
                    "non_empty": len([v for v in values if v]),
                    "unique": len(set(values)),
                }

                if numeric_values:
                    col_stats["numeric_count"] = len(numeric_values)
                    col_stats["sum"] = sum(numeric_values)
                    col_stats["avg"] = sum(numeric_values) / len(numeric_values)
                    col_stats["min"] = min(numeric_values)
                    col_stats["max"] = max(numeric_values)

                stats[col] = col_stats

            return json.dumps(stats, indent=2, ensure_ascii=False)

        except Exception as e:
            return f"Error: {e}"

    def csv_to_json(self, data: str, delimiter: str = ",") -> str:
        """Convert CSV string to JSON."""
        try:
            reader = csv.DictReader(io.StringIO(data), delimiter=delimiter)
            rows = [dict(row) for row in reader]
            return json.dumps(rows, indent=2, ensure_ascii=False)
        except Exception as e:
            return f"Error: {e}"

    def csv_from_json(self, data: str) -> str:
        """Convert JSON array to CSV string."""
        try:
            rows = json.loads(data)
            if not rows:
                return ""

            output = io.StringIO()
            fieldnames = list(rows[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

            return output.getvalue()

        except json.JSONDecodeError as e:
            return f"Error parsing JSON: {e}"
        except Exception as e:
            return f"Error: {e}"

    def csv_columns(self, file_path: str) -> str:
        """Get column names from CSV."""
        try:
            path = Path(file_path).expanduser()
            if not path.exists():
                return f"Error: File not found: {file_path}"

            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader, [])

            return json.dumps(headers, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def csv_aggregate(
        self,
        file_path: str,
        agg_column: str,
        operation: str,
        group_by: Optional[str] = None,
    ) -> str:
        """Aggregate CSV data."""
        try:
            path = Path(file_path).expanduser()
            if not path.exists():
                return f"Error: File not found: {file_path}"

            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if not rows:
                return "No data"

            def aggregate(values: list) -> float:
                nums = []
                for v in values:
                    try:
                        nums.append(float(v))
                    except (ValueError, TypeError):
                        pass

                if not nums:
                    return 0

                if operation == "sum":
                    return sum(nums)
                elif operation == "avg":
                    return sum(nums) / len(nums)
                elif operation == "count":
                    return len(nums)
                elif operation == "min":
                    return min(nums)
                elif operation == "max":
                    return max(nums)
                return 0

            if group_by:
                groups: dict[str, list] = {}
                for row in rows:
                    key = row.get(group_by, "")
                    if key not in groups:
                        groups[key] = []
                    groups[key].append(row.get(agg_column, ""))

                result = {k: aggregate(v) for k, v in groups.items()}
            else:
                values = [row.get(agg_column, "") for row in rows]
                result = {f"{operation}({agg_column})": aggregate(values)}

            return json.dumps(result, indent=2, ensure_ascii=False)

        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "read")

        if action == "read":
            return self.csv_read(kwargs.get("file", ""))
        elif action == "write":
            return self.csv_write(kwargs.get("file", ""), kwargs.get("data", ""))
        elif action == "filter":
            return self.csv_filter(
                kwargs.get("file", ""),
                kwargs.get("column", ""),
                kwargs.get("operator", "eq"),
                kwargs.get("value", ""),
            )
        elif action == "stats":
            return self.csv_stats(kwargs.get("file", ""), kwargs.get("column"))
        else:
            return f"Unknown action: {action}"
