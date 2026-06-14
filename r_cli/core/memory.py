"""
Sistema de memoria para R CLI.

Implementa memoria jerárquica:
- Short-term: Contexto de la conversación actual
- Medium-term: Historial de la sesión
- Long-term: Base de conocimiento persistente (RAG con ChromaDB)
"""

import hashlib
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from r_cli.core.config import Config

logger = logging.getLogger(__name__)


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

    def __init__(self, config: Optional[Config] = None, namespace: str | None = None):
        self.config = config or Config()
        self.config.ensure_directories()
        self.namespace = namespace

        # Short-term memory (conversación actual)
        self.short_term: list[MemoryEntry] = []

        # Paths
        self.home_dir = Path(os.path.expanduser(self.config.home_dir))
        session_dir = self.home_dir / "agents" / namespace if namespace else self.home_dir
        session_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = session_dir / "session.json"
        self.gbrain_state_file = session_dir / "gbrain-sync.json"
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

        if self._gbrain_enabled():
            self._sync_short_term_to_gbrain()

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

    def status(self) -> dict:
        """Return backend and storage status for this namespace."""
        state = self._load_gbrain_state()
        return {
            "provider": self.config.memory.provider,
            "namespace": self.namespace or "default",
            "session_file": str(self.session_file),
            "entries": len(self.short_term),
            "rag_directory": str(self.long_term_dir),
            "gbrain_enabled": self._gbrain_enabled(),
            "gbrain_available": self._gbrain_available() if self._gbrain_enabled() else False,
            "gbrain_command": self.config.memory.gbrain_command,
            "gbrain_retrieval_command": self.config.memory.gbrain_retrieval_command,
            "gbrain_source": self.config.memory.gbrain_source,
            "gbrain_synced_entries": state["last_synced_count"],
        }

    def sync(self) -> dict:
        """Persist the session and, when enabled, flush new entries to GBrain."""
        if not self.short_term:
            self.load_session()
        before = self._load_gbrain_state()["last_synced_count"] if self._gbrain_enabled() else 0
        self.save_session()
        after = self._load_gbrain_state()["last_synced_count"] if self._gbrain_enabled() else 0
        return {
            **self.status(),
            "session_saved": True,
            "entries_uploaded": max(0, after - before),
        }

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
        if self._gbrain_enabled():
            gbrain_id = self._add_document_gbrain(content, doc_id, metadata)
            if gbrain_id is not None:
                return gbrain_id

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
        if self._gbrain_enabled():
            results = self._search_gbrain(query)
            if results:
                return results

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
            docs_context = "\n\n".join(
                [self._format_search_result(result) for result in search_results]
            )
            context_parts.append(f"Documentos relevantes:\n{docs_context}")

        full_context = "\n\n---\n\n".join(context_parts)

        # Truncar si es muy largo
        if len(full_context) > max_chars:
            full_context = full_context[:max_chars] + "..."

        return full_context

    def _gbrain_enabled(self) -> bool:
        return self.config.memory.provider == "gbrain"

    def _gbrain_available(self) -> bool:
        return shutil.which(self.config.memory.gbrain_command) is not None

    def _run_gbrain(
        self,
        command: list[str],
        *,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str] | None:
        if not self._gbrain_available():
            return None

        try:
            return subprocess.run(
                [self.config.memory.gbrain_command, *command],
                input=input_text,
                text=True,
                capture_output=True,
                timeout=self.config.memory.gbrain_timeout_seconds,
                check=False,
            )
        except OSError as exc:
            logger.warning("GBrain command failed to start: %s", exc)
            return None
        except subprocess.TimeoutExpired:
            logger.warning("GBrain command timed out: %s", " ".join(command))
            return None

    def _gbrain_source_args(self) -> list[str]:
        if self.config.memory.gbrain_source:
            return ["--source", self.config.memory.gbrain_source]
        return []

    def _load_gbrain_state(self) -> dict[str, int]:
        if not self.gbrain_state_file.exists():
            return {"last_synced_count": 0}
        try:
            with open(self.gbrain_state_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"last_synced_count": 0}
        count = data.get("last_synced_count", 0)
        if not isinstance(count, int) or count < 0:
            count = 0
        return {"last_synced_count": count}

    def _save_gbrain_state(self, count: int) -> None:
        with open(self.gbrain_state_file, "w") as f:
            json.dump({"last_synced_count": count}, f, indent=2)

    def _sync_short_term_to_gbrain(self) -> None:
        state = self._load_gbrain_state()
        start_index = state["last_synced_count"]
        if start_index > len(self.short_term):
            start_index = 0
        pending_entries = self.short_term[start_index:]
        if not pending_entries:
            return

        next_index = start_index
        for entry in pending_entries:
            payload = self._format_gbrain_entry(entry)
            result = self._run_gbrain(
                ["capture", "--stdin", *self._gbrain_source_args()],
                input_text=payload,
            )
            if result is None or result.returncode != 0:
                stderr = (
                    result.stderr.strip() if result is not None and result.stderr else "unknown"
                )
                logger.warning("GBrain capture failed: %s", stderr)
                return
            next_index += 1

        self._save_gbrain_state(next_index)

    def _format_gbrain_entry(self, entry: MemoryEntry) -> str:
        namespace = self.namespace or "default"
        return (
            "# R CLI Session Memory\n\n"
            f"- namespace: {namespace}\n"
            f"- entry_type: {entry.entry_type}\n"
            f"- timestamp: {entry.timestamp.isoformat()}\n\n"
            f"{entry.content}\n"
        )

    def _add_document_gbrain(
        self,
        content: str,
        doc_id: Optional[str],
        metadata: Optional[dict],
    ) -> str | None:
        if doc_id is None:
            doc_id = hashlib.md5(content.encode()).hexdigest()[:12]

        metadata_block = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
        payload = (
            "# R CLI Document Memory\n\n"
            f"- doc_id: {doc_id}\n"
            f"- namespace: {self.namespace or 'default'}\n"
            f"- metadata: {metadata_block}\n\n"
            f"{content}\n"
        )
        result = self._run_gbrain(
            ["capture", "--stdin", *self._gbrain_source_args()],
            input_text=payload,
        )
        if result is None or result.returncode != 0:
            stderr = result.stderr.strip() if result is not None and result.stderr else "unknown"
            logger.warning("GBrain document capture failed: %s", stderr)
            return None
        return doc_id

    def _search_gbrain(self, query: str) -> list[dict]:
        retrieval_command = self.config.memory.gbrain_retrieval_command
        result = self._run_gbrain([retrieval_command, query, *self._gbrain_source_args()])
        if result is None or result.returncode != 0:
            stderr = result.stderr.strip() if result is not None and result.stderr else "unknown"
            logger.warning("GBrain retrieval failed: %s", stderr)
            return []

        output = result.stdout.strip()
        if not output:
            return []

        return [
            {
                "content": output,
                "metadata": {
                    "provider": "gbrain",
                    "command": retrieval_command,
                },
                "distance": None,
            }
        ]

    def _format_search_result(self, result: dict) -> str:
        provider = result.get("metadata", {}).get("provider")
        prefix = "[Brain]" if provider == "gbrain" else "[Doc]"
        content = result["content"][:500]
        suffix = "" if provider == "gbrain" else "..."
        return f"{prefix} {content}{suffix}"
