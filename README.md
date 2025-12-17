# R CLI

<div align="center">

```
██████╗        ██████╗██╗     ██╗
██╔══██╗      ██╔════╝██║     ██║
██████╔╝█████╗██║     ██║     ██║
██╔══██╗╚════╝██║     ██║     ██║
██║  ██║      ╚██████╗███████╗██║
╚═╝  ╚═╝       ╚═════╝╚══════╝╚═╝
```

**Local AI Agent Runtime**

[![PyPI version](https://badge.fury.io/py/r-cli-ai.svg)](https://pypi.org/project/r-cli-ai/)
[![Downloads](https://static.pepy.tech/badge/r-cli-ai)](https://pepy.tech/project/r-cli-ai)
[![CI](https://github.com/raym33/r/actions/workflows/ci.yml/badge.svg)](https://github.com/raym33/r/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A tool orchestrator that connects local LLMs to 76 system tools via function calling.

[Installation](#installation) · [Quick Start](#quick-start) · [All Skills](#all-76-skills) · [Distributed AI](#distributed-ai-apple-silicon-cluster) · [P2P](#p2p-distributed-agents) · [Docs](docs/COMPLETE_GUIDE.md)

</div>

---

## What is R CLI?

R CLI is a **tool orchestrator** for local LLMs. It exposes 76 "skills" (PDF generation, SQL queries, git, docker, distributed AI, P2P agents, etc.) as structured function calls that any OpenAI-compatible model can invoke.

**This is NOT an operating system.** It's a Python CLI that sits between your local LLM (Ollama, LM Studio) and real system tools.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   You       │────▶│   R CLI     │────▶│  Local LLM  │
│  (prompt)   │     │ (orchestrator)│    │  (Ollama)   │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                          │                    │
                          ▼                    │
                   ┌─────────────┐             │
                   │   Skills    │◀────────────┘
                   │ (74 tools)  │  function call
                   └─────────────┘
```

```bash
$ r chat "Create a PDF report about Python"
# LLM calls pdf.generate_pdf() -> creates python_report.pdf

$ r sql sales.csv "SELECT product, SUM(revenue) FROM data GROUP BY product"
# Runs actual SQL against CSV using DuckDB

$ r rag --add ./docs/ && r rag --query "how does auth work"
# ChromaDB vectors, semantic search across your docs
```

## Why Structured Tools Instead of Terminal Access?

You could just give an LLM shell access. But structured function calling provides:

| Raw Terminal Access | R CLI Structured Tools |
|---------------------|------------------------|
| Model guesses bash syntax | Model sees JSON schema for each tool |
| "Run `zip *.py`" can fail in many ways | `archive.create_zip(files=["*.py"])` with validation |
| Hard to add confirmation gates | Each tool can require user approval |
| No type checking | Pydantic validates all inputs |
| Unpredictable output parsing | Structured return values |

**Example:** When you ask "compress python files", the LLM doesn't generate bash. It calls:

```json
{
  "tool": "archive.create_zip",
  "arguments": {
    "source_path": ".",
    "pattern": "*.py",
    "output": "python_files.zip"
  }
}
```

R CLI validates the arguments, executes the tool, and returns structured results.

---

## Features

| Feature | Description |
|---------|-------------|
| **100% Local** | Your data never leaves your machine |
| **76 Skills** | PDF, SQL, code, git, docker, RAG, voice, and more |
| **Distributed AI** | Run 70B+ models across multiple Macs with MLX |
| **P2P Agents** | Discover and collaborate with other R CLI instances |
| **REST API** | OpenAI-compatible server for IDE integration |
| **Plugin System** | Add custom skills in Python |
| **Voice Interface** | Whisper STT + Piper TTS (optional) |
| **Hardware Skills** | GPIO, Bluetooth, WiFi for Raspberry Pi |

---

## Installation

```bash
# Basic
pip install r-cli-ai

# With all features
pip install r-cli-ai[all]

# R OS Simulator (Textual TUI)
pip install r-cli-ai[simulator]

# Raspberry Pi (with GPIO)
pip install r-cli-ai[all-rpi]
```

### Requirements

- Python 3.10+
- [Ollama](https://ollama.ai/) or [LM Studio](https://lmstudio.ai/)
- 8GB+ RAM (16GB+ recommended)

---

## Quick Start

### 1. Start your LLM

```bash
# Ollama
ollama pull qwen3:4b && ollama serve

# Or use LM Studio GUI
```

### 2. Run R CLI

```bash
# Interactive chat
r

# Direct command
r chat "Explain quantum computing in simple terms"

# Start API server
r serve --port 8765
```

---

## R OS - Terminal UI (Experimental)

A terminal-based interface that looks like Android. Built with [Textual](https://textual.textualize.io/). This is an experimental feature for Raspberry Pi and edge devices - not an actual OS.

```
┌─────────────────────────────────────────────────────────┐
│ ▁▂▄█ 📶 R OS          12:45          🔋 85%             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   💬 Messages   📞 Phone     📧 Email     🌐 Browser   │
│                                                         │
│   📷 Camera     🖼️ Gallery   🎵 Music     🎬 Video     │
│                                                         │
│   📁 Files      📅 Calendar  ⏰ Clock     🔢 Calculator │
│                                                         │
│   🤖 R Chat     🎤 Voice     🌍 Translate 📝 Notes     │
│                                                         │
│   ⚙️ Settings   📶 WiFi      🔵 Bluetooth 🔋 Battery   │
│                                                         │
│   💡 GPIO       💻 Terminal  🔌 Network   📊 System    │
│                                                         │
├─────────────────────────────────────────────────────────┤
│           ◀ Back      ● Home      ▢ Recent             │
└─────────────────────────────────────────────────────────┘
```

### Launch

```bash
r-os                    # Material theme
r-os --theme amoled     # AMOLED black
r-os --theme light      # Light theme
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `t` | Cycle themes |
| `n` | Notifications panel |
| `h` | Home |
| `Esc` | Back |
| `q` | Quit |

### Raspberry Pi Setup

```bash
# One-command installer
curl -sSL https://raw.githubusercontent.com/raym33/r/main/r_os/rpi/install.sh | bash
```

📖 **[Full R OS Documentation](r_os/README.md)**

---

## Distributed AI (Apple Silicon Cluster)

Run large language models (70B+) across multiple Apple Silicon Macs. Similar to [exo](https://github.com/exo-explore/exo), but integrated with R CLI's skill ecosystem.

```
┌──────────────────────────────────────────────────────────────┐
│                 5-Mac Cluster for Llama 70B                  │
├──────────────────────────────────────────────────────────────┤
│  Mac Mini 1    Mac Mini 2    Mac Mini 3    Mac Mini 4       │
│   M4 16GB       M4 16GB       M4 16GB       M4 16GB         │
│  Layers 0-13   Layers 14-27  Layers 28-41  Layers 42-55     │
│      │              │              │              │          │
│      └──────────────┴──────────────┴──────────────┘          │
│                            │                                 │
│                            ▼                                 │
│                    ┌──────────────┐                          │
│                    │ MacBook M4   │                          │
│                    │    24GB      │                          │
│                    │ Layers 56-79 │ ──▶ Output               │
│                    └──────────────┘                          │
└──────────────────────────────────────────────────────────────┘
```

### Quick Start

```bash
# Install with MLX support
pip install r-cli-ai[mlx,p2p]

# On each Mac, start the server
r serve --host 0.0.0.0 --port 8765

# Add nodes to cluster (from coordinator)
curl -X POST http://localhost:8765/v1/distributed/nodes \
  -d '{"host": "192.168.1.101", "port": 8765, "name": "mac-mini-1"}'

# Load 70B model across cluster
curl -X POST http://localhost:8765/v1/distributed/models/load \
  -d '{"model_name": "mlx-community/Meta-Llama-3.1-70B-Instruct-4bit"}'

# Generate text
curl -X POST http://localhost:8765/v1/distributed/generate \
  -d '{"prompt": "Explain quantum computing:", "max_tokens": 500}'
```

### Performance (5x M4 Macs, 70B model)

| Network | Est. Tokens/sec |
|---------|-----------------|
| 10 GbE | 8-15 |
| 1 GbE | 5-10 |
| WiFi 6 | 2-5 |

### R CLI vs exo

| | R CLI | exo |
|--|-------|-----|
| **Skills** | 74 integrated | Inference only |
| **Hardware** | Apple Silicon | Apple + NVIDIA |
| **RAG** | Built-in | None |
| **Voice** | Whisper + TTS | None |
| **API** | REST | gRPC |

📖 **[Full Distributed AI Documentation](docs/DISTRIBUTED_AI.md)**

---

## P2P Distributed Agents

Multiple R CLI instances can discover each other and collaborate on tasks.

```bash
# Discover peers on local network (mDNS)
r chat "discover peers on the network"

# Or add manually
r chat "add peer at 192.168.1.50"

# Execute task on remote peer
r chat "ask mac-mini-2 to generate a PDF report"

# Share context/memory
r chat "sync my conversation history with mac-mini-2"
```

### Features

- **Auto-discovery**: mDNS/Bonjour on LAN
- **Manual peers**: Add by IP for internet connections
- **Security**: Approval required for new peers
- **Skill sharing**: Access remote skills
- **Context sync**: Share conversation memory

📖 **[Full P2P Documentation](docs/P2P_AGENTS.md)**

---

## All 76 Skills

### 📄 Documents
`pdf` · `latex` · `markdown` · `pdftools` · `template` · `resume` · `changelog`

### 💻 Code & Data
`code` · `sql` · `json` · `yaml` · `csv` · `regex` · `schema` · `diff`

### 🤖 AI & Knowledge
`rag` · `multiagent` · `translate` · `faker` · `distributed_ai` · `p2p`

### 🎨 Media
`ocr` · `voice` · `design` · `image` · `video` · `audio` · `screenshot` · `qr` · `barcode`

### 📁 Files
`fs` · `archive` · `clipboard` · `env`

### 📅 Productivity
`calendar` · `email` · `ical` · `vcard`

### 🔧 DevOps
`git` · `docker` · `ssh` · `http` · `web` · `network` · `system` · `metrics`

### 🔍 Dev Tools
`logs` · `benchmark` · `openapi` · `cron` · `jwt`

### 📝 Text
`text` · `html` · `xml` · `url` · `ip` · `encoding`

### 🔢 Data
`datetime` · `color` · `math` · `currency` · `crypto` · `semver` · `mime`

### 🌐 Web
`rss` · `sitemap` · `manifest` · `hublab` · `weather`

### 🔌 Hardware (R OS)
`gpio` · `bluetooth` · `wifi` · `power` · `android`

### 🧩 Extensions
`plugin`

---

## REST API

```bash
# Start server
r serve --port 8765

# Chat (OpenAI-compatible)
curl -X POST http://localhost:8765/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}]}'

# Call skill directly
curl -X POST http://localhost:8765/v1/skills/call \
  -d '{"skill": "pdf", "tool": "generate_pdf", "arguments": {"content": "Hello"}}'
```

**Swagger UI:** http://localhost:8765/docs

---

## Configuration

```yaml
# ~/.r-cli/config.yaml
llm:
  backend: ollama
  model: qwen3:4b
  base_url: http://localhost:11434/v1

ui:
  theme: ps2  # ps2, matrix, minimal, retro

skills:
  disabled: []  # Skills to disable
```

---

## Create Custom Skills

```python
# ~/.r-cli/skills/my_skill.py
from r_cli.core.agent import Skill
from r_cli.core.llm import Tool

class MySkill(Skill):
    name = "my_skill"
    description = "My custom skill"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="my_function",
                description="Does something useful",
                parameters={"type": "object", "properties": {"input": {"type": "string"}}},
                handler=self.my_function,
            )
        ]

    def my_function(self, input: str) -> str:
        return f"Processed: {input}"
```

---

## Development

```bash
git clone https://github.com/raym33/r.git
cd r
pip install -e ".[dev]"
pytest tests/ -v
ruff check . && ruff format .
```

---

## Links

- [Complete Documentation](docs/COMPLETE_GUIDE.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Report Issues](https://github.com/raym33/r/issues)
- [PyPI Package](https://pypi.org/project/r-cli-ai/)

---

## Honest Limitations

- **Sandboxing is basic** - Skills run with your user permissions. Working on better isolation.
- **Small models (4B) sometimes pick the wrong tool** - Larger models (7B+) work better.
- **It's a tool layer, not magic** - Prompt quality still matters.
- **Some skills need external dependencies** - OCR needs Tesseract, voice needs Whisper, etc.

---

## License

MIT License

---

<div align="center">

**R CLI** - A tool orchestrator for local LLMs.

Created by [Ramón Guillamón](https://x.com/learntouseai)

</div>
