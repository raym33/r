"""
Skill de Calendario para R CLI.

Gestión de calendario 100% local usando SQLite.
Soporta eventos, recordatorios, tareas y exportación a iCal.

Todo offline, sin dependencias de Google Calendar o servicios en la nube.
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


@dataclass
class Event:
    """Representa un evento del calendario."""
    id: Optional[int] = None
    title: str = ""
    description: str = ""
    start_time: str = ""  # ISO format
    end_time: str = ""    # ISO format
    location: str = ""
    all_day: bool = False
    recurrence: str = ""  # none, daily, weekly, monthly, yearly
    reminder_minutes: int = 15
    category: str = "general"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Task:
    """Representa una tarea."""
    id: Optional[int] = None
    title: str = ""
    description: str = ""
    due_date: str = ""
    priority: int = 2  # 1=high, 2=medium, 3=low
    completed: bool = False
    category: str = "general"
    created_at: str = ""
    completed_at: str = ""


class CalendarSkill(Skill):
    """Skill para gestión de calendario local."""

    name = "calendar"
    description = "Gestiona calendario y tareas localmente con SQLite"

    CATEGORIES = ["general", "work", "personal", "health", "finance", "education", "social"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_path = Path(self.config.home_dir if hasattr(self.config, 'home_dir') else "~/.r-cli").expanduser() / "calendar.db"
        self._init_database()

    def _init_database(self):
        """Inicializa la base de datos SQLite."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Tabla de eventos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                location TEXT,
                all_day INTEGER DEFAULT 0,
                recurrence TEXT DEFAULT 'none',
                reminder_minutes INTEGER DEFAULT 15,
                category TEXT DEFAULT 'general',
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Tabla de tareas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                due_date TEXT,
                priority INTEGER DEFAULT 2,
                completed INTEGER DEFAULT 0,
                category TEXT DEFAULT 'general',
                created_at TEXT,
                completed_at TEXT
            )
        """)

        # Índices para búsquedas rápidas
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_start ON events(start_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed)")

        conn.commit()
        conn.close()

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="add_event",
                description="Añade un evento al calendario",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Título del evento"},
                        "start_time": {"type": "string", "description": "Fecha/hora inicio (YYYY-MM-DD HH:MM o YYYY-MM-DD)"},
                        "end_time": {"type": "string", "description": "Fecha/hora fin (opcional)"},
                        "description": {"type": "string", "description": "Descripción del evento"},
                        "location": {"type": "string", "description": "Ubicación"},
                        "category": {"type": "string", "enum": self.CATEGORIES},
                        "reminder_minutes": {"type": "integer", "description": "Minutos antes para recordatorio"},
                        "recurrence": {"type": "string", "enum": ["none", "daily", "weekly", "monthly", "yearly"]},
                    },
                    "required": ["title", "start_time"],
                },
                handler=self.add_event,
            ),
            Tool(
                name="list_events",
                description="Lista eventos del calendario",
                parameters={
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "Fecha específica (YYYY-MM-DD)"},
                        "start_date": {"type": "string", "description": "Inicio del rango"},
                        "end_date": {"type": "string", "description": "Fin del rango"},
                        "category": {"type": "string", "description": "Filtrar por categoría"},
                    },
                },
                handler=self.list_events,
            ),
            Tool(
                name="delete_event",
                description="Elimina un evento del calendario",
                parameters={
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "integer", "description": "ID del evento a eliminar"},
                    },
                    "required": ["event_id"],
                },
                handler=self.delete_event,
            ),
            Tool(
                name="add_task",
                description="Añade una tarea",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Título de la tarea"},
                        "due_date": {"type": "string", "description": "Fecha límite (YYYY-MM-DD)"},
                        "description": {"type": "string", "description": "Descripción"},
                        "priority": {"type": "integer", "enum": [1, 2, 3], "description": "1=alta, 2=media, 3=baja"},
                        "category": {"type": "string", "enum": self.CATEGORIES},
                    },
                    "required": ["title"],
                },
                handler=self.add_task,
            ),
            Tool(
                name="list_tasks",
                description="Lista tareas pendientes o completadas",
                parameters={
                    "type": "object",
                    "properties": {
                        "show_completed": {"type": "boolean", "description": "Mostrar tareas completadas"},
                        "category": {"type": "string", "description": "Filtrar por categoría"},
                        "priority": {"type": "integer", "description": "Filtrar por prioridad"},
                    },
                },
                handler=self.list_tasks,
            ),
            Tool(
                name="complete_task",
                description="Marca una tarea como completada",
                parameters={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer", "description": "ID de la tarea"},
                    },
                    "required": ["task_id"],
                },
                handler=self.complete_task,
            ),
            Tool(
                name="delete_task",
                description="Elimina una tarea",
                parameters={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "integer", "description": "ID de la tarea"},
                    },
                    "required": ["task_id"],
                },
                handler=self.delete_task,
            ),
            Tool(
                name="today_summary",
                description="Resumen de eventos y tareas de hoy",
                parameters={"type": "object", "properties": {}},
                handler=self.today_summary,
            ),
            Tool(
                name="week_summary",
                description="Resumen de la semana",
                parameters={"type": "object", "properties": {}},
                handler=self.week_summary,
            ),
            Tool(
                name="export_ical",
                description="Exporta eventos a formato iCal (.ics)",
                parameters={
                    "type": "object",
                    "properties": {
                        "output_path": {"type": "string", "description": "Ruta del archivo .ics"},
                        "start_date": {"type": "string", "description": "Fecha inicio (opcional)"},
                        "end_date": {"type": "string", "description": "Fecha fin (opcional)"},
                    },
                },
                handler=self.export_ical,
            ),
        ]

    def add_event(
        self,
        title: str,
        start_time: str,
        end_time: Optional[str] = None,
        description: str = "",
        location: str = "",
        category: str = "general",
        reminder_minutes: int = 15,
        recurrence: str = "none",
    ) -> str:
        """Añade un evento al calendario."""
        try:
            # Parsear y validar fecha
            start_dt = self._parse_datetime(start_time)
            if not start_dt:
                return f"Error: Formato de fecha inválido: {start_time}"

            end_dt = None
            if end_time:
                end_dt = self._parse_datetime(end_time)

            now = datetime.now().isoformat()
            all_day = len(start_time) <= 10  # Solo fecha, sin hora

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO events (title, description, start_time, end_time, location,
                                   all_day, recurrence, reminder_minutes, category, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                title, description, start_dt.isoformat(),
                end_dt.isoformat() if end_dt else None,
                location, all_day, recurrence, reminder_minutes, category, now, now
            ))

            event_id = cursor.lastrowid
            conn.commit()
            conn.close()

            formatted_date = start_dt.strftime("%A, %d %B %Y")
            if not all_day:
                formatted_date += f" a las {start_dt.strftime('%H:%M')}"

            return f"Evento creado (ID: {event_id})\n- {title}\n- {formatted_date}\n- Categoría: {category}"

        except Exception as e:
            return f"Error creando evento: {e}"

    def list_events(
        self,
        date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
    ) -> str:
        """Lista eventos del calendario."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM events WHERE 1=1"
            params = []

            if date:
                query += " AND date(start_time) = date(?)"
                params.append(date)
            elif start_date and end_date:
                query += " AND date(start_time) BETWEEN date(?) AND date(?)"
                params.extend([start_date, end_date])
            elif start_date:
                query += " AND date(start_time) >= date(?)"
                params.append(start_date)

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " ORDER BY start_time ASC"

            cursor.execute(query, params)
            events = cursor.fetchall()
            conn.close()

            if not events:
                return "No hay eventos para mostrar."

            result = ["Eventos:\n"]
            for event in events:
                start_dt = datetime.fromisoformat(event["start_time"])
                date_str = start_dt.strftime("%d/%m/%Y")
                time_str = start_dt.strftime("%H:%M") if not event["all_day"] else "Todo el día"

                result.append(f"  [{event['id']}] {event['title']}")
                result.append(f"      {date_str} - {time_str}")
                if event["location"]:
                    result.append(f"      Lugar: {event['location']}")
                result.append(f"      Categoría: {event['category']}")
                result.append("")

            return "\n".join(result)

        except Exception as e:
            return f"Error listando eventos: {e}"

    def delete_event(self, event_id: int) -> str:
        """Elimina un evento."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("SELECT title FROM events WHERE id = ?", (event_id,))
            event = cursor.fetchone()

            if not event:
                conn.close()
                return f"Error: Evento {event_id} no encontrado."

            cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
            conn.commit()
            conn.close()

            return f"Evento eliminado: {event[0]}"

        except Exception as e:
            return f"Error eliminando evento: {e}"

    def add_task(
        self,
        title: str,
        due_date: Optional[str] = None,
        description: str = "",
        priority: int = 2,
        category: str = "general",
    ) -> str:
        """Añade una tarea."""
        try:
            now = datetime.now().isoformat()

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO tasks (title, description, due_date, priority, category, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, description, due_date, priority, category, now))

            task_id = cursor.lastrowid
            conn.commit()
            conn.close()

            priority_labels = {1: "Alta", 2: "Media", 3: "Baja"}
            result = f"Tarea creada (ID: {task_id})\n- {title}\n- Prioridad: {priority_labels.get(priority, 'Media')}"
            if due_date:
                result += f"\n- Fecha límite: {due_date}"

            return result

        except Exception as e:
            return f"Error creando tarea: {e}"

    def list_tasks(
        self,
        show_completed: bool = False,
        category: Optional[str] = None,
        priority: Optional[int] = None,
    ) -> str:
        """Lista tareas."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM tasks WHERE 1=1"
            params = []

            if not show_completed:
                query += " AND completed = 0"

            if category:
                query += " AND category = ?"
                params.append(category)

            if priority:
                query += " AND priority = ?"
                params.append(priority)

            query += " ORDER BY priority ASC, due_date ASC"

            cursor.execute(query, params)
            tasks = cursor.fetchall()
            conn.close()

            if not tasks:
                return "No hay tareas pendientes."

            priority_icons = {1: "[!]", 2: "[-]", 3: "[ ]"}
            result = ["Tareas:\n"]

            for task in tasks:
                icon = priority_icons.get(task["priority"], "[-]")
                status = "[x]" if task["completed"] else icon

                result.append(f"  {status} [{task['id']}] {task['title']}")
                if task["due_date"]:
                    result.append(f"      Fecha límite: {task['due_date']}")
                result.append(f"      Categoría: {task['category']}")
                result.append("")

            return "\n".join(result)

        except Exception as e:
            return f"Error listando tareas: {e}"

    def complete_task(self, task_id: int) -> str:
        """Marca una tarea como completada."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("SELECT title, completed FROM tasks WHERE id = ?", (task_id,))
            task = cursor.fetchone()

            if not task:
                conn.close()
                return f"Error: Tarea {task_id} no encontrada."

            if task[1]:
                conn.close()
                return f"La tarea '{task[0]}' ya está completada."

            now = datetime.now().isoformat()
            cursor.execute(
                "UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ?",
                (now, task_id)
            )
            conn.commit()
            conn.close()

            return f"Tarea completada: {task[0]}"

        except Exception as e:
            return f"Error completando tarea: {e}"

    def delete_task(self, task_id: int) -> str:
        """Elimina una tarea."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute("SELECT title FROM tasks WHERE id = ?", (task_id,))
            task = cursor.fetchone()

            if not task:
                conn.close()
                return f"Error: Tarea {task_id} no encontrada."

            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            conn.close()

            return f"Tarea eliminada: {task[0]}"

        except Exception as e:
            return f"Error eliminando tarea: {e}"

    def today_summary(self) -> str:
        """Resumen de hoy."""
        try:
            today = datetime.now().strftime("%Y-%m-%d")

            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Eventos de hoy
            cursor.execute(
                "SELECT * FROM events WHERE date(start_time) = date(?) ORDER BY start_time",
                (today,)
            )
            events = cursor.fetchall()

            # Tareas pendientes con fecha de hoy o vencidas
            cursor.execute("""
                SELECT * FROM tasks
                WHERE completed = 0 AND (due_date IS NULL OR date(due_date) <= date(?))
                ORDER BY priority, due_date
            """, (today,))
            tasks = cursor.fetchall()

            conn.close()

            result = [f"Resumen de hoy ({datetime.now().strftime('%A, %d %B %Y')}):\n"]

            # Eventos
            result.append("EVENTOS:")
            if events:
                for event in events:
                    start_dt = datetime.fromisoformat(event["start_time"])
                    time_str = start_dt.strftime("%H:%M") if not event["all_day"] else "Todo el día"
                    result.append(f"  - {time_str}: {event['title']}")
            else:
                result.append("  (Sin eventos)")

            result.append("")

            # Tareas
            result.append("TAREAS PENDIENTES:")
            if tasks:
                priority_icons = {1: "[!]", 2: "[-]", 3: "[ ]"}
                for task in tasks:
                    icon = priority_icons.get(task["priority"], "[-]")
                    overdue = ""
                    if task["due_date"] and task["due_date"] < today:
                        overdue = " (VENCIDA)"
                    result.append(f"  {icon} {task['title']}{overdue}")
            else:
                result.append("  (Sin tareas pendientes)")

            return "\n".join(result)

        except Exception as e:
            return f"Error generando resumen: {e}"

    def week_summary(self) -> str:
        """Resumen de la semana."""
        try:
            today = datetime.now()
            # Inicio de semana (lunes)
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)

            start_str = start_of_week.strftime("%Y-%m-%d")
            end_str = end_of_week.strftime("%Y-%m-%d")

            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Eventos de la semana
            cursor.execute("""
                SELECT * FROM events
                WHERE date(start_time) BETWEEN date(?) AND date(?)
                ORDER BY start_time
            """, (start_str, end_str))
            events = cursor.fetchall()

            # Tareas de la semana
            cursor.execute("""
                SELECT * FROM tasks
                WHERE completed = 0 AND date(due_date) BETWEEN date(?) AND date(?)
                ORDER BY due_date, priority
            """, (start_str, end_str))
            tasks = cursor.fetchall()

            conn.close()

            result = [f"Resumen de la semana ({start_of_week.strftime('%d/%m')} - {end_of_week.strftime('%d/%m/%Y')}):\n"]

            # Organizar eventos por día
            days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            events_by_day = {i: [] for i in range(7)}

            for event in events:
                start_dt = datetime.fromisoformat(event["start_time"])
                day_idx = start_dt.weekday()
                events_by_day[day_idx].append(event)

            for day_idx, day_name in enumerate(days):
                day_date = start_of_week + timedelta(days=day_idx)
                is_today = day_date.date() == today.date()
                marker = " <-- HOY" if is_today else ""

                result.append(f"{day_name} {day_date.strftime('%d/%m')}{marker}:")

                day_events = events_by_day[day_idx]
                if day_events:
                    for event in day_events:
                        start_dt = datetime.fromisoformat(event["start_time"])
                        time_str = start_dt.strftime("%H:%M") if not event["all_day"] else "Todo el día"
                        result.append(f"  - {time_str}: {event['title']}")
                else:
                    result.append("  (Sin eventos)")
                result.append("")

            # Tareas de la semana
            result.append("TAREAS DE LA SEMANA:")
            if tasks:
                for task in tasks:
                    result.append(f"  - [{task['due_date']}] {task['title']}")
            else:
                result.append("  (Sin tareas programadas)")

            return "\n".join(result)

        except Exception as e:
            return f"Error generando resumen semanal: {e}"

    def export_ical(
        self,
        output_path: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> str:
        """Exporta eventos a formato iCal."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM events WHERE 1=1"
            params = []

            if start_date:
                query += " AND date(start_time) >= date(?)"
                params.append(start_date)
            if end_date:
                query += " AND date(start_time) <= date(?)"
                params.append(end_date)

            cursor.execute(query, params)
            events = cursor.fetchall()
            conn.close()

            if not events:
                return "No hay eventos para exportar."

            # Generar iCal
            ical_lines = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//R CLI//Calendar//EN",
                "CALSCALE:GREGORIAN",
                "METHOD:PUBLISH",
            ]

            for event in events:
                start_dt = datetime.fromisoformat(event["start_time"])

                ical_lines.append("BEGIN:VEVENT")
                ical_lines.append(f"UID:{event['id']}@r-cli")
                ical_lines.append(f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}")

                if event["all_day"]:
                    ical_lines.append(f"DTSTART;VALUE=DATE:{start_dt.strftime('%Y%m%d')}")
                else:
                    ical_lines.append(f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}")

                if event["end_time"]:
                    end_dt = datetime.fromisoformat(event["end_time"])
                    if event["all_day"]:
                        ical_lines.append(f"DTEND;VALUE=DATE:{end_dt.strftime('%Y%m%d')}")
                    else:
                        ical_lines.append(f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}")

                ical_lines.append(f"SUMMARY:{event['title']}")

                if event["description"]:
                    ical_lines.append(f"DESCRIPTION:{event['description']}")
                if event["location"]:
                    ical_lines.append(f"LOCATION:{event['location']}")

                ical_lines.append(f"CATEGORIES:{event['category'].upper()}")
                ical_lines.append("END:VEVENT")

            ical_lines.append("END:VCALENDAR")

            # Guardar archivo
            if output_path:
                out_path = Path(output_path)
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_path = Path(self.output_dir) / f"calendar_{timestamp}.ics"

            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("\n".join(ical_lines))

            return f"Calendario exportado: {out_path}\n{len(events)} eventos exportados."

        except Exception as e:
            return f"Error exportando calendario: {e}"

    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """Parsea string a datetime."""
        formats = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
        return None

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        action = kwargs.get("action", "today")

        if action == "today":
            return self.today_summary()
        elif action == "week":
            return self.week_summary()
        elif action == "add":
            return self.add_event(
                title=kwargs.get("title", "Evento"),
                start_time=kwargs.get("date", datetime.now().strftime("%Y-%m-%d")),
                description=kwargs.get("description", ""),
            )
        elif action == "task":
            return self.add_task(
                title=kwargs.get("title", "Tarea"),
                due_date=kwargs.get("due"),
                priority=kwargs.get("priority", 2),
            )
        elif action == "export":
            return self.export_ical(kwargs.get("output"))
        else:
            return self.today_summary()
