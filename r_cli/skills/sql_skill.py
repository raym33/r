"""
SQL Skill for R CLI.

Features:
- Text-to-SQL: Convert natural language to SQL queries
- Execute queries on local databases (SQLite, DuckDB, PostgreSQL)
- Schema introspection: tables, columns, relationships, indexes
- Analyze CSVs with SQL
- Query explanation and optimization hints
"""

import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class SQLSkill(Skill):
    """Skill for natural language SQL queries and database introspection."""

    name = "sql"
    description = (
        "SQL queries, schema introspection, database management (SQLite, DuckDB, PostgreSQL)"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._duckdb_conn = None
        self._pg_conn = None
        self._sqlite_conn = None

    @property
    def duckdb(self):
        """Lazy loading of DuckDB."""
        if self._duckdb_conn is None:
            try:
                import duckdb

                db_path = os.path.join(os.path.expanduser(self.config.home_dir), "r_cli.duckdb")
                self._duckdb_conn = duckdb.connect(db_path)
            except ImportError:
                return None
        return self._duckdb_conn

    def _get_postgres_conn(self, connection_string: str):
        """Get PostgreSQL connection."""
        try:
            import psycopg2

            return psycopg2.connect(connection_string)
        except ImportError:
            return None

    def _get_sqlite_conn(self, db_path: str):
        """Get SQLite connection."""
        path = Path(db_path).expanduser()
        if not path.exists():
            return None
        return sqlite3.connect(str(path))

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
                name="query_postgres",
                description="Execute a SQL query on a PostgreSQL database",
                parameters={
                    "type": "object",
                    "properties": {
                        "connection_string": {
                            "type": "string",
                            "description": "PostgreSQL connection string (e.g., postgresql://user:pass@localhost/db)",
                        },
                        "query": {
                            "type": "string",
                            "description": "SQL query to execute",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Row limit (default: 100)",
                        },
                    },
                    "required": ["connection_string", "query"],
                },
                handler=self.query_postgres,
            ),
            Tool(
                name="query_sqlite",
                description="Execute a SQL query on a SQLite database file",
                parameters={
                    "type": "object",
                    "properties": {
                        "db_path": {
                            "type": "string",
                            "description": "Path to SQLite database file",
                        },
                        "query": {
                            "type": "string",
                            "description": "SQL query to execute",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Row limit (default: 100)",
                        },
                    },
                    "required": ["db_path", "query"],
                },
                handler=self.query_sqlite,
            ),
            Tool(
                name="introspect_schema",
                description="Get full schema introspection: tables, columns, relationships, indexes",
                parameters={
                    "type": "object",
                    "properties": {
                        "db_type": {
                            "type": "string",
                            "enum": ["duckdb", "postgres", "sqlite"],
                            "description": "Database type",
                        },
                        "connection_string": {
                            "type": "string",
                            "description": "Connection string (for postgres) or path (for sqlite)",
                        },
                        "table_name": {
                            "type": "string",
                            "description": "Specific table to introspect (optional, all if omitted)",
                        },
                    },
                    "required": ["db_type"],
                },
                handler=self.introspect_schema,
            ),
            Tool(
                name="explain_query",
                description="Get query execution plan (EXPLAIN) to understand performance",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "SQL query to explain",
                        },
                        "db_type": {
                            "type": "string",
                            "enum": ["duckdb", "postgres", "sqlite"],
                            "description": "Database type (default: duckdb)",
                        },
                        "connection_string": {
                            "type": "string",
                            "description": "Connection string (for postgres) or path (for sqlite)",
                        },
                        "analyze": {
                            "type": "boolean",
                            "description": "Run EXPLAIN ANALYZE for actual timing (default: false)",
                        },
                    },
                    "required": ["query"],
                },
                handler=self.explain_query,
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
                parameters={
                    "type": "object",
                    "properties": {
                        "db_type": {
                            "type": "string",
                            "enum": ["duckdb", "postgres", "sqlite"],
                            "description": "Database type (default: duckdb)",
                        },
                        "connection_string": {
                            "type": "string",
                            "description": "Connection string (for postgres) or path (for sqlite)",
                        },
                    },
                },
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
                        "db_type": {
                            "type": "string",
                            "enum": ["duckdb", "postgres", "sqlite"],
                            "description": "Database type (default: duckdb)",
                        },
                        "connection_string": {
                            "type": "string",
                            "description": "Connection string (for postgres) or path (for sqlite)",
                        },
                    },
                    "required": ["table_name"],
                },
                handler=self.describe_table,
            ),
            Tool(
                name="get_table_relationships",
                description="Get foreign key relationships for a table",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Table name",
                        },
                        "db_type": {
                            "type": "string",
                            "enum": ["duckdb", "postgres", "sqlite"],
                            "description": "Database type",
                        },
                        "connection_string": {
                            "type": "string",
                            "description": "Connection string (for postgres) or path (for sqlite)",
                        },
                    },
                    "required": ["table_name", "db_type"],
                },
                handler=self.get_table_relationships,
            ),
            Tool(
                name="get_indexes",
                description="Get indexes for a table or database",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Table name (optional, all tables if omitted)",
                        },
                        "db_type": {
                            "type": "string",
                            "enum": ["duckdb", "postgres", "sqlite"],
                            "description": "Database type",
                        },
                        "connection_string": {
                            "type": "string",
                            "description": "Connection string (for postgres) or path (for sqlite)",
                        },
                    },
                    "required": ["db_type"],
                },
                handler=self.get_indexes,
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

            if "FROM" not in actual_query.upper() or csv_path not in actual_query:
                if " data" in actual_query.lower() or "from data" in actual_query.lower():
                    actual_query = actual_query.replace(" data", f" '{csv_path}'")

            result = self.duckdb.execute(actual_query).fetchdf()

            if len(result) == 0:
                return "Query executed. No results."

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

    def query_postgres(self, connection_string: str, query: str, limit: int = 100) -> str:
        """Execute SQL on PostgreSQL."""
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError:
            return "Error: psycopg2 not installed. Run: pip install psycopg2-binary"

        try:
            conn = psycopg2.connect(connection_string)
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            if query.strip().upper().startswith("SELECT") and "LIMIT" not in query.upper():
                query = f"{query} LIMIT {limit}"

            cursor.execute(query)

            if cursor.description is None:
                conn.commit()
                conn.close()
                return "Query executed successfully."

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return "Query executed. No results."

            # Format as table
            columns = [desc[0] for desc in cursor.description]
            output = [f"Results ({len(rows)} rows):\n"]

            # Header
            output.append(" | ".join(columns))
            output.append("-" * (len(" | ".join(columns))))

            # Rows
            for row in rows[:50]:
                values = [str(row.get(col, "NULL"))[:50] for col in columns]
                output.append(" | ".join(values))

            if len(rows) > 50:
                output.append(f"\n... (showing 50 of {len(rows)} rows)")

            return "\n".join(output)

        except Exception as e:
            return f"Error executing query: {e}"

    def query_sqlite(self, db_path: str, query: str, limit: int = 100) -> str:
        """Execute SQL on SQLite."""
        try:
            path = Path(db_path).expanduser()
            if not path.exists():
                return f"Error: Database not found: {db_path}"

            conn = sqlite3.connect(str(path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if query.strip().upper().startswith("SELECT") and "LIMIT" not in query.upper():
                query = f"{query} LIMIT {limit}"

            cursor.execute(query)

            if cursor.description is None:
                conn.commit()
                conn.close()
                return "Query executed successfully."

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return "Query executed. No results."

            columns = [desc[0] for desc in cursor.description]
            output = [f"Results ({len(rows)} rows):\n"]

            output.append(" | ".join(columns))
            output.append("-" * (len(" | ".join(columns))))

            for row in rows[:50]:
                values = [str(row[col])[:50] if row[col] is not None else "NULL" for col in columns]
                output.append(" | ".join(values))

            if len(rows) > 50:
                output.append(f"\n... (showing 50 of {len(rows)} rows)")

            return "\n".join(output)

        except Exception as e:
            return f"Error executing query: {e}"

    def introspect_schema(
        self,
        db_type: str = "duckdb",
        connection_string: Optional[str] = None,
        table_name: Optional[str] = None,
    ) -> str:
        """Full schema introspection."""
        result = [f"=== Schema Introspection ({db_type}) ===\n"]

        try:
            if db_type == "duckdb":
                if self.duckdb is None:
                    return "Error: DuckDB not installed"

                # Get all tables
                tables_df = self.duckdb.execute("SHOW TABLES").fetchdf()
                tables = tables_df["name"].tolist() if len(tables_df) > 0 else []

                if table_name:
                    tables = [t for t in tables if t == table_name]

                for table in tables:
                    result.append(f"\n## Table: {table}")

                    # Columns
                    schema = self.duckdb.execute(f"DESCRIBE {table}").fetchdf()
                    result.append("  Columns:")
                    for _, row in schema.iterrows():
                        nullable = "NULL" if row.get("null") == "YES" else "NOT NULL"
                        result.append(
                            f"    - {row['column_name']}: {row['column_type']} {nullable}"
                        )

                    # Row count
                    count = self.duckdb.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    result.append(f"  Rows: {count:,}")

            elif db_type == "postgres":
                if not connection_string:
                    return "Error: connection_string required for PostgreSQL"

                import psycopg2

                conn = psycopg2.connect(connection_string)
                cursor = conn.cursor()

                # Get tables
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                tables = [row[0] for row in cursor.fetchall()]

                if table_name:
                    tables = [t for t in tables if t == table_name]

                for table in tables:
                    result.append(f"\n## Table: {table}")

                    # Columns with constraints
                    cursor.execute(
                        """
                        SELECT
                            c.column_name,
                            c.data_type,
                            c.is_nullable,
                            c.column_default,
                            tc.constraint_type
                        FROM information_schema.columns c
                        LEFT JOIN information_schema.key_column_usage kcu
                            ON c.table_name = kcu.table_name AND c.column_name = kcu.column_name
                        LEFT JOIN information_schema.table_constraints tc
                            ON kcu.constraint_name = tc.constraint_name
                        WHERE c.table_name = %s
                        ORDER BY c.ordinal_position
                    """,
                        (table,),
                    )

                    result.append("  Columns:")
                    for row in cursor.fetchall():
                        col_name, data_type, nullable, default, constraint = row
                        constraint_str = f" [{constraint}]" if constraint else ""
                        nullable_str = "NULL" if nullable == "YES" else "NOT NULL"
                        default_str = f" DEFAULT {default}" if default else ""
                        result.append(
                            f"    - {col_name}: {data_type} {nullable_str}{default_str}{constraint_str}"
                        )

                    # Foreign keys
                    cursor.execute(
                        """
                        SELECT
                            kcu.column_name,
                            ccu.table_name AS foreign_table,
                            ccu.column_name AS foreign_column
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                            ON tc.constraint_name = kcu.constraint_name
                        JOIN information_schema.constraint_column_usage ccu
                            ON ccu.constraint_name = tc.constraint_name
                        WHERE tc.constraint_type = 'FOREIGN KEY'
                            AND tc.table_name = %s
                    """,
                        (table,),
                    )

                    fks = cursor.fetchall()
                    if fks:
                        result.append("  Foreign Keys:")
                        for fk in fks:
                            result.append(f"    - {fk[0]} -> {fk[1]}.{fk[2]}")

                    # Row count
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    result.append(f"  Rows: {count:,}")

                conn.close()

            elif db_type == "sqlite":
                if not connection_string:
                    return "Error: connection_string (db path) required for SQLite"

                conn = sqlite3.connect(connection_string)
                cursor = conn.cursor()

                # Get tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = [row[0] for row in cursor.fetchall()]

                if table_name:
                    tables = [t for t in tables if t == table_name]

                for table in tables:
                    result.append(f"\n## Table: {table}")

                    # Columns
                    cursor.execute(f"PRAGMA table_info({table})")
                    result.append("  Columns:")
                    for row in cursor.fetchall():
                        cid, name, dtype, notnull, default, pk = row
                        nullable = "NOT NULL" if notnull else "NULL"
                        pk_str = " [PRIMARY KEY]" if pk else ""
                        default_str = f" DEFAULT {default}" if default else ""
                        result.append(f"    - {name}: {dtype} {nullable}{default_str}{pk_str}")

                    # Foreign keys
                    cursor.execute(f"PRAGMA foreign_key_list({table})")
                    fks = cursor.fetchall()
                    if fks:
                        result.append("  Foreign Keys:")
                        for fk in fks:
                            result.append(f"    - {fk[3]} -> {fk[2]}.{fk[4]}")

                    # Indexes
                    cursor.execute(f"PRAGMA index_list({table})")
                    indexes = cursor.fetchall()
                    if indexes:
                        result.append("  Indexes:")
                        for idx in indexes:
                            result.append(f"    - {idx[1]} (unique: {idx[2]})")

                    # Row count
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    result.append(f"  Rows: {count:,}")

                conn.close()

        except Exception as e:
            return f"Error during introspection: {e}"

        return "\n".join(result)

    def explain_query(
        self,
        query: str,
        db_type: str = "duckdb",
        connection_string: Optional[str] = None,
        analyze: bool = False,
    ) -> str:
        """Get query execution plan."""
        result = [f"=== Query Execution Plan ({db_type}) ===\n"]
        result.append(f"Query: {query[:200]}...\n" if len(query) > 200 else f"Query: {query}\n")

        try:
            explain_prefix = "EXPLAIN ANALYZE" if analyze else "EXPLAIN"

            if db_type == "duckdb":
                if self.duckdb is None:
                    return "Error: DuckDB not installed"

                plan = self.duckdb.execute(f"{explain_prefix} {query}").fetchdf()
                result.append("Execution Plan:")
                result.append(plan.to_string(index=False))

            elif db_type == "postgres":
                if not connection_string:
                    return "Error: connection_string required for PostgreSQL"

                import psycopg2

                conn = psycopg2.connect(connection_string)
                cursor = conn.cursor()

                cursor.execute(f"{explain_prefix} {query}")
                plan = cursor.fetchall()
                conn.close()

                result.append("Execution Plan:")
                for row in plan:
                    result.append(f"  {row[0]}")

            elif db_type == "sqlite":
                if not connection_string:
                    return "Error: connection_string (db path) required for SQLite"

                conn = sqlite3.connect(connection_string)
                cursor = conn.cursor()

                cursor.execute(f"EXPLAIN QUERY PLAN {query}")
                plan = cursor.fetchall()
                conn.close()

                result.append("Execution Plan:")
                for row in plan:
                    result.append(f"  {row}")

            # Add optimization hints
            result.append("\n## Optimization Hints")
            query_upper = query.upper()

            if "SELECT *" in query_upper:
                result.append("  - Consider selecting only needed columns instead of SELECT *")
            if "WHERE" not in query_upper and "SELECT" in query_upper:
                result.append("  - No WHERE clause - consider adding filters")
            if "JOIN" in query_upper and "INDEX" not in str(result):
                result.append("  - Joins detected - ensure join columns are indexed")
            if "LIKE '%'" in query_upper or "LIKE '%" in query:
                result.append("  - Leading wildcard in LIKE prevents index usage")
            if "ORDER BY" in query_upper and "LIMIT" not in query_upper:
                result.append("  - ORDER BY without LIMIT may be slow on large tables")

        except Exception as e:
            return f"Error explaining query: {e}"

        return "\n".join(result)

    def describe_csv(self, csv_path: str) -> str:
        """Describe the structure and statistics of a CSV."""
        try:
            if self.duckdb is None:
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

            output = [f"Analysis of: {path.name}\n"]

            count = self.duckdb.execute(f"SELECT COUNT(*) FROM '{csv_path}'").fetchone()[0]
            output.append(f"Total rows: {count:,}")

            schema = self.duckdb.execute(f"DESCRIBE SELECT * FROM '{csv_path}'").fetchdf()

            output.append(f"Columns: {len(schema)}\n")
            output.append("Structure:")

            for _, row in schema.iterrows():
                output.append(f"  - {row['column_name']}: {row['column_type']}")

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

            self.duckdb.execute(
                f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM '{csv_path}'"
            )

            count = self.duckdb.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

            return f"Imported: {count:,} rows to table '{table_name}'"

        except Exception as e:
            return f"Error importing CSV: {e}"

    def list_tables(
        self,
        db_type: str = "duckdb",
        connection_string: Optional[str] = None,
    ) -> str:
        """List tables in the database."""
        try:
            output = [f"=== Tables ({db_type}) ===\n"]

            if db_type == "duckdb":
                if self.duckdb is None:
                    return "Error: DuckDB not installed"

                tables = self.duckdb.execute("SHOW TABLES").fetchdf()

                if len(tables) == 0:
                    return "No tables in the database.\nUse import_csv_to_db to import data."

                for _, row in tables.iterrows():
                    table_name = row["name"]
                    try:
                        count = self.duckdb.execute(
                            f"SELECT COUNT(*) FROM {table_name}"
                        ).fetchone()[0]
                        output.append(f"  - {table_name} ({count:,} rows)")
                    except Exception:
                        output.append(f"  - {table_name}")

            elif db_type == "postgres":
                if not connection_string:
                    return "Error: connection_string required for PostgreSQL"

                import psycopg2

                conn = psycopg2.connect(connection_string)
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)

                for row in cursor.fetchall():
                    table_name = row[0]
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    output.append(f"  - {table_name} ({count:,} rows)")

                conn.close()

            elif db_type == "sqlite":
                if not connection_string:
                    return "Error: connection_string (db path) required for SQLite"

                conn = sqlite3.connect(connection_string)
                cursor = conn.cursor()

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")

                for row in cursor.fetchall():
                    table_name = row[0]
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    output.append(f"  - {table_name} ({count:,} rows)")

                conn.close()

            return "\n".join(output)

        except Exception as e:
            return f"Error listing tables: {e}"

    def describe_table(
        self,
        table_name: str,
        db_type: str = "duckdb",
        connection_string: Optional[str] = None,
    ) -> str:
        """Describe the structure of a table."""
        # Use introspect_schema with specific table
        return self.introspect_schema(db_type, connection_string, table_name)

    def get_table_relationships(
        self,
        table_name: str,
        db_type: str,
        connection_string: Optional[str] = None,
    ) -> str:
        """Get foreign key relationships for a table."""
        result = [f"=== Relationships for {table_name} ({db_type}) ===\n"]

        try:
            if db_type == "postgres":
                if not connection_string:
                    return "Error: connection_string required"

                import psycopg2

                conn = psycopg2.connect(connection_string)
                cursor = conn.cursor()

                # Outgoing FKs (this table references others)
                cursor.execute(
                    """
                    SELECT
                        kcu.column_name,
                        ccu.table_name AS foreign_table,
                        ccu.column_name AS foreign_column
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage ccu
                        ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                        AND tc.table_name = %s
                """,
                    (table_name,),
                )

                outgoing = cursor.fetchall()
                if outgoing:
                    result.append("## References (this table -> other tables)")
                    for fk in outgoing:
                        result.append(f"  {table_name}.{fk[0]} -> {fk[1]}.{fk[2]}")

                # Incoming FKs (other tables reference this)
                cursor.execute(
                    """
                    SELECT
                        tc.table_name,
                        kcu.column_name,
                        ccu.column_name AS referenced_column
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage ccu
                        ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                        AND ccu.table_name = %s
                """,
                    (table_name,),
                )

                incoming = cursor.fetchall()
                if incoming:
                    result.append("\n## Referenced by (other tables -> this table)")
                    for fk in incoming:
                        result.append(f"  {fk[0]}.{fk[1]} -> {table_name}.{fk[2]}")

                conn.close()

            elif db_type == "sqlite":
                if not connection_string:
                    return "Error: connection_string (db path) required"

                conn = sqlite3.connect(connection_string)
                cursor = conn.cursor()

                cursor.execute(f"PRAGMA foreign_key_list({table_name})")
                fks = cursor.fetchall()

                if fks:
                    result.append("## References (this table -> other tables)")
                    for fk in fks:
                        result.append(f"  {table_name}.{fk[3]} -> {fk[2]}.{fk[4]}")
                else:
                    result.append("No foreign key relationships found.")

                conn.close()

            elif db_type == "duckdb":
                result.append("DuckDB foreign key introspection not yet supported.")

            if len(result) == 1:
                result.append("No relationships found.")

        except Exception as e:
            return f"Error getting relationships: {e}"

        return "\n".join(result)

    def get_indexes(
        self,
        db_type: str,
        table_name: Optional[str] = None,
        connection_string: Optional[str] = None,
    ) -> str:
        """Get indexes for a table or database."""
        result = [f"=== Indexes ({db_type}) ===\n"]

        try:
            if db_type == "postgres":
                if not connection_string:
                    return "Error: connection_string required"

                import psycopg2

                conn = psycopg2.connect(connection_string)
                cursor = conn.cursor()

                query = """
                    SELECT
                        schemaname,
                        tablename,
                        indexname,
                        indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                """
                if table_name:
                    query += f" AND tablename = '{table_name}'"

                cursor.execute(query)

                for row in cursor.fetchall():
                    result.append(f"\n## {row[1]}.{row[2]}")
                    result.append(f"  {row[3][:100]}")

                conn.close()

            elif db_type == "sqlite":
                if not connection_string:
                    return "Error: connection_string (db path) required"

                conn = sqlite3.connect(connection_string)
                cursor = conn.cursor()

                if table_name:
                    cursor.execute(f"PRAGMA index_list({table_name})")
                    indexes = cursor.fetchall()
                    for idx in indexes:
                        result.append(f"  - {idx[1]} (unique: {idx[2]})")
                        cursor.execute(f"PRAGMA index_info({idx[1]})")
                        cols = cursor.fetchall()
                        for col in cols:
                            result.append(f"      Column: {col[2]}")
                else:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = cursor.fetchall()
                    for t in tables:
                        cursor.execute(f"PRAGMA index_list({t[0]})")
                        indexes = cursor.fetchall()
                        if indexes:
                            result.append(f"\n## {t[0]}")
                            for idx in indexes:
                                result.append(f"  - {idx[1]} (unique: {idx[2]})")

                conn.close()

            elif db_type == "duckdb":
                result.append("DuckDB index introspection not yet supported.")

        except Exception as e:
            return f"Error getting indexes: {e}"

        return "\n".join(result)

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

    def get_prompt(self) -> str:
        return """You are a database expert. Help users with:
- Writing and optimizing SQL queries
- Understanding database schemas and relationships
- Querying CSV files, SQLite, DuckDB, and PostgreSQL databases
- Analyzing query performance with EXPLAIN

Use introspect_schema to understand database structure.
Use explain_query to analyze query performance.
Use get_table_relationships to understand foreign keys.
Use get_indexes to see what's indexed.

For PostgreSQL, users need to provide a connection string like:
postgresql://user:password@localhost:5432/dbname
"""
