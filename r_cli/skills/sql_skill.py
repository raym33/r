"""
SQL Skill for R CLI.

Features:
- Text-to-SQL: Convert natural language to SQL queries
- Execute queries on local databases (SQLite, DuckDB)
- Analyze CSVs with SQL
- Create and manage databases
"""

import os
from pathlib import Path

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class SQLSkill(Skill):
    """Skill for natural language SQL queries."""

    name = "sql"
    description = "SQL queries on local databases and CSVs"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._duckdb_conn = None

    @property
    def duckdb(self):
        """Lazy loading of DuckDB."""
        if self._duckdb_conn is None:
            try:
                import duckdb

                # In-memory connection with optional persistence
                db_path = os.path.join(os.path.expanduser(self.config.home_dir), "r_cli.duckdb")
                self._duckdb_conn = duckdb.connect(db_path)
            except ImportError:
                return None
        return self._duckdb_conn

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="query_csv",
                description="Execute a SQL query on a CSV file",
                parameters={
                    "type": "object",
                    "properties": {
                        "csv_path": {
                            "type": "string",
                            "description": "Path to the CSV file",
                        },
                        "query": {
                            "type": "string",
                            "description": "SQL query (use 'data' as table name)",
                        },
                    },
                    "required": ["csv_path", "query"],
                },
                handler=self.query_csv,
            ),
            Tool(
                name="query_database",
                description="Execute a SQL query on the local database",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "SQL query to execute",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Row limit to return (default: 100)",
                        },
                    },
                    "required": ["query"],
                },
                handler=self.query_database,
            ),
            Tool(
                name="describe_csv",
                description="Show structure and statistics of a CSV",
                parameters={
                    "type": "object",
                    "properties": {
                        "csv_path": {
                            "type": "string",
                            "description": "Path to the CSV file",
                        },
                    },
                    "required": ["csv_path"],
                },
                handler=self.describe_csv,
            ),
            Tool(
                name="import_csv_to_db",
                description="Import a CSV to a table in the local database",
                parameters={
                    "type": "object",
                    "properties": {
                        "csv_path": {
                            "type": "string",
                            "description": "Path to the CSV file",
                        },
                        "table_name": {
                            "type": "string",
                            "description": "Name of the table to create",
                        },
                    },
                    "required": ["csv_path", "table_name"],
                },
                handler=self.import_csv_to_db,
            ),
            Tool(
                name="list_tables",
                description="List available tables in the database",
                parameters={"type": "object", "properties": {}},
                handler=self.list_tables,
            ),
            Tool(
                name="describe_table",
                description="Show the structure of a table",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Table name",
                        },
                    },
                    "required": ["table_name"],
                },
                handler=self.describe_table,
            ),
        ]

    def query_csv(self, csv_path: str, query: str) -> str:
        """Execute SQL on a CSV using DuckDB."""
        try:
            if self.duckdb is None:
                return "Error: DuckDB not installed. Run: pip install duckdb"

            path = Path(csv_path)
            if not path.exists():
                return f"Error: CSV not found: {csv_path}"

            # Replace 'data' with actual CSV path
            actual_query = query.replace("data", f"'{csv_path}'")
            actual_query = actual_query.replace("FROM csv", f"FROM '{csv_path}'")

            # If query doesn't have FROM with path, add it
            if "FROM" not in actual_query.upper() or csv_path not in actual_query:
                # Try to detect table name used
                if " data" in actual_query.lower() or "from data" in actual_query.lower():
                    actual_query = actual_query.replace(" data", f" '{csv_path}'")

            result = self.duckdb.execute(actual_query).fetchdf()

            # Format result
            if len(result) == 0:
                return "Query executed. No results."

            # Limit rows for display
            display_df = result.head(50)

            output = [f"Results ({len(result)} rows):\n"]
            output.append(display_df.to_string(index=False))

            if len(result) > 50:
                output.append(f"\n... (showing 50 of {len(result)} rows)")

            return "\n".join(output)

        except Exception as e:
            return f"Error executing query: {e}"

    def query_database(self, query: str, limit: int = 100) -> str:
        """Execute SQL on the local database."""
        try:
            if self.duckdb is None:
                return "Error: DuckDB not installed. Run: pip install duckdb"

            # Add LIMIT if not present and is SELECT
            if query.strip().upper().startswith("SELECT") and "LIMIT" not in query.upper():
                query = f"{query} LIMIT {limit}"

            result = self.duckdb.execute(query).fetchdf()

            if len(result) == 0:
                if query.strip().upper().startswith("SELECT"):
                    return "Query executed. No results."
                else:
                    return "Query executed successfully."

            output = [f"Results ({len(result)} rows):\n"]
            output.append(result.to_string(index=False))

            return "\n".join(output)

        except Exception as e:
            return f"Error executing query: {e}"

    def describe_csv(self, csv_path: str) -> str:
        """Describe the structure and statistics of a CSV."""
        try:
            if self.duckdb is None:
                # Fallback to pandas
                try:
                    import pandas as pd

                    df = pd.read_csv(csv_path, nrows=1000)

                    output = [f"Analysis of: {Path(csv_path).name}\n"]
                    output.append(f"Rows (sample): {len(df)}")
                    output.append(f"Columns: {len(df.columns)}\n")

                    output.append("Columns:")
                    for col in df.columns:
                        dtype = str(df[col].dtype)
                        nulls = df[col].isnull().sum()
                        output.append(f"  - {col}: {dtype} ({nulls} nulls)")

                    return "\n".join(output)

                except ImportError:
                    return "Error: DuckDB or Pandas required"

            path = Path(csv_path)
            if not path.exists():
                return f"Error: CSV not found: {csv_path}"

            # Use DuckDB for analysis
            output = [f"Analysis of: {path.name}\n"]

            # Count rows
            count = self.duckdb.execute(f"SELECT COUNT(*) FROM '{csv_path}'").fetchone()[0]
            output.append(f"Total rows: {count:,}")

            # Get schema
            schema = self.duckdb.execute(f"DESCRIBE SELECT * FROM '{csv_path}'").fetchdf()

            output.append(f"Columns: {len(schema)}\n")
            output.append("Structure:")

            for _, row in schema.iterrows():
                output.append(f"  - {row['column_name']}: {row['column_type']}")

            # Basic statistics for numeric columns
            output.append("\nStatistics (numeric columns):")
            try:
                stats = self.duckdb.execute(
                    f"SELECT * FROM (SUMMARIZE SELECT * FROM '{csv_path}')"
                ).fetchdf()

                for _, row in stats.iterrows():
                    if row["column_type"] in ["INTEGER", "DOUBLE", "FLOAT", "BIGINT"]:
                        output.append(
                            f"  {row['column_name']}: min={row['min']}, max={row['max']}, avg={row['avg']:.2f}"
                        )
            except Exception:
                pass

            return "\n".join(output)

        except Exception as e:
            return f"Error describing CSV: {e}"

    def import_csv_to_db(self, csv_path: str, table_name: str) -> str:
        """Import a CSV to a persistent table."""
        try:
            if self.duckdb is None:
                return "Error: DuckDB not installed"

            path = Path(csv_path)
            if not path.exists():
                return f"Error: CSV not found: {csv_path}"

            # Create table from CSV
            self.duckdb.execute(
                f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM '{csv_path}'"
            )

            # Count imported rows
            count = self.duckdb.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

            return f"Imported: {count:,} rows to table '{table_name}'"

        except Exception as e:
            return f"Error importing CSV: {e}"

    def list_tables(self) -> str:
        """List tables in the database."""
        try:
            if self.duckdb is None:
                return "Error: DuckDB not installed"

            tables = self.duckdb.execute("SHOW TABLES").fetchdf()

            if len(tables) == 0:
                return "No tables in the database.\nUse import_csv_to_db to import data."

            output = ["Available tables:\n"]

            for _, row in tables.iterrows():
                table_name = row["name"]
                try:
                    count = self.duckdb.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                    output.append(f"  - {table_name} ({count:,} rows)")
                except Exception:
                    output.append(f"  - {table_name}")

            return "\n".join(output)

        except Exception as e:
            return f"Error listing tables: {e}"

    def describe_table(self, table_name: str) -> str:
        """Describe the structure of a table."""
        try:
            if self.duckdb is None:
                return "Error: DuckDB not installed"

            # Verify it exists
            tables = self.duckdb.execute("SHOW TABLES").fetchdf()
            if table_name not in tables["name"].values:
                return f"Error: Table not found: {table_name}"

            schema = self.duckdb.execute(f"DESCRIBE {table_name}").fetchdf()

            output = [f"Structure of: {table_name}\n"]

            for _, row in schema.iterrows():
                nullable = "NULL" if row["null"] == "YES" else "NOT NULL"
                output.append(f"  - {row['column_name']}: {row['column_type']} {nullable}")

            # Count rows
            count = self.duckdb.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            output.append(f"\nTotal rows: {count:,}")

            # Preview
            preview = self.duckdb.execute(f"SELECT * FROM {table_name} LIMIT 5").fetchdf()
            output.append("\nPreview (5 rows):")
            output.append(preview.to_string(index=False))

            return "\n".join(output)

        except Exception as e:
            return f"Error describing table: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        query = kwargs.get("query", "")
        csv_path = kwargs.get("csv")

        if csv_path:
            return self.query_csv(csv_path, query)
        elif query:
            return self.query_database(query)
        else:
            return self.list_tables()
