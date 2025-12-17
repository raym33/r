# R CLI

<div align="center">

**Your Local AI Operating System**

[![PyPI](https://img.shields.io/pypi/v/r-cli-ai?color=blue&label=pip%20install%20r-cli-ai)](https://pypi.org/project/r-cli-ai/)
[![Downloads](https://static.pepy.tech/badge/r-cli-ai)](https://pepy.tech/project/r-cli-ai)
[![CI](https://github.com/raym33/r/actions/workflows/ci.yml/badge.svg)](https://github.com/raym33/r/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**76 Skills** | **100% Private** | **Distributed AI** | **P2P Agents**

[Get Started](#get-started) | [Skills](#skills) | [Distributed AI](#distributed-ai) | [P2P Agents](#p2p-agents) | [Docs](docs/COMPLETE_GUIDE.md)

</div>

---

## What is R CLI?

R CLI connects your local LLM to 76 real system tools. Ask in natural language, the AI calls the right tool.

```
You: "Create a PDF report about Python"
 │
 ▼
R CLI → LLM decides → calls pdf.generate_pdf() → python_report.pdf
```

```bash
# Chat with tools
r chat "compress all python files into backup.zip"

# SQL on CSV files
r sql sales.csv "SELECT product, SUM(revenue) FROM data GROUP BY product"

# Semantic search your docs
r rag --add ./docs/ && r rag --query "how does auth work"
```

**Why tools instead of shell access?**

| Shell Access | R CLI Tools |
|--------------|-------------|
| LLM guesses bash syntax | LLM sees typed schemas |
| No validation | Pydantic validates inputs |
| Unpredictable output | Structured JSON responses |
| Hard to add gates | Built-in approval system |

---

## Get Started

### 1. Install

```bash
# From GitHub (latest)
pip install git+https://github.com/raym33/r.git

# With extras (distributed AI + P2P)
pip install "r-cli-ai[mlx,p2p] @ git+https://github.com/raym33/r.git"

# Or install base + dependencies separately
pip install git+https://github.com/raym33/r.git
pip install mlx mlx-lm zeroconf cryptography httpx
```

### 2. Start your LLM

```bash
# Option A: Ollama
ollama pull llama3.2 && ollama serve

# Option B: LM Studio
# Download from lmstudio.ai, load any model
```

### 3. Run

```bash
r                              # Interactive mode
r chat "explain quantum physics"  # Single query
r serve                        # Start API server
```

---

## Skills

76 tools organized by category:

| Category | Skills |
|----------|--------|
| **Documents** | `pdf` `latex` `markdown` `template` `resume` |
| **Code & Data** | `code` `sql` `json` `yaml` `csv` `regex` `diff` |
| **AI** | `rag` `multiagent` `translate` `distributed_ai` `p2p` |
| **Media** | `voice` `ocr` `image` `video` `audio` `qr` |
| **DevOps** | `git` `docker` `ssh` `http` `network` `system` |
| **Productivity** | `calendar` `email` `clipboard` `archive` |
| **Hardware** | `gpio` `bluetooth` `wifi` `power` |

<details>
<summary><b>View all 76 skills</b></summary>

**Documents:** pdf, latex, markdown, pdftools, template, resume, changelog

**Code & Data:** code, sql, json, yaml, csv, regex, schema, diff

**AI & Knowledge:** rag, multiagent, translate, faker, distributed_ai, p2p

**Media:** ocr, voice, design, image, video, audio, screenshot, qr, barcode

**Files:** fs, archive, clipboard, env

**Productivity:** calendar, email, ical, vcard

**DevOps:** git, docker, ssh, http, web, network, system, metrics

**Dev Tools:** logs, benchmark, openapi, cron, jwt

**Text:** text, html, xml, url, ip, encoding

**Data:** datetime, color, math, currency, crypto, semver, mime

**Web:** rss, sitemap, manifest, hublab, weather

**Hardware:** gpio, bluetooth, wifi, power, android

**Extensions:** plugin

</details>

---

## Distributed AI

Run 70B+ models across multiple Apple Silicon Macs using MLX.

### Example: 5-Mac Cluster

```
┌─────────────────────────────────────────────────────────────┐
│                     Llama 70B (80 layers)                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Mac Mini 1     Mac Mini 2     Mac Mini 3     Mac Mini 4    │
│  M4 16GB        M4 16GB        M4 16GB        M4 16GB       │
│  Layers 0-15    Layers 16-31   Layers 32-47   Layers 48-63  │
│                                                             │
│                    MacBook Pro M4 24GB                      │
│                    Layers 64-79 + Output                    │
│                                                             │
│  Total: 88GB unified memory → 70B model fits                │
└─────────────────────────────────────────────────────────────┘
```

### Setup

```bash
# Install with MLX + P2P
pip install git+https://github.com/raym33/r.git
pip install mlx mlx-lm zeroconf cryptography httpx

# On each Mac
r serve --host 0.0.0.0 --port 8765

# From coordinator, add nodes
r chat "add node at 192.168.1.101"
r chat "add node at 192.168.1.102"
# ...

# Load model across cluster
r chat "load model mlx-community/Meta-Llama-3.1-70B-Instruct-4bit"

# Generate
r chat "explain quantum computing"
```

### Performance

| Network | Tokens/sec (70B) |
|---------|------------------|
| 10 GbE  | 8-15            |
| 1 GbE   | 5-10            |
| WiFi 6  | 2-5             |

**[Full Guide](docs/DISTRIBUTED_AI.md)**

---

## P2P Agents

R CLI instances can discover each other and collaborate.

```bash
# Auto-discover on LAN (mDNS)
r chat "discover peers"

# Add remote peer
r chat "add peer at 192.168.1.50"

# Run task on remote peer
r chat "ask mac-mini-2 to generate a sales report PDF"

# Share context
r chat "sync conversation with mac-mini-2"
```

### Features

- **mDNS Discovery** - Automatic on local network
- **Manual Peers** - Add by IP for internet
- **Approval System** - Must approve new peers
- **Skill Sharing** - Access remote skills
- **Context Sync** - Share conversation memory

**[Full Guide](docs/P2P_AGENTS.md)**

---

## REST API

```bash
# Start server
r serve --port 8765

# OpenAI-compatible chat
curl http://localhost:8765/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'

# Call skill directly
curl http://localhost:8765/v1/skills/call \
  -d '{"skill": "pdf", "tool": "generate_pdf", "arguments": {"content": "Hello"}}'
```

Swagger docs: http://localhost:8765/docs

---

## Configuration

```yaml
# ~/.r-cli/config.yaml
llm:
  backend: ollama          # or lmstudio
  model: llama3.2
  base_url: http://localhost:11434/v1

skills:
  disabled: []             # skills to disable
```

---

## Custom Skills

```python
# ~/.r-cli/skills/hello.py
from r_cli.core.agent import Skill
from r_cli.core.llm import Tool

class HelloSkill(Skill):
    name = "hello"
    description = "A greeting skill"

    def get_tools(self):
        return [Tool(
            name="greet",
            description="Greet someone",
            parameters={"type": "object", "properties": {"name": {"type": "string"}}},
            handler=self.greet,
        )]

    def greet(self, name: str) -> str:
        return f"Hello, {name}!"
```

---

## R OS (Experimental)

Terminal UI for Raspberry Pi. Not an actual OS.

```bash
pip install git+https://github.com/raym33/r.git
pip install textual
r-os
```

**[R OS Guide](r_os/README.md)**

---

## Development

```bash
git clone https://github.com/raym33/r.git
cd r
pip install -e ".[dev]"
pytest tests/
ruff check . && ruff format .
```

---

## Links

- [Documentation](docs/COMPLETE_GUIDE.md)
- [Changelog](CHANGELOG.md)
- [Issues](https://github.com/raym33/r/issues)
- [PyPI](https://pypi.org/project/r-cli-ai/)

---

## Limitations

- Skills run with your user permissions (sandboxing is basic)
- Small models (4B) may pick wrong tools; 7B+ recommended
- Some skills need dependencies (OCR needs Tesseract, voice needs Whisper)

---

<div align="center">

MIT License | Created by [Ramón Guillamón](https://x.com/learntouseai)

</div>
