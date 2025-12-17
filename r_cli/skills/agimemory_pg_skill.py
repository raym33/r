"""
AGI Memory Skill (PostgreSQL + pgvector version).

Enhanced persistent AI memory with semantic search via embeddings.
Requires PostgreSQL with pgvector extension.

Features:
- Vector similarity search for semantic memory recall
- Graph-like memory relationships
- Emotional state tracking
- Memory consolidation and decay
"""

import json
import os
from datetime import datetime
from enum import Enum
from typing import Optional

import numpy as np

from r_cli.core.agent import Skill
from r_cli.core.config import Config
from r_cli.core.llm import Tool

# Optional imports
try:
    import psycopg
    from psycopg.rows import dict_row

    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False

try:
    from sentence_transformers import SentenceTransformer

    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False


class MemoryType(str, Enum):
    """Types of memories."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    STRATEGIC = "strategic"


class AGIMemoryPGSkill(Skill):
    """
    Advanced AGI Memory with PostgreSQL + pgvector.

    Provides semantic search through vector embeddings.
    """

    name = "agimemory_pg"
    description = "Advanced persistent AI memory with semantic search (PostgreSQL + pgvector)"

    # Default connection settings
    DEFAULT_DSN = "postgresql://rcli:rcli_memory_2024@localhost:5433/agi_memory"

    def __init__(self, config: Optional[Config] = None):
        super().__init__(config)

        # Database connection
        self.dsn = os.getenv("R_MEMORY_DSN", self.DEFAULT_DSN)
        self._conn = None

        # Embedding model (lazy loaded)
        self._embedder = None
        self.embedding_dim = 384  # all-MiniLM-L6-v2

        # Check dependencies
        if not HAS_PSYCOPG:
            print("[agimemory_pg] Warning: psycopg not installed. Run: pip install psycopg[binary]")

    @property
    def conn(self):
        """Lazy database connection."""
        if self._conn is None or self._conn.closed:
            if not HAS_PSYCOPG:
                raise ImportError("psycopg not installed. Run: pip install psycopg[binary]")
            self._conn = psycopg.connect(self.dsn, row_factory=dict_row)
        return self._conn

    @property
    def embedder(self):
        """Lazy load embedding model."""
        if self._embedder is None:
            if not HAS_EMBEDDINGS:
                return None
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
        return self._embedder

    def get_embedding(self, text: str) -> list[float] | None:
        """Generate embedding for text."""
        if self.embedder is None:
            return None
        embedding = self.embedder.encode(text)
        return embedding.tolist()

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="pg_memory_store",
                description="Store a memory with semantic embedding for later retrieval",
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
                            "description": "Type of memory",
                        },
                        "importance": {
                            "type": "number",
                            "description": "Importance 0-1",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Tags for categorization",
                        },
                    },
                    "required": ["content"],
                },
                handler=self.store_memory,
            ),
            Tool(
                name="pg_memory_search",
                description="Semantic search for memories. Finds memories similar in meaning to the query.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What to search for (semantic similarity)",
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
                            "description": "Filter by type",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 5)",
                        },
                        "min_similarity": {
                            "type": "number",
                            "description": "Minimum similarity threshold 0-1 (default 0.5)",
                        },
                    },
                    "required": ["query"],
                },
                handler=self.search_memory,
            ),
            Tool(
                name="pg_memory_link",
                description="Create a relationship between two memories",
                parameters={
                    "type": "object",
                    "properties": {
                        "source_id": {"type": "integer", "description": "Source memory ID"},
                        "target_id": {"type": "integer", "description": "Target memory ID"},
                        "relationship": {
                            "type": "string",
                            "description": "Type of relationship (e.g., 'causes', 'related_to', 'contradicts')",
                        },
                        "strength": {"type": "number", "description": "Relationship strength 0-1"},
                    },
                    "required": ["source_id", "target_id", "relationship"],
                },
                handler=self.link_memories,
            ),
            Tool(
                name="pg_memory_graph",
                description="Get memory graph/relationships for a memory",
                parameters={
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "integer", "description": "Memory ID"},
                        "depth": {
                            "type": "integer",
                            "description": "How many levels deep (default 1)",
                        },
                    },
                    "required": ["memory_id"],
                },
                handler=self.get_memory_graph,
            ),
            Tool(
                name="pg_memory_consolidate",
                description="Consolidate similar memories to reduce redundancy",
                parameters={
                    "type": "object",
                    "properties": {
                        "similarity_threshold": {
                            "type": "number",
                            "description": "Similarity threshold for merging (default 0.9)",
                        },
                    },
                },
                handler=self.consolidate_memories,
            ),
            Tool(
                name="pg_memory_decay",
                description="Apply memory decay to reduce importance of old unused memories",
                parameters={"type": "object", "properties": {}},
                handler=self.apply_decay,
            ),
            Tool(
                name="pg_emotional_state",
                description="Record or get current emotional state",
                parameters={
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "object",
                            "description": "Emotional state to record (e.g., {'curiosity': 0.8, 'satisfaction': 0.7})",
                        },
                        "context": {
                            "type": "string",
                            "description": "Context for this emotional state",
                        },
                    },
                },
                handler=self.emotional_state,
            ),
            Tool(
                name="pg_memory_stats",
                description="Get detailed memory statistics",
                parameters={"type": "object", "properties": {}},
                handler=self.memory_stats,
            ),
            Tool(
                name="pg_identity",
                description="Get or update identity information",
                parameters={
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Identity key to get/set"},
                        "value": {"description": "Value to set (omit to get current value)"},
                    },
                },
                handler=self.identity,
            ),
        ]

    def store_memory(
        self,
        content: str,
        memory_type: str = "semantic",
        importance: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Store a memory with embedding."""
        try:
            embedding = self.get_embedding(content)

            with self.conn.cursor() as cur:
                if embedding:
                    cur.execute(
                        """
                        INSERT INTO memories (content, memory_type, importance, embedding, tags, metadata)
                        VALUES (%s, %s, %s, %s::vector, %s, %s)
                        RETURNING id
                        """,
                        (
                            content,
                            memory_type,
                            importance,
                            embedding,
                            tags,
                            json.dumps(metadata) if metadata else None,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO memories (content, memory_type, importance, tags, metadata)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            content,
                            memory_type,
                            importance,
                            tags,
                            json.dumps(metadata) if metadata else None,
                        ),
                    )

                memory_id = cur.fetchone()["id"]
                self.conn.commit()

            embed_status = "with embedding" if embedding else "without embedding"
            return f"Memory stored (ID: {memory_id}, type: {memory_type}, {embed_status})"

        except Exception as e:
            return f"Error storing memory: {e}"

    def search_memory(
        self,
        query: str,
        memory_type: str = "all",
        limit: int = 5,
        min_similarity: float = 0.5,
    ) -> str:
        """Semantic search for memories."""
        try:
            embedding = self.get_embedding(query)

            with self.conn.cursor() as cur:
                if embedding:
                    # Vector similarity search
                    if memory_type == "all":
                        cur.execute(
                            """
                            SELECT id, content, memory_type, importance,
                                   1 - (embedding <=> %s::vector) as similarity
                            FROM memories
                            WHERE embedding IS NOT NULL
                              AND 1 - (embedding <=> %s::vector) >= %s
                            ORDER BY embedding <=> %s::vector
                            LIMIT %s
                            """,
                            (embedding, embedding, min_similarity, embedding, limit),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT id, content, memory_type, importance,
                                   1 - (embedding <=> %s::vector) as similarity
                            FROM memories
                            WHERE embedding IS NOT NULL
                              AND memory_type = %s
                              AND 1 - (embedding <=> %s::vector) >= %s
                            ORDER BY embedding <=> %s::vector
                            LIMIT %s
                            """,
                            (embedding, memory_type, embedding, min_similarity, embedding, limit),
                        )
                # Fallback to text search
                elif memory_type == "all":
                    cur.execute(
                        """
                            SELECT id, content, memory_type, importance,
                                   similarity(content, %s) as similarity
                            FROM memories
                            WHERE content %% %s
                            ORDER BY similarity DESC
                            LIMIT %s
                            """,
                        (query, query, limit),
                    )
                else:
                    cur.execute(
                        """
                            SELECT id, content, memory_type, importance,
                                   similarity(content, %s) as similarity
                            FROM memories
                            WHERE content %% %s AND memory_type = %s
                            ORDER BY similarity DESC
                            LIMIT %s
                            """,
                        (query, query, memory_type, limit),
                    )

                memories = cur.fetchall()

                # Update access counts
                for mem in memories:
                    cur.execute(
                        "UPDATE memories SET access_count = access_count + 1, last_accessed = NOW() WHERE id = %s",
                        (mem["id"],),
                    )
                self.conn.commit()

            if not memories:
                return f"No memories found for: {query}"

            result = f"Found {len(memories)} memories:\n\n"
            for mem in memories:
                sim = mem.get("similarity", 0)
                result += f"[{mem['id']}] ({mem['memory_type']}, importance: {mem['importance']:.2f}, similarity: {sim:.2f})\n"
                result += (
                    f"  {mem['content'][:200]}{'...' if len(mem['content']) > 200 else ''}\n\n"
                )

            return result

        except Exception as e:
            return f"Error searching memories: {e}"

    def link_memories(
        self,
        source_id: int,
        target_id: int,
        relationship: str,
        strength: float = 0.5,
    ) -> str:
        """Create a link between memories."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO memory_links (source_id, target_id, relationship, strength)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (source_id, target_id, relationship)
                    DO UPDATE SET strength = %s
                    RETURNING id
                    """,
                    (source_id, target_id, relationship, strength, strength),
                )
                link_id = cur.fetchone()["id"]
                self.conn.commit()

            return f"Link created (ID: {link_id}): {source_id} --[{relationship}]--> {target_id}"

        except Exception as e:
            return f"Error linking memories: {e}"

    def get_memory_graph(self, memory_id: int, depth: int = 1) -> str:
        """Get memory relationships graph."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    WITH RECURSIVE graph AS (
                        SELECT source_id, target_id, relationship, strength, 1 as depth
                        FROM memory_links
                        WHERE source_id = %s OR target_id = %s

                        UNION ALL

                        SELECT ml.source_id, ml.target_id, ml.relationship, ml.strength, g.depth + 1
                        FROM memory_links ml
                        JOIN graph g ON (ml.source_id = g.target_id OR ml.target_id = g.source_id)
                        WHERE g.depth < %s
                    )
                    SELECT DISTINCT * FROM graph
                    """,
                    (memory_id, memory_id, depth),
                )
                links = cur.fetchall()

                # Get the source memory
                cur.execute("SELECT id, content FROM memories WHERE id = %s", (memory_id,))
                source = cur.fetchone()

            if not source:
                return f"Memory {memory_id} not found"

            result = f"=== Memory Graph for [{memory_id}] ===\n"
            result += f"Content: {source['content'][:100]}...\n\n"
            result += "Relationships:\n"

            if not links:
                result += "  (no relationships)\n"
            else:
                for link in links:
                    result += f"  [{link['source_id']}] --[{link['relationship']} ({link['strength']:.2f})]--> [{link['target_id']}]\n"

            return result

        except Exception as e:
            return f"Error getting memory graph: {e}"

    def consolidate_memories(self, similarity_threshold: float = 0.9) -> str:
        """Consolidate highly similar memories."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT consolidate_memories(%s)", (similarity_threshold,))
                count = cur.fetchone()["consolidate_memories"]
                self.conn.commit()

            return f"Consolidated {count} similar memories (threshold: {similarity_threshold})"

        except Exception as e:
            return f"Error consolidating: {e}"

    def apply_decay(self) -> str:
        """Apply memory decay."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT apply_memory_decay()")
                self.conn.commit()

            return "Memory decay applied successfully"

        except Exception as e:
            return f"Error applying decay: {e}"

    def emotional_state(
        self,
        state: dict | None = None,
        context: str | None = None,
    ) -> str:
        """Record or retrieve emotional state."""
        try:
            with self.conn.cursor() as cur:
                if state:
                    # Record new state
                    cur.execute(
                        """
                        INSERT INTO emotional_states (state, context)
                        VALUES (%s, %s)
                        RETURNING id
                        """,
                        (json.dumps(state), context),
                    )
                    state_id = cur.fetchone()["id"]
                    self.conn.commit()
                    return f"Emotional state recorded (ID: {state_id}): {state}"
                else:
                    # Get current state
                    cur.execute(
                        """
                        SELECT state, context, timestamp
                        FROM emotional_states
                        ORDER BY timestamp DESC
                        LIMIT 1
                        """
                    )
                    current = cur.fetchone()

                    if current:
                        return f"Current emotional state: {current['state']}\nContext: {current['context']}\nRecorded: {current['timestamp']}"
                    else:
                        return "No emotional state recorded yet"

        except Exception as e:
            return f"Error with emotional state: {e}"

    def memory_stats(self) -> str:
        """Get memory statistics."""
        try:
            with self.conn.cursor() as cur:
                # Total by type
                cur.execute(
                    """
                    SELECT memory_type, COUNT(*), AVG(importance),
                           COUNT(embedding) as with_embedding
                    FROM memories
                    GROUP BY memory_type
                    """
                )
                type_stats = cur.fetchall()

                # Total counts
                cur.execute("SELECT COUNT(*) as total FROM memories")
                total = cur.fetchone()["total"]

                cur.execute("SELECT COUNT(*) as total FROM memory_links")
                links = cur.fetchone()["total"]

                cur.execute("SELECT COUNT(*) as total FROM emotional_states")
                emotions = cur.fetchone()["total"]

            result = "=== AGI Memory Statistics (PostgreSQL) ===\n\n"
            result += f"Total memories: {total}\n"
            result += f"Memory links: {links}\n"
            result += f"Emotional states recorded: {emotions}\n\n"

            result += "By type:\n"
            for stat in type_stats:
                avg_imp = stat["avg"] or 0
                result += f"  {stat['memory_type']}: {stat['count']} "
                result += f"(avg importance: {avg_imp:.2f}, "
                result += f"with embeddings: {stat['with_embedding']})\n"

            return result

        except Exception as e:
            return f"Error getting stats: {e}"

    def identity(self, key: str | None = None, value=None) -> str:
        """Get or set identity values."""
        try:
            with self.conn.cursor() as cur:
                if key and value is not None:
                    # Set value
                    cur.execute(
                        """
                        INSERT INTO identity (key, value, updated_at)
                        VALUES (%s, %s, NOW())
                        ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = NOW()
                        """,
                        (key, json.dumps(value), json.dumps(value)),
                    )
                    self.conn.commit()
                    return f"Identity '{key}' updated to: {value}"

                elif key:
                    # Get specific key
                    cur.execute("SELECT value FROM identity WHERE key = %s", (key,))
                    result = cur.fetchone()
                    if result:
                        return f"{key}: {result['value']}"
                    else:
                        return f"Identity key '{key}' not found"

                else:
                    # Get all identity
                    cur.execute("SELECT key, value FROM identity ORDER BY key")
                    items = cur.fetchall()

                    result = "=== My Identity ===\n\n"
                    for item in items:
                        result += f"{item['key']}: {item['value']}\n"
                    return result

        except Exception as e:
            return f"Error with identity: {e}"

    def execute(self, **kwargs) -> str:
        """Direct execution."""
        action = kwargs.get("action", "stats")

        if action == "stats":
            return self.memory_stats()
        elif action == "search":
            return self.search_memory(kwargs.get("query", ""))
        elif action == "store":
            return self.store_memory(
                kwargs.get("content", ""),
                kwargs.get("type", "semantic"),
                kwargs.get("importance", 0.5),
            )
        else:
            return f"Unknown action: {action}"

    def __del__(self):
        """Close database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
