# R CLI

<div align="center">

**Your Local AI Operating System**

[![PyPI](https://img.shields.io/pypi/v/r-cli-ai?color=blue&label=PyPI)](https://pypi.org/project/r-cli-ai/)
[![Downloads](https://static.pepy.tech/badge/r-cli-ai)](https://pepy.tech/project/r-cli-ai)
[![CI](https://github.com/raym33/r/actions/workflows/ci.yml/badge.svg)](https://github.com/raym33/r/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**82 Skills** | **100% Private** | **Distributed AI** | **P2P Agents**

[Install](#install) | [Skills](#skills) | [Distributed AI](#distributed-ai) | [P2P Agents](#p2p-agents) | [Docs](docs/COMPLETE_GUIDE.md)

</div>

---

## What is R CLI?

R CLI connects your local LLM to 82 real system tools. Ask in natural language, the AI calls the right tool.

```
You: "Create a PDF report about Python"
 │
 ▼
R CLI → LLM decides → calls pdf.generate_pdf() → python_report.pdf
```

```bash
# Chat with tools
r chat "compress all python files into backup.zip"

# Diagnose your setup
r doctor
r status  # Alias

# Discover tools
r skills --search pdf

# Inspect any local project and get skill recommendations
r project inspect .

# Execute any of the 100+ tools directly, without an LLM
r tool math calculate --arg expression='sqrt(144)'

# SQL on CSV files
r sql sales.csv "SELECT product, SUM(revenue) FROM data GROUP BY product"

# Semantic search your docs
r rag --add ./docs/ && r rag --query "how does auth work"
```

---

## Install

```bash
# From GitHub (latest)
pip install git+https://github.com/raym33/r.git

# With Distributed AI + P2P (Apple Silicon)
pip install "r-cli-ai[mlx,p2p] @ git+https://github.com/raym33/r.git"
```

### Requirements

- Python 3.10+
- [Ollama](https://ollama.ai/) or [LM Studio](https://lmstudio.ai/) running locally

### Run

```bash
# Start Ollama first
ollama pull llama3.2 && ollama serve

# Then run R CLI
r                                 # Interactive mode with skill selector
r chat "explain quantum physics"  # Direct query
r serve                           # Start API server
```

### CLI Power Tools

```bash
# Machine-readable output for scripts and CI
r doctor --json
r config --json
r skills --json

# Print the active configuration path
r config --path

# Enable shell completion (add the matching line to your shell profile)
eval "$(r completion zsh)"
eval "$(r completion bash)"
r completion fish | source

# Pipe a prompt without animations or interactive menus
printf "summarize this repository" | r

# Build a PDF from Markdown, a literal argument, or stdin
r pdf --file report.md --template report --output report.pdf
printf '# Report\n\nGenerated from a pipe.' | r pdf --output report.pdf
```

---

## Project Intelligence

R can inspect a repository without uploading or reading its source contents:

```bash
r project inspect /path/to/project
r project inspect /path/to/project --json
r project init /path/to/project
```

It detects language stacks, Docker, document collections, data files, AI services,
web apps, and system services. The report recommends relevant skills and executable
commands for that project. `project init` creates a `.r-cli.yaml` profile containing
only the recommended skills.

Configuration priority is:

1. `R_CLI_CONFIG`
2. nearest `.r-cli.yaml` or `.r-cli/config.yaml`
3. `~/.r-cli/config.yaml`

## Universal Tool Runner

Every tool exposed by every skill is available from one consistent interface:

```bash
# Discover tools and schemas
r tool pdf
r tool pdf generate_pdf --schema

# Typed KEY=VALUE arguments (JSON values are decoded)
r tool math statistics --arg 'numbers=[1,2,3,4]'

# Full JSON arguments and machine-readable output
r tool pdftools pdf_info --params '{"file_path":"report.pdf"}' --json
```

This makes R useful in shell scripts and automation even when no LLM is running.

## Local Permissions

R classifies every tool call as `low`, `medium`, `high`, or `critical`.
High-risk actions require confirmation by default, including calls initiated by the LLM.
In pipes and CI they are denied unless approval is explicit.

```bash
# Understand a decision before running it
r permissions explain docker docker_run

# Review recent decisions
r permissions audit

# Inspect reliability and latency across CLI, agents, API, and MCP
r traces list
r traces summary
r traces export traces.csv

# Create, validate, and run a reproducible workflow
r workflow init report.yaml
r workflow validate report.yaml
r workflow run report.yaml --var multiplier=3

# Deliberately approve an automated action
r --yes tool code run_python --arg 'code=print("hello")'
```

Project or user configuration:

```yaml
security:
  mode: ask                # ask, strict, permissive
  confirm_risk: [high, critical]
  denied_skills: [power]
  denied_tools: [fs.delete_file]
  allowed_tools: [git.git_status]
  audit_enabled: true
  audit_path: audit.jsonl
```

Explicit deny rules always win over `--yes`. Audit records redact common secrets such as
passwords, tokens, API keys, credentials, and authorization headers.

Every tool execution also receives a trace ID, source, outcome, and duration. Use
`r traces list` to filter recent runs, `r traces summary` for success rate and P50/P95
latency, or `r traces export` to analyze the history as JSON or CSV.

## Workflows

Workflows compose registered R tools without granting arbitrary shell access:

```yaml
version: 1
name: calculation-report

variables:
  expression: 6 * 7
  multiplier: 2

steps:
  - id: calculate
    uses: math.calculate
    with:
      expression: "{{ vars.expression }}"

  - id: scale
    uses: math.calculate
    depends_on: [calculate]
    retry: 2
    with:
      expression: "{{ steps.calculate.result }} * {{ vars.multiplier }}"
```

Use `if` for conditional steps and `continue_on_error: true` for recoverable failures.
Templates run in a sandboxed Jinja environment and preserve native values. Every tool call
still passes through R's permission policy and appears in traces as
`workflow:<workflow-name>`.

```bash
r workflow validate workflow.yaml
r workflow run workflow.yaml --dry-run
r workflow run workflow.yaml --var expression='100 / 4' --json
```

## MCP Plugins

R can consume external Model Context Protocol servers over `stdio` using the official
Python SDK:

```bash
pip install 'r-cli-ai[mcp]'

r mcp add filesystem \
  --command npx \
  --arg -y \
  --arg @modelcontextprotocol/server-filesystem \
  --arg "$HOME/Documents"

r mcp list
r mcp tools filesystem
r mcp call filesystem read_file --arg path=README.md
```

Use quoted environment references for credentials so secrets remain outside YAML:

```bash
r mcp add private-api --command uvx --arg private-api-mcp \
  --env 'API_TOKEN=${PRIVATE_API_TOKEN}'
```

MCP calls use the same risk classification, confirmation, deny rules, secret redaction,
and audit trail as native tools. Set `mcp.auto_load: true` to expose configured MCP tools
to the chat agent automatically; it defaults to `false` so startup never launches external
processes unexpectedly.

## Skills

82 tools organized by category:

| Category | Skills |
|----------|--------|
| **Documents** | `pdf` `latex` `markdown` `template` `resume` `pdftools` `changelog` |
| **Code & Data** | `code` `sql` `json` `yaml` `csv` `regex` `schema` `diff` |
| **AI & Knowledge** | `rag` `multiagent` `translate` `distributed_ai` `p2p` |
| **Media** | `voice` `ocr` `image` `video` `audio` `screenshot` `qr` `barcode` |
| **DevOps** | `git` `docker` `ssh` `http` `web` `network` `system` `metrics` |
| **Productivity** | `calendar` `email` `clipboard` `archive` `ical` `vcard` |
| **Hardware** | `gpio` `bluetooth` `wifi` `power` `android` |

<details>
<summary><b>View all 82 skills</b></summary>

```
agimemory, agimemory_pg, android, archive, audio, autoresponder,
barcode, benchmark, bluetooth, calendar, changelog, clipboard,
code, color, cron, crypto, csv, currency, datetime, diff,
distributed_ai, docker, email, encoding, env, faker, fs, git,
gpio, html, http, hublab, ical, image, imagegen, ip, json, jwt,
latex, logs, manifest, markdown, math, metrics, mime, msoffice,
multiagent, network, ocr, openapi, p2p, pdf, pdftools, plugin,
power, qr, rag, realtime_voice, regex, resume, rss, schema,
screenshot, semver, sitemap, social, sql, ssh, system, template,
text, translate, url, vcard, video, voice, weather, web,
websearch, wifi, xml, yaml
```

</details>

---

## Distributed AI

Run 70B+ models across multiple Apple Silicon Macs using MLX. Like [exo](https://github.com/exo-explore/exo), but integrated with R CLI's 82 skills.

### Example: 5-Mac Cluster for Llama 70B

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
│  Total: 88GB unified memory → 70B 4-bit model fits          │
└─────────────────────────────────────────────────────────────┘
```

### Setup

```bash
# Install on each Mac
pip install "r-cli-ai[mlx,p2p] @ git+https://github.com/raym33/r.git"

# Start server on each Mac
r serve --host 0.0.0.0 --port 8765

# From coordinator Mac, add nodes
r chat "add node at 192.168.1.101"
r chat "add node at 192.168.1.102"
r chat "add node at 192.168.1.103"
r chat "add node at 192.168.1.104"

# Check cluster status
r chat "cluster status"

# Load 70B model distributed across cluster
r chat "load model mlx-community/Meta-Llama-3.1-70B-Instruct-4bit"

# Generate (uses all nodes)
r chat "explain quantum computing in detail"
```

### Performance

| Network | Tokens/sec (70B) |
|---------|------------------|
| 10 GbE  | 8-15            |
| 1 GbE   | 5-10            |
| WiFi 6  | 2-5             |

**[Full Distributed AI Guide](docs/DISTRIBUTED_AI.md)**

---

## P2P Agents

Multiple R CLI instances can discover each other and collaborate on tasks.

```bash
# Auto-discover peers on LAN (mDNS/Bonjour)
r chat "discover peers"

# Add remote peer manually
r chat "add peer at 192.168.1.50"

# List connected peers
r chat "list peers"

# Run task on remote peer
r chat "ask mac-mini-2 to generate a sales report PDF"

# Share conversation context
r chat "sync conversation with mac-mini-2"

# Find peers with specific skills
r chat "find peers with pdf skill"
```

### Features

- **mDNS Discovery** - Automatic peer discovery on LAN
- **Manual Peers** - Add peers by IP for internet connections
- **Approval System** - Must approve new peers before collaboration
- **Skill Sharing** - Access skills from remote peers
- **Context Sync** - Share conversation memory between instances

**[Full P2P Guide](docs/P2P_AGENTS.md)**

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

# Distributed AI endpoints
curl http://localhost:8765/v1/distributed/cluster
curl http://localhost:8765/v1/distributed/generate -d '{"prompt": "Hello"}'

# P2P endpoints
curl http://localhost:8765/v1/p2p/peers
curl http://localhost:8765/v1/p2p/discover
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
- [Distributed AI Guide](docs/DISTRIBUTED_AI.md)
- [P2P Agents Guide](docs/P2P_AGENTS.md)
- [Changelog](CHANGELOG.md)
- [Issues](https://github.com/raym33/r/issues)

---

## Limitations

- Skills run with your user permissions (sandboxing is basic)
- Small models (4B) may pick wrong tools; 7B+ recommended
- Some skills need dependencies (OCR needs Tesseract, voice needs Whisper)
- Distributed AI requires Apple Silicon Macs with MLX

---

<div align="center">

MIT License | Created by [Ramón Guillamón](https://x.com/learntouseai)

</div>
