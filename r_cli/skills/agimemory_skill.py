"""
AGI Memory Skill - Persistent AI memory system for R CLI.

Based on QuixiAI/agi-memory architecture.
Provides persistent memory with semantic search capabilities.

Memory Types:
- WORKING: Active processing context
- EPISODIC: Event-based memories with temporal context
- SEMANTIC: Facts and knowledge with confidence scores
- PROCEDURAL: Step-by-step task memories
- STRATEGIC: Patterns and long-term goals
"""

import json
import os
import sqlite3
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.config import Config
from r_cli.core.llm import Tool


class MemoryType(str, Enum):
    """Types of memories the system can store."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    STRATEGIC = "strategic"


class AGIMemorySkill(Skill):
    """
    Persistent AGI memory system.

    Provides long-term memory storage with:
    - Multiple memory types
    - Importance scoring
    - Memory decay
    - Semantic search (via embeddings when available)
    - Identity persistence
    """

    name = "agimemory"
    description = "Persistent AI memory system with semantic search and identity persistence"

    def __init__(self, config: Optional[Config] = None):
        super().__init__(config)
        self.db_path = Path(os.path.expanduser("~/.r-cli/agi_memory.db"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

        # Identity configuration
        self.identity = {
            "name": "R",
            "version": "0.3.2",
            "personality": "helpful, direct, technical",
            "created_at": datetime.now().isoformat(),
        }

    def _init_database(self):
        """Initialize SQLite database with memory tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Main memories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                importance REAL DEFAULT 0.5,
                confidence REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                decay_rate REAL DEFAULT 0.01,
                metadata TEXT,
                embedding BLOB
            )
        """)

        # Identity/beliefs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS beliefs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                belief TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Relationships between memories
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER,
                target_id INTEGER,
                relationship TEXT,
                strength REAL DEFAULT 0.5,
                FOREIGN KEY (source_id) REFERENCES memories(id),
                FOREIGN KEY (target_id) REFERENCES memories(id)
            )
        """)

        # Conversation history for episodic memory
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Goals and intentions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal TEXT NOT NULL,
                priority REAL DEFAULT 0.5,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        # Create indexes for faster search
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id)"
        )

        conn.commit()
        conn.close()

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="memory_store",
                description="Store a new memory. Use this to remember important information, facts, or events.",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The content to remember",
                        },
                        "memory_type": {
                            "type": "string",
                            "enum": ["working", "episodic", "semantic", "procedural", "strategic"],
                            "description": "Type of memory (default: semantic)",
                        },
                        "importance": {
                            "type": "number",
                            "description": "Importance score 0-1 (default: 0.5)",
                        },
                    },
                    "required": ["content"],
                },
                handler=self.store_memory,
            ),
            Tool(
                name="memory_recall",
                description="Recall memories related to a query. Use this to remember past information.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What to search for in memory",
                        },
                        "memory_type": {
                            "type": "string",
                            "enum": [
                                "working",
                                "episodic",
                                "semantic",
                                "procedural",
                                "strategic",
                                "all",
                            ],
                            "description": "Filter by memory type (default: all)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum memories to return (default: 5)",
                        },
                    },
                    "required": ["query"],
                },
                handler=self.recall_memory,
            ),
            Tool(
                name="memory_forget",
                description="Forget a specific memory by ID",
                parameters={
                    "type": "object",
                    "properties": {
                        "memory_id": {
                            "type": "integer",
                            "description": "ID of memory to forget",
                        },
                    },
                    "required": ["memory_id"],
                },
                handler=self.forget_memory,
            ),
            Tool(
                name="memory_stats",
                description="Get statistics about stored memories",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.memory_stats,
            ),
            Tool(
                name="belief_add",
                description="Add or update a belief/preference",
                parameters={
                    "type": "object",
                    "properties": {
                        "belief": {
                            "type": "string",
                            "description": "The belief or preference to store",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence level 0-1 (default: 0.5)",
                        },
                    },
                    "required": ["belief"],
                },
                handler=self.add_belief,
            ),
            Tool(
                name="belief_list",
                description="List current beliefs and preferences",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.list_beliefs,
            ),
            Tool(
                name="goal_add",
                description="Add a new goal or intention",
                parameters={
                    "type": "object",
                    "properties": {
                        "goal": {
                            "type": "string",
                            "description": "The goal to add",
                        },
                        "priority": {
                            "type": "number",
                            "description": "Priority 0-1 (default: 0.5)",
                        },
                    },
                    "required": ["goal"],
                },
                handler=self.add_goal,
            ),
            Tool(
                name="goal_list",
                description="List active goals",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.list_goals,
            ),
            Tool(
                name="identity_info",
                description="Get information about my identity and self",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.get_identity,
            ),
            Tool(
                name="conversation_log",
                description="Log a conversation message for episodic memory",
                parameters={
                    "type": "object",
                    "properties": {
                        "role": {
                            "type": "string",
                            "description": "Role: user or assistant",
                        },
                        "content": {
                            "type": "string",
                            "description": "Message content",
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Session identifier (optional)",
                        },
                    },
                    "required": ["role", "content"],
                },
                handler=self.log_conversation,
            ),
        ]

    def store_memory(
        self,
        content: str,
        memory_type: str = "semantic",
        importance: float = 0.5,
        metadata: dict | None = None,
    ) -> str:
        """Store a new memory."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO memories (content, memory_type, importance, metadata)
            VALUES (?, ?, ?, ?)
            """,
            (content, memory_type, importance, json.dumps(metadata) if metadata else None),
        )

        memory_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return f"Memory stored (ID: {memory_id}, type: {memory_type}, importance: {importance})"

    def recall_memory(
        self,
        query: str,
        memory_type: str = "all",
        limit: int = 5,
    ) -> str:
        """Recall memories matching a query."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Simple text search (in production, use vector similarity)
        if memory_type == "all":
            cursor.execute(
                """
                SELECT id, content, memory_type, importance, created_at
                FROM memories
                WHERE content LIKE ?
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
                """,
                (f"%{query}%", limit),
            )
        else:
            cursor.execute(
                """
                SELECT id, content, memory_type, importance, created_at
                FROM memories
                WHERE content LIKE ? AND memory_type = ?
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
                """,
                (f"%{query}%", memory_type, limit),
            )

        memories = cursor.fetchall()

        # Update access count
        for mem in memories:
            cursor.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP WHERE id = ?",
                (mem[0],),
            )

        conn.commit()
        conn.close()

        if not memories:
            return f"No memories found for: {query}"

        result = f"Found {len(memories)} memories:\n\n"
        for mem in memories:
            result += f"[{mem[0]}] ({mem[2]}, importance: {mem[3]:.2f})\n"
            result += f"  {mem[1]}\n"
            result += f"  Created: {mem[4]}\n\n"

        return result

    def forget_memory(self, memory_id: int) -> str:
        """Delete a memory by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

        if cursor.rowcount > 0:
            conn.commit()
            conn.close()
            return f"Memory {memory_id} forgotten"
        else:
            conn.close()
            return f"Memory {memory_id} not found"

    def memory_stats(self) -> str:
        """Get memory statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total memories by type
        cursor.execute(
            """
            SELECT memory_type, COUNT(*), AVG(importance)
            FROM memories
            GROUP BY memory_type
            """
        )
        type_stats = cursor.fetchall()

        # Total counts
        cursor.execute("SELECT COUNT(*) FROM memories")
        total_memories = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM beliefs")
        total_beliefs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM goals WHERE status = 'active'")
        active_goals = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM conversations")
        conversation_msgs = cursor.fetchone()[0]

        conn.close()

        result = "=== AGI Memory Statistics ===\n\n"
        result += f"Total memories: {total_memories}\n"
        result += f"Beliefs: {total_beliefs}\n"
        result += f"Active goals: {active_goals}\n"
        result += f"Conversation messages: {conversation_msgs}\n\n"

        result += "By type:\n"
        for stat in type_stats:
            result += f"  {stat[0]}: {stat[1]} (avg importance: {stat[2]:.2f})\n"

        return result

    def add_belief(self, belief: str, confidence: float = 0.5, source: str | None = None) -> str:
        """Add or update a belief."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO beliefs (belief, confidence, source)
            VALUES (?, ?, ?)
            """,
            (belief, confidence, source),
        )

        belief_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return f"Belief added (ID: {belief_id}, confidence: {confidence})"

    def list_beliefs(self) -> str:
        """List all beliefs."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, belief, confidence, source, created_at
            FROM beliefs
            ORDER BY confidence DESC
            """
        )
        beliefs = cursor.fetchall()
        conn.close()

        if not beliefs:
            return "No beliefs stored yet."

        result = "=== Current Beliefs ===\n\n"
        for b in beliefs:
            result += f"[{b[0]}] (confidence: {b[2]:.2f})\n"
            result += f"  {b[1]}\n"
            if b[3]:
                result += f"  Source: {b[3]}\n"
            result += "\n"

        return result

    def add_goal(self, goal: str, priority: float = 0.5) -> str:
        """Add a new goal."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO goals (goal, priority)
            VALUES (?, ?)
            """,
            (goal, priority),
        )

        goal_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return f"Goal added (ID: {goal_id}, priority: {priority})"

    def list_goals(self) -> str:
        """List active goals."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, goal, priority, status, created_at
            FROM goals
            WHERE status = 'active'
            ORDER BY priority DESC
            """
        )
        goals = cursor.fetchall()
        conn.close()

        if not goals:
            return "No active goals."

        result = "=== Active Goals ===\n\n"
        for g in goals:
            result += f"[{g[0]}] (priority: {g[2]:.2f})\n"
            result += f"  {g[1]}\n"
            result += f"  Created: {g[4]}\n\n"

        return result

    def get_identity(self) -> str:
        """Get identity information."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM memories")
        total_memories = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM beliefs")
        total_beliefs = cursor.fetchone()[0]

        cursor.execute("SELECT MIN(created_at) FROM memories")
        first_memory = cursor.fetchone()[0]

        conn.close()

        result = "=== My Identity ===\n\n"
        result += f"Name: {self.identity['name']}\n"
        result += f"Version: {self.identity['version']}\n"
        result += f"Personality: {self.identity['personality']}\n"
        result += "\nMemory:\n"
        result += f"  Total memories: {total_memories}\n"
        result += f"  Total beliefs: {total_beliefs}\n"
        if first_memory:
            result += f"  First memory: {first_memory}\n"

        return result

    def log_conversation(
        self,
        role: str,
        content: str,
        session_id: str | None = None,
    ) -> str:
        """Log a conversation message."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if not session_id:
            session_id = datetime.now().strftime("%Y%m%d")

        cursor.execute(
            """
            INSERT INTO conversations (session_id, role, content)
            VALUES (?, ?, ?)
            """,
            (session_id, role, content),
        )

        conn.commit()
        conn.close()

        return f"Conversation logged (session: {session_id})"

    def execute(self, **kwargs) -> str:
        """Direct execution."""
        action = kwargs.get("action", "stats")

        if action == "stats":
            return self.memory_stats()
        elif action == "recall":
            return self.recall_memory(kwargs.get("query", ""))
        elif action == "store":
            return self.store_memory(
                kwargs.get("content", ""),
                kwargs.get("type", "semantic"),
                kwargs.get("importance", 0.5),
            )
        else:
            return f"Unknown action: {action}"
