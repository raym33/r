"""
Sistema de memoria para R CLI.

Implementa memoria jerárquica:
- Short-term: Contexto de la conversación actual
- Medium-term: Historial de la sesión
- Long-term: Base de conocimiento persistente (RAG con ChromaDB)
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from r_cli.core.config import Config


@dataclass
class MemoryEntry:
    """Una entrada en la memoria."""

    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    entry_type: str = "general"  # general, task, fact, document
    metadata: dict = field(default_factory=dict)
    embedding: Optional[list[float]] = None

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "entry_type": self.entry_type,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        return cls(
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            entry_type=data.get("entry_type", "general"),
            metadata=data.get("metadata", {}),
        )


class Memory:
    """
    Sistema de memoria con múltiples niveles.

    - Short-term: Lista en memoria (conversación actual)
    - Medium-term: Archivo JSON de sesión
    - Long-term: ChromaDB para RAG persistente
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.config.ensure_directories()

        # Short-term memory (conversación actual)
        self.short_term: list[MemoryEntry] = []

        # Paths
        self.home_dir = Path(os.path.expanduser(self.config.home_dir))
        self.session_file = self.home_dir / "session.json"
        self.long_term_dir = Path(os.path.expanduser(self.config.rag.persist_directory))

        # ChromaDB para long-term (lazy loading)
        self._chroma_client = None
        self._collection = None

    @property
    def chroma_client(self):
        """Lazy loading de ChromaDB."""
        if self._chroma_client is None:
            try:
                import chromadb

                # Use new PersistentClient API (ChromaDB >= 0.4.0)
                self._chroma_client = chromadb.PersistentClient(path=str(self.long_term_dir))
            except ImportError:
                # ChromaDB no instalado, usar fallback
                self._chroma_client = None
            except Exception as e:
                # Error initializing ChromaDB, use fallback
                import logging

                logging.getLogger(__name__).warning(f"ChromaDB init failed: {e}")
                self._chroma_client = None

        return self._chroma_client

    @property
    def collection(self):
        """Obtiene o crea la colección de ChromaDB."""
        if self._collection is None and self.chroma_client is not None:
            self._collection = self.chroma_client.get_or_create_collection(
                name=self.config.rag.collection_name,
                metadata={"description": "R CLI knowledge base"},
            )
        return self._collection

    # ==================== SHORT-TERM MEMORY ====================

    def add_short_term(
        self, content: str, entry_type: str = "general", metadata: Optional[dict] = None
    ) -> None:
        """Agrega entrada a memoria de corto plazo."""
        entry = MemoryEntry(
            content=content,
            entry_type=entry_type,
            metadata=metadata or {},
        )
        self.short_term.append(entry)

    def get_short_term_context(self, max_entries: int = 10) -> str:
        """Obtiene contexto reciente para el LLM."""
        recent = self.short_term[-max_entries:]
        if not recent:
            return ""

        context_parts = []
        for entry in recent:
            prefix = f"[{entry.entry_type.upper()}]" if entry.entry_type != "general" else ""
            context_parts.append(f"{prefix} {entry.content}")

        return "\n".join(context_parts)

    def clear_short_term(self) -> None:
        """Limpia memoria de corto plazo."""
        self.short_term = []

    # ==================== MEDIUM-TERM MEMORY ====================

    def save_session(self) -> None:
        """Guarda la sesión actual a disco."""
        session_data = {
            "timestamp": datetime.now().isoformat(),
            "entries": [e.to_dict() for e in self.short_term],
        }

        with open(self.session_file, "w") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)

    def load_session(self) -> bool:
        """Carga sesión anterior si existe."""
        if not self.session_file.exists():
            return False

        try:
            with open(self.session_file) as f:
                data = json.load(f)

            self.short_term = [MemoryEntry.from_dict(e) for e in data.get("entries", [])]
            return True
        except json.JSONDecodeError:
            # Archivo corrupto, ignorar silenciosamente
            return False
        except (KeyError, TypeError):
            # Formato de datos inválido
            return False
        except OSError:
            # Error de lectura de archivo
            return False

    def get_session_summary(self) -> str:
        """Genera un resumen de la sesión para contexto."""
        if not self.short_term:
            return "No hay historial de sesión."

        # Agrupar por tipo
        by_type = {}
        for entry in self.short_term:
            t = entry.entry_type
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(entry.content[:100])  # Primeros 100 chars

        summary_parts = ["Resumen de sesión:"]
        for entry_type, contents in by_type.items():
            summary_parts.append(f"- {entry_type}: {len(contents)} entradas")

        return "\n".join(summary_parts)

    # ==================== LONG-TERM MEMORY (RAG) ====================

    def add_document(
        self,
        content: str,
        doc_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Agrega un documento a la base de conocimiento persistente.

        Returns: ID del documento
        """
        if self.collection is None:
            # Fallback sin ChromaDB: guardar en archivo
            return self._add_document_fallback(content, doc_id, metadata)

        # Generar ID si no se proporciona
        if doc_id is None:
            doc_id = hashlib.md5(content.encode()).hexdigest()[:12]

        # Dividir en chunks si es muy largo
        chunks = self._chunk_text(content)

        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_{i}"
            chunk_metadata = {
                **(metadata or {}),
                "doc_id": doc_id,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }

            self.collection.add(
                documents=[chunk],
                ids=[chunk_id],
                metadatas=[chunk_metadata],
            )

        return doc_id

    def _chunk_text(self, text: str) -> list[str]:
        """Divide texto en chunks para RAG."""
        chunk_size = self.config.rag.chunk_size
        overlap = self.config.rag.chunk_overlap

        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # Intentar cortar en un espacio o punto
            if end < len(text):
                last_period = chunk.rfind(".")
                last_space = chunk.rfind(" ")
                cut_point = max(last_period, last_space)
                if cut_point > chunk_size // 2:
                    chunk = chunk[: cut_point + 1]
                    end = start + cut_point + 1

            chunks.append(chunk.strip())
            start = end - overlap

        return chunks

    def _add_document_fallback(
        self, content: str, doc_id: Optional[str], metadata: Optional[dict]
    ) -> str:
        """Fallback sin ChromaDB: guarda en archivo JSON."""
        if doc_id is None:
            doc_id = hashlib.md5(content.encode()).hexdigest()[:12]

        docs_file = self.home_dir / "documents.json"

        # Cargar documentos existentes
        docs = {}
        if docs_file.exists():
            with open(docs_file) as f:
                docs = json.load(f)

        # Agregar nuevo documento
        docs[doc_id] = {
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }

        # Guardar
        with open(docs_file, "w") as f:
            json.dump(docs, f, indent=2, ensure_ascii=False)

        return doc_id

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """
        Busca en la base de conocimiento.

        Returns: Lista de resultados con content, metadata, y distance.
        """
        if self.collection is None:
            return self._search_fallback(query, n_results)

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
        )

        # Formatear resultados
        formatted = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                formatted.append(
                    {
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else None,
                    }
                )

        return formatted

    def _search_fallback(self, query: str, n_results: int) -> list[dict]:
        """Búsqueda simple sin ChromaDB (keyword matching)."""
        docs_file = self.home_dir / "documents.json"

        if not docs_file.exists():
            return []

        with open(docs_file) as f:
            docs = json.load(f)

        # Búsqueda simple por keywords
        query_lower = query.lower()
        results = []

        for doc_id, doc_data in docs.items():
            content = doc_data["content"].lower()
            # Contar matches de palabras
            matches = sum(1 for word in query_lower.split() if word in content)
            if matches > 0:
                results.append(
                    {
                        "content": doc_data["content"],
                        "metadata": {**doc_data.get("metadata", {}), "doc_id": doc_id},
                        "distance": 1.0 / (matches + 1),  # Menor es mejor
                    }
                )

        # Ordenar por relevancia
        results.sort(key=lambda x: x["distance"])
        return results[:n_results]

    def get_relevant_context(self, query: str, max_chars: int = 4000) -> str:
        """
        Obtiene contexto relevante para una query.

        Combina short-term y long-term memory.
        """
        context_parts = []

        # Short-term context
        short_context = self.get_short_term_context(max_entries=5)
        if short_context:
            context_parts.append(f"Contexto reciente:\n{short_context}")

        # Long-term search
        search_results = self.search(query, n_results=3)
        if search_results:
            docs_context = "\n\n".join([f"[Doc] {r['content'][:500]}..." for r in search_results])
            context_parts.append(f"Documentos relevantes:\n{docs_context}")

        full_context = "\n\n---\n\n".join(context_parts)

        # Truncar si es muy largo
        if len(full_context) > max_chars:
            full_context = full_context[:max_chars] + "..."

        return full_context
