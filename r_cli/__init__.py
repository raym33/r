"""
R CLI - Your Local AI Operating System
======================================

A terminal-based AI agent powered by local open source LLMs.
100% private, 100% offline, 100% yours.

Works with:
- LM Studio (recommended)
- Ollama
- Any OpenAI-compatible server

Available Skills:
- pdf: Generate professional PDF documents
- latex: Compile LaTeX to PDF
- ocr: Extract text from images/PDFs
- voice: Transcription (Whisper) + TTS (Piper)
- design: Image generation with Stable Diffusion
- calendar: Local calendar & tasks
- multiagent: Multi-agent orchestration
- plugin: Community plugin system
- rag: Semantic search with local embeddings
- resume: Summarize long documents
- sql: SQL queries on CSVs/DBs
- code: Generate and execute code
- fs: File operations

Installation:
    pip install r-cli-ai

    # With extras:
    pip install r-cli-ai[rag]      # Semantic search
    pip install r-cli-ai[audio]    # Voice mode
    pip install r-cli-ai[design]   # Image generation
    pip install r-cli-ai[all]      # Everything

Usage:
    r                    # Interactive mode
    r "message"          # Direct chat
    r pdf "content"      # Execute skill directly
    r --help             # Show help

For more info: https://github.com/raym33/r
"""

__version__ = "0.3.2"
__author__ = "Ramón Guillamón"
__email__ = "learntouseai@gmail.com"

from r_cli.main import cli, create_agent

__all__ = ["__version__", "cli", "create_agent"]
