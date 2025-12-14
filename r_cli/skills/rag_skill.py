"""
Enhanced RAG Skill for R CLI.

Semantic search using local embeddings with sentence-transformers.
100% offline after downloading the model.
"""

from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class RAGSkill(Skill):
    """Skill for RAG with local embeddings."""

    name = "rag"
    description = "Knowledge base with semantic search using local embeddings"

    # Available models
    MODELS = {
        "mini": "Fast and lightweight (80MB, ideal for CPU)",
        "minilm": "Speed/quality balance (120MB)",
        "mpnet": "High quality (420MB)",
        "multilingual": "Supports 50+ languages (470MB)",
        "spanish": "Optimized for Spanish (470MB)",
        "qa": "Optimized for Q&A (80MB)",
        "code": "For code search (420MB)",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._embeddings = None
        self._index = None
        self._model_name = "mini"  # Default

    def _get_embeddings(self):
        """Lazy loading of embeddings."""
        if self._embeddings is None:
            try:
                from r_cli.core.embeddings import LocalEmbeddings

                cache_dir = None
                if hasattr(self.config, "home_dir"):
                    cache_dir = Path(self.config.home_dir) / "embeddings_cache"

                self._embeddings = LocalEmbeddings(
                    model_name=self._model_name,
                    cache_dir=cache_dir,
                    use_cache=True,
                )
            except ImportError:
                return None
        return self._embeddings

    def _get_index(self):
        """Lazy loading of the semantic index."""
        if self._index is None:
            embeddings = self._get_embeddings()
            if embeddings is None:
                return None

            try:
                from r_cli.core.embeddings import SemanticIndex

                index_path = None
                if hasattr(self.config, "home_dir"):
                    index_path = Path(self.config.home_dir) / "semantic_index.json"

                self._index = SemanticIndex(
                    embeddings=embeddings,
                    index_path=index_path,
                )
            except Exception:
                return None

        return self._index

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="rag_add",
                description="Add a document to the knowledge base",
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Document content",
                        },
                        "doc_id": {
                            "type": "string",
                            "description": "Optional document ID",
                        },
                        "source": {
                            "type": "string",
                            "description": "Document source/origin",
                        },
                        "tags": {
                            "type": "string",
                            "description": "Comma-separated tags",
                        },
                    },
                    "required": ["content"],
                },
                handler=self.add_document,
            ),
            Tool(
                name="rag_add_file",
                description="Add a file to the knowledge base",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file",
                        },
                        "chunk_size": {
                            "type": "integer",
                            "description": "Chunk size (default: 1000)",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.add_file,
            ),
            Tool(
                name="rag_search",
                description="Search for similar documents using semantic search",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search text",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results (default: 5)",
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Minimum similarity 0-1 (default: 0.3)",
                        },
                    },
                    "required": ["query"],
                },
                handler=self.search,
            ),
            Tool(
                name="rag_similarity",
                description="Calculate semantic similarity between two texts",
                parameters={
                    "type": "object",
                    "properties": {
                        "text1": {"type": "string", "description": "First text"},
                        "text2": {"type": "string", "description": "Second text"},
                    },
                    "required": ["text1", "text2"],
                },
                handler=self.similarity,
            ),
            Tool(
                name="rag_list_models",
                description="List available embedding models",
                parameters={"type": "object", "properties": {}},
                handler=self.list_models,
            ),
            Tool(
                name="rag_set_model",
                description="Change the embedding model",
                parameters={
                    "type": "object",
                    "properties": {
                        "model": {
                            "type": "string",
                            "enum": list(self.MODELS.keys()),
                            "description": "Model name",
                        },
                    },
                    "required": ["model"],
                },
                handler=self.set_model,
            ),
            Tool(
                name="rag_stats",
                description="Show index statistics",
                parameters={"type": "object", "properties": {}},
                handler=self.get_stats,
            ),
            Tool(
                name="rag_delete",
                description="Delete a document from the index",
                parameters={
                    "type": "object",
                    "properties": {
                        "doc_id": {
                            "type": "string",
                            "description": "ID of the document to delete",
                        },
                    },
                    "required": ["doc_id"],
                },
                handler=self.delete_document,
            ),
            Tool(
                name="rag_clear",
                description="Clear the entire index (caution!)",
                parameters={"type": "object", "properties": {}},
                handler=self.clear_index,
            ),
        ]

    def add_document(
        self,
        content: str,
        doc_id: Optional[str] = None,
        source: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> str:
        """Add a document to the index."""
        index = self._get_index()
        if index is None:
            return (
                "Error: sentence-transformers not installed. Run: pip install sentence-transformers"
            )

        try:
            metadata = {}
            if source:
                metadata["source"] = source
            if tags:
                metadata["tags"] = [t.strip() for t in tags.split(",")]

            doc_id = index.add(
                content=content,
                doc_id=doc_id,
                metadata=metadata,
            )

            return f"Document added with ID: {doc_id}\nContent: {content[:100]}..."

        except Exception as e:
            return f"Error adding document: {e}"

    def add_file(
        self,
        file_path: str,
        chunk_size: int = 1000,
    ) -> str:
        """Add a file to the index, splitting it into chunks."""
        index = self._get_index()
        if index is None:
            return (
                "Error: sentence-transformers not installed. Run: pip install sentence-transformers"
            )

        path = Path(file_path).expanduser()
        if not path.exists():
            return f"Error: File not found: {file_path}"

        try:
            # Read file
            content = path.read_text(encoding="utf-8", errors="ignore")

            # Split into chunks
            chunks = self._chunk_text(content, chunk_size)

            # Add chunks
            documents = []
            for i, chunk in enumerate(chunks):
                documents.append(
                    {
                        "content": chunk,
                        "id": f"{path.stem}_{i}",
                        "metadata": {
                            "source": str(path),
                            "chunk": i,
                            "total_chunks": len(chunks),
                        },
                    }
                )

            ids = index.add_batch(documents)

            return f"File added: {path.name}\n{len(chunks)} chunks indexed."

        except Exception as e:
            return f"Error processing file: {e}"

    def _chunk_text(self, text: str, chunk_size: int) -> list[str]:
        """Split text into chunks."""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        overlap = chunk_size // 5  # 20% overlap

        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # Cut at period or space
            if end < len(text):
                for sep in [". ", "\n\n", "\n", " "]:
                    last_sep = chunk.rfind(sep)
                    if last_sep > chunk_size // 2:
                        chunk = chunk[: last_sep + len(sep)]
                        end = start + last_sep + len(sep)
                        break

            chunks.append(chunk.strip())
            start = end - overlap

        return chunks

    def search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> str:
        """Search for similar documents."""
        index = self._get_index()
        if index is None:
            return (
                "Error: sentence-transformers not installed. Run: pip install sentence-transformers"
            )

        try:
            results = index.search(
                query=query,
                top_k=top_k,
                threshold=threshold,
            )

            if not results:
                return f"No similar documents found for: '{query}'"

            output = [f"Results for: '{query}'\n"]

            for i, doc in enumerate(results, 1):
                similarity = doc["similarity"]
                content = doc["content"]
                if len(content) > 300:
                    content = content[:300] + "..."

                output.append(f"{i}. [Similarity: {similarity:.2%}]")
                output.append(f"   ID: {doc['id']}")

                if doc.get("metadata", {}).get("source"):
                    output.append(f"   Source: {doc['metadata']['source']}")

                output.append(f"   {content}")
                output.append("")

            return "\n".join(output)

        except Exception as e:
            return f"Search error: {e}"

    def similarity(self, text1: str, text2: str) -> str:
        """Calculate similarity between two texts."""
        embeddings = self._get_embeddings()
        if embeddings is None:
            return "Error: sentence-transformers not installed."

        try:
            sim = embeddings.similarity(text1, text2)

            interpretation = ""
            if sim >= 0.8:
                interpretation = "Very similar"
            elif sim >= 0.6:
                interpretation = "Similar"
            elif sim >= 0.4:
                interpretation = "Moderately similar"
            elif sim >= 0.2:
                interpretation = "Slightly similar"
            else:
                interpretation = "Not related"

            return f"""Semantic similarity: {sim:.2%} ({interpretation})

Text 1: {text1[:100]}{"..." if len(text1) > 100 else ""}
Text 2: {text2[:100]}{"..." if len(text2) > 100 else ""}"""

        except Exception as e:
            return f"Error calculating similarity: {e}"

    def list_models(self) -> str:
        """List available models."""
        try:
            from r_cli.core.embeddings import list_available_models

            return list_available_models()
        except ImportError:
            result = ["Available embedding models:\n"]
            for name, desc in self.MODELS.items():
                result.append(f"  - {name}: {desc}")
            result.append("\nInstallation: pip install sentence-transformers")
            return "\n".join(result)

    def set_model(self, model: str) -> str:
        """Change the embedding model."""
        if model not in self.MODELS:
            return f"Error: Model '{model}' not valid. Use: {', '.join(self.MODELS.keys())}"

        self._model_name = model
        self._embeddings = None  # Force reload
        self._index = None

        return f"Model changed to: {model}\n{self.MODELS[model]}"

    def get_stats(self) -> str:
        """Get index statistics."""
        index = self._get_index()
        if index is None:
            return "Error: sentence-transformers not installed."

        try:
            stats = index.get_stats()
            embeddings = self._get_embeddings()
            model_info = embeddings.get_model_info() if embeddings else {}

            result = [
                "RAG Statistics:\n",
                f"  Indexed documents: {stats['total_documents']}",
                f"  Embedding dimension: {stats['embedding_dimension']}",
                f"  Model: {stats['model']}",
                f"  Index size: {stats['index_size_mb']:.2f} MB",
            ]

            if model_info:
                result.append(f"  Device: {model_info.get('device', 'N/A')}")
                result.append(f"  Embedding cache: {model_info.get('cache_size', 0)} entries")

            return "\n".join(result)

        except Exception as e:
            return f"Error getting statistics: {e}"

    def delete_document(self, doc_id: str) -> str:
        """Delete a document."""
        index = self._get_index()
        if index is None:
            return "Error: sentence-transformers not installed."

        if index.delete(doc_id):
            return f"Document '{doc_id}' deleted."
        else:
            return f"Document '{doc_id}' not found."

    def clear_index(self) -> str:
        """Clear the entire index."""
        index = self._get_index()
        if index is None:
            return "Error: sentence-transformers not installed."

        index.clear()
        return "Index cleared completely."

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "stats")
        query = kwargs.get("query")
        content = kwargs.get("content")
        file_path = kwargs.get("file")

        if query:
            return self.search(query, kwargs.get("top_k", 5))
        elif content:
            return self.add_document(content, kwargs.get("id"), kwargs.get("source"))
        elif file_path:
            return self.add_file(file_path, kwargs.get("chunk_size", 1000))
        elif action == "models":
            return self.list_models()
        elif action == "clear":
            return self.clear_index()
        else:
            return self.get_stats()
