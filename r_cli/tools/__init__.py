"""
Herramientas compartidas para R CLI.

Estas son utilidades de bajo nivel usadas por múltiples skills.
"""

from r_cli.tools.text_processing import chunk_text, extract_sentences, word_count
from r_cli.tools.file_utils import safe_path, ensure_dir, get_file_type

__all__ = [
    "chunk_text",
    "extract_sentences",
    "word_count",
    "safe_path",
    "ensure_dir",
    "get_file_type",
]
