"""
Skill de SQL para R CLI.

Funcionalidades:
- Text-to-SQL: Convertir lenguaje natural a consultas SQL
- Ejecutar queries en bases de datos locales (SQLite, DuckDB)
- Analizar CSVs con SQL
- Crear y gestionar bases de datos
"""

import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class SQLSkill(Skill):
    """Skill para consultas SQL en lenguaje natural."""

    name = "sql"
    description = "Consultas SQL sobre bases de datos locales y CSVs"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._duckdb_conn = None

    @property
    def duckdb(self):
        """Lazy loading de DuckDB."""
        if self._duckdb_conn is None:
            try:
                import duckdb

                # Conexión en memoria con persistencia opcional
                db_path = os.path.join(
                    os.path.expanduser(self.config.home_dir), "r_cli.duckdb"
                )
                self._duckdb_conn = duckdb.connect(db_path)
            except ImportError:
                return None
        return self._duckdb_conn

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="query_csv",
                description="Ejecuta una consulta SQL sobre un archivo CSV",
                parameters={
                    "type": "object",
                    "properties": {
                        "csv_path": {
                            "type": "string",
                            "description": "Ruta al archivo CSV",
                        },
                        "query": {
                            "type": "string",
                            "description": "Consulta SQL (usa 'data' como nombre de tabla)",
                        },
                    },
                    "required": ["csv_path", "query"],
                },
                handler=self.query_csv,
            ),
            Tool(
                name="query_database",
                description="Ejecuta una consulta SQL en la base de datos local",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Consulta SQL a ejecutar",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Límite de filas a retornar (default: 100)",
                        },
                    },
                    "required": ["query"],
                },
                handler=self.query_database,
            ),
            Tool(
                name="describe_csv",
                description="Muestra la estructura y estadísticas de un CSV",
                parameters={
                    "type": "object",
                    "properties": {
                        "csv_path": {
                            "type": "string",
                            "description": "Ruta al archivo CSV",
                        },
                    },
                    "required": ["csv_path"],
                },
                handler=self.describe_csv,
            ),
            Tool(
                name="import_csv_to_db",
                description="Importa un CSV a una tabla en la base de datos local",
                parameters={
                    "type": "object",
                    "properties": {
                        "csv_path": {
                            "type": "string",
                            "description": "Ruta al archivo CSV",
                        },
                        "table_name": {
                            "type": "string",
                            "description": "Nombre de la tabla a crear",
                        },
                    },
                    "required": ["csv_path", "table_name"],
                },
                handler=self.import_csv_to_db,
            ),
            Tool(
                name="list_tables",
                description="Lista las tablas disponibles en la base de datos",
                parameters={"type": "object", "properties": {}},
                handler=self.list_tables,
            ),
            Tool(
                name="describe_table",
                description="Muestra la estructura de una tabla",
                parameters={
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Nombre de la tabla",
                        },
                    },
                    "required": ["table_name"],
                },
                handler=self.describe_table,
            ),
        ]

    def query_csv(self, csv_path: str, query: str) -> str:
        """Ejecuta SQL sobre un CSV usando DuckDB."""
        try:
            if self.duckdb is None:
                return "Error: DuckDB no instalado. Ejecuta: pip install duckdb"

            path = Path(csv_path)
            if not path.exists():
                return f"Error: CSV no encontrado: {csv_path}"

            # Reemplazar 'data' con la ruta real del CSV
            actual_query = query.replace("data", f"'{csv_path}'")
            actual_query = actual_query.replace("FROM csv", f"FROM '{csv_path}'")

            # Si la query no tiene FROM con path, agregar
            if "FROM" not in actual_query.upper() or csv_path not in actual_query:
                # Intentar detectar el nombre de tabla usado
                if " data" in actual_query.lower() or "from data" in actual_query.lower():
                    actual_query = actual_query.replace(" data", f" '{csv_path}'")

            result = self.duckdb.execute(actual_query).fetchdf()

            # Formatear resultado
            if len(result) == 0:
                return "Query ejecutada. Sin resultados."

            # Limitar filas para display
            display_df = result.head(50)

            output = [f"📊 Resultados ({len(result)} filas):\n"]
            output.append(display_df.to_string(index=False))

            if len(result) > 50:
                output.append(f"\n... (mostrando 50 de {len(result)} filas)")

            return "\n".join(output)

        except Exception as e:
            return f"Error ejecutando query: {e}"

    def query_database(self, query: str, limit: int = 100) -> str:
        """Ejecuta SQL en la base de datos local."""
        try:
            if self.duckdb is None:
                return "Error: DuckDB no instalado. Ejecuta: pip install duckdb"

            # Agregar LIMIT si no está presente y es SELECT
            if query.strip().upper().startswith("SELECT") and "LIMIT" not in query.upper():
                query = f"{query} LIMIT {limit}"

            result = self.duckdb.execute(query).fetchdf()

            if len(result) == 0:
                if query.strip().upper().startswith("SELECT"):
                    return "Query ejecutada. Sin resultados."
                else:
                    return "✅ Query ejecutada exitosamente."

            output = [f"📊 Resultados ({len(result)} filas):\n"]
            output.append(result.to_string(index=False))

            return "\n".join(output)

        except Exception as e:
            return f"Error ejecutando query: {e}"

    def describe_csv(self, csv_path: str) -> str:
        """Describe la estructura y estadísticas de un CSV."""
        try:
            if self.duckdb is None:
                # Fallback a pandas
                try:
                    import pandas as pd

                    df = pd.read_csv(csv_path, nrows=1000)

                    output = [f"📄 Análisis de: {Path(csv_path).name}\n"]
                    output.append(f"Filas (muestra): {len(df)}")
                    output.append(f"Columnas: {len(df.columns)}\n")

                    output.append("Columnas:")
                    for col in df.columns:
                        dtype = str(df[col].dtype)
                        nulls = df[col].isnull().sum()
                        output.append(f"  • {col}: {dtype} ({nulls} nulos)")

                    return "\n".join(output)

                except ImportError:
                    return "Error: Necesitas DuckDB o Pandas instalado"

            path = Path(csv_path)
            if not path.exists():
                return f"Error: CSV no encontrado: {csv_path}"

            # Usar DuckDB para análisis
            output = [f"📄 Análisis de: {path.name}\n"]

            # Contar filas
            count = self.duckdb.execute(f"SELECT COUNT(*) FROM '{csv_path}'").fetchone()[0]
            output.append(f"Total filas: {count:,}")

            # Obtener schema
            schema = self.duckdb.execute(f"DESCRIBE SELECT * FROM '{csv_path}'").fetchdf()

            output.append(f"Columnas: {len(schema)}\n")
            output.append("Estructura:")

            for _, row in schema.iterrows():
                output.append(f"  • {row['column_name']}: {row['column_type']}")

            # Estadísticas básicas para columnas numéricas
            output.append("\nEstadísticas (columnas numéricas):")
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
            return f"Error describiendo CSV: {e}"

    def import_csv_to_db(self, csv_path: str, table_name: str) -> str:
        """Importa un CSV a una tabla persistente."""
        try:
            if self.duckdb is None:
                return "Error: DuckDB no instalado"

            path = Path(csv_path)
            if not path.exists():
                return f"Error: CSV no encontrado: {csv_path}"

            # Crear tabla desde CSV
            self.duckdb.execute(
                f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM '{csv_path}'"
            )

            # Contar filas importadas
            count = self.duckdb.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[
                0
            ]

            return f"✅ Importado: {count:,} filas a tabla '{table_name}'"

        except Exception as e:
            return f"Error importando CSV: {e}"

    def list_tables(self) -> str:
        """Lista las tablas en la base de datos."""
        try:
            if self.duckdb is None:
                return "Error: DuckDB no instalado"

            tables = self.duckdb.execute("SHOW TABLES").fetchdf()

            if len(tables) == 0:
                return "No hay tablas en la base de datos.\nUsa import_csv_to_db para importar datos."

            output = ["📊 Tablas disponibles:\n"]

            for _, row in tables.iterrows():
                table_name = row["name"]
                try:
                    count = self.duckdb.execute(
                        f"SELECT COUNT(*) FROM {table_name}"
                    ).fetchone()[0]
                    output.append(f"  • {table_name} ({count:,} filas)")
                except Exception:
                    output.append(f"  • {table_name}")

            return "\n".join(output)

        except Exception as e:
            return f"Error listando tablas: {e}"

    def describe_table(self, table_name: str) -> str:
        """Describe la estructura de una tabla."""
        try:
            if self.duckdb is None:
                return "Error: DuckDB no instalado"

            # Verificar que existe
            tables = self.duckdb.execute("SHOW TABLES").fetchdf()
            if table_name not in tables["name"].values:
                return f"Error: Tabla no encontrada: {table_name}"

            schema = self.duckdb.execute(f"DESCRIBE {table_name}").fetchdf()

            output = [f"📊 Estructura de: {table_name}\n"]

            for _, row in schema.iterrows():
                nullable = "NULL" if row["null"] == "YES" else "NOT NULL"
                output.append(f"  • {row['column_name']}: {row['column_type']} {nullable}")

            # Contar filas
            count = self.duckdb.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[
                0
            ]
            output.append(f"\nTotal filas: {count:,}")

            # Preview
            preview = self.duckdb.execute(f"SELECT * FROM {table_name} LIMIT 5").fetchdf()
            output.append(f"\nPreview (5 filas):")
            output.append(preview.to_string(index=False))

            return "\n".join(output)

        except Exception as e:
            return f"Error describiendo tabla: {e}"

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        query = kwargs.get("query", "")
        csv_path = kwargs.get("csv")

        if csv_path:
            return self.query_csv(csv_path, query)
        elif query:
            return self.query_database(query)
        else:
            return self.list_tables()
