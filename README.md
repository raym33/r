# R CLI

Local AI Agent Runtime — **69 skills**, REST API daemon, 100% offline.

R CLI connects local LLMs (Ollama, LM Studio) to real system tools.
Chat in the terminal or integrate via REST API. Your data never leaves your machine.

```
╔═══════════════════════════════════════════════════════════════╗
║     ██████╗        ██████╗██╗     ██╗                        ║
║     ██╔══██╗      ██╔════╝██║     ██║                        ║
║     ██████╔╝█████╗██║     ██║     ██║                        ║
║     ██╔══██╗╚════╝██║     ██║     ██║                        ║
║     ██║  ██║      ╚██████╗███████╗██║                        ║
║     ╚═╝  ╚═╝       ╚═════╝╚══════╝╚═╝                        ║
╚═══════════════════════════════════════════════════════════════╝
```

**[Complete Documentation](docs/COMPLETE_GUIDE.md)** | **[Installation](#installation)** | **[Quick Start](#quick-start)** | **[All Skills](#all-69-skills)** | **[API Server](#api-server-daemon-mode)**

## Features

- **100% Local** - Your data never leaves your machine
- **69 Skills** - PDF, SQL, code, voice, design, RAG, HubLab, and 60+ more utilities
- **REST API Daemon** - Run as a server for IDE/app integration
- **PS2/Matrix UI** - Retro terminal animations
- **Built-in RAG** - Persistent knowledge base with ChromaDB
- **Streaming** - Real-time response display
- **Extensible** - Create your own skills or install plugins
- **Free** - No paid APIs or subscriptions

## Requirements

- Python 3.10+
- [LM Studio](https://lmstudio.ai/) or [Ollama](https://ollama.ai/)
- 8GB+ RAM (16GB+ recommended)

### Recommended Models

| Model | VRAM | Use Case |
|-------|------|----------|
| qwen3:4b | 4GB | Fast, simple tasks |
| Qwen2.5-7B | 8GB | Balanced |
| Qwen2.5-32B | 20GB | High quality |
| DeepSeek-Coder | 16GB | Code specialized |

## Installation

### From PyPI

```bash
# Basic installation
pip install r-cli-ai

# With all features
pip install r-cli-ai[all]

# Individual extras
pip install r-cli-ai[rag]      # Semantic search
pip install r-cli-ai[audio]    # Voice mode
pip install r-cli-ai[design]   # Image generation
pip install r-cli-ai[postgres] # PostgreSQL support
```

### From Source

```bash
git clone https://github.com/raym33/r.git
cd r
pip install -e .
```

## Quick Start

### 1. Start your LLM server

**Ollama:**
```bash
ollama pull qwen3:4b
ollama serve
```

**LM Studio:**
1. Open LM Studio
2. Load a model
3. Start local server (port 1234)

### 2. Configure R CLI

```bash
mkdir -p ~/.r-cli
cat > ~/.r-cli/config.yaml << 'EOF'
llm:
  backend: ollama
  model: qwen3:4b
  base_url: http://localhost:11434/v1
EOF
```

### 3. Run R CLI

```bash
# Interactive mode
r

# Direct chat
r chat "Explain what Python is"

# With streaming
r chat --stream "Write a haiku about coding"

# Start API server (daemon mode)
r serve --port 8765
```

## API Server (Daemon Mode)

R CLI can run as a REST API server for integration with IDEs, scripts, and other applications.

### Start the Server

```bash
# Default: localhost:8765
r serve

# Custom port
r serve --port 8080

# Listen on all interfaces
r serve --host 0.0.0.0

# Development mode with auto-reload
r serve --reload
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/health` | GET | Simple health status |
| `/v1/status` | GET | Detailed status (LLM, skills, uptime) |
| `/v1/chat` | POST | Chat completions (OpenAI-compatible, streaming) |
| `/v1/skills` | GET | List all skills and tools |
| `/v1/skills/{name}` | GET | Get skill details |
| `/v1/skills/call` | POST | Direct tool invocation |

### API Documentation

When the server is running, visit:
- **Swagger UI**: http://localhost:8765/docs
- **ReDoc**: http://localhost:8765/redoc

### Example: Chat Request

```bash
curl -X POST http://localhost:8765/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

### Example: Call a Tool Directly

```bash
curl -X POST http://localhost:8765/v1/skills/call \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "pdf",
    "tool": "generate_pdf",
    "arguments": {"content": "Hello World", "output": "test.pdf"}
  }'
```

## All 69 Skills

### Document Generation & Processing

| Skill | Description | Tools |
|-------|-------------|-------|
| `pdf` | Generate PDF documents | generate_pdf, merge_pdf |
| `latex` | Compile LaTeX to PDF | compile_latex, latex_preview |
| `resume` | Summarize documents | summarize_text, extract_key_points |
| `markdown` | Markdown processing | md_to_html, md_lint, md_toc |
| `pdftools` | Advanced PDF ops | split, merge, compress, watermark |
| `template` | Jinja2 rendering | render_template, render_string |
| `changelog` | Keep a Changelog format | parse, generate, add_entry |

### Code & Data

| Skill | Description | Tools |
|-------|-------------|-------|
| `code` | Generate and run code | generate_code, run_code, explain_code |
| `sql` | Query databases (SQLite, PostgreSQL, DuckDB) | execute, schema, explain |
| `json` | JSON manipulation | parse, query, transform, diff |
| `yaml` | YAML operations | parse, validate, convert |
| `csv` | CSV processing | read, write, query, transform |
| `regex` | Regular expressions | match, replace, extract, test |
| `schema` | JSON Schema validation | validate, generate, document |
| `diff` | Text/file comparison | diff_texts, diff_files, patch |

### AI & Knowledge

| Skill | Description | Tools |
|-------|-------------|-------|
| `rag` | Semantic search (ChromaDB) | add, query, list, delete |
| `multiagent` | Multi-agent orchestration | spawn, delegate, aggregate |
| `translate` | Text translation | translate_text, detect_language |
| `faker` | Random data generation | person, address, company, text |

### Media & Vision

| Skill | Description | Tools |
|-------|-------------|-------|
| `ocr` | Extract text from images | ocr_image, ocr_pdf, ocr_batch |
| `voice` | Speech-to-text + TTS | transcribe, speak, voice_clone |
| `design` | Image generation (SD) | generate_image, img2img |
| `screenshot` | Screen captures | capture, region, window |
| `image` | Image manipulation | resize, crop, convert, filter |
| `video` | Video processing (ffmpeg) | convert, trim, extract, merge |
| `audio` | Audio processing (ffmpeg) | convert, trim, normalize, mix |
| `qr` | QR code gen/read | generate_qr, read_qr |
| `barcode` | Barcode gen/read | generate, read, batch |

### File System & Archives

| Skill | Description | Tools |
|-------|-------------|-------|
| `fs` | File operations | list, read, write, search, copy |
| `archive` | ZIP/TAR/GZIP | create, extract, list, add |
| `clipboard` | System clipboard | copy, paste, clear, history |
| `env` | .env file management | get, set, load, export |

### Productivity & Communication

| Skill | Description | Tools |
|-------|-------------|-------|
| `calendar` | Local calendar (SQLite) | add_event, list_events, remind |
| `email` | Send emails (SMTP) | send, draft, template |
| `ical` | iCalendar (ICS) files | parse, create, generate |
| `vcard` | vCard (VCF) contacts | parse, create, merge |

### DevOps & System

| Skill | Description | Tools |
|-------|-------------|-------|
| `git` | Git operations | status, commit, branch, diff |
| `docker` | Container management | ps, logs, exec, build |
| `ssh` | Remote connections | connect, execute, transfer |
| `http` | HTTP/REST client | get, post, put, delete |
| `web` | Web scraping | fetch, extract, crawl |
| `network` | Network utilities | ping, dns, port_scan, interfaces |
| `system` | System info | cpu, memory, disk, processes |
| `metrics` | System metrics | cpu, memory, disk, network stats |

### Observability & Dev Workflow

| Skill | Description | Tools |
|-------|-------------|-------|
| `logs` | Log analysis | tail, search, explain_crash, diff |
| `benchmark` | Performance profiling | profile, compare, stress_test |
| `openapi` | OpenAPI integration | load_spec, call_endpoint, generate |
| `cron` | Cron expressions | parse, next_run, validate |
| `jwt` | JWT handling | decode, verify, generate |

### Text & String Utilities

| Skill | Description | Tools |
|-------|-------------|-------|
| `text` | Text processing | word_count, clean, case, truncate |
| `html` | HTML parsing | parse, clean, extract, to_text |
| `xml` | XML/XPath | parse, query, transform, validate |
| `url` | URL manipulation | parse, build, encode, decode |
| `ip` | IP address utilities | info, validate, range, geolocation |
| `encoding` | Text encoding | convert, detect, base64, hex |

### Data & Format Utilities

| Skill | Description | Tools |
|-------|-------------|-------|
| `datetime` | Date/time operations | parse, format, diff, timezone |
| `color` | Color conversion | hex_to_rgb, palette, contrast |
| `math` | Mathematical ops | evaluate, statistics, convert |
| `currency` | Currency conversion | convert, rates, format |
| `crypto` | Hashing & encoding | hash, password, encrypt, sign |
| `semver` | Semantic versioning | parse, compare, bump, validate |
| `mime` | MIME type detection | detect, extension, info |

### Web Standards

| Skill | Description | Tools |
|-------|-------------|-------|
| `rss` | RSS/Atom feeds | parse, generate, validate |
| `sitemap` | XML sitemaps | parse, generate, validate |
| `manifest` | Web app manifests | generate, validate, icons |

### Platform Integration

| Skill | Description | Tools |
|-------|-------------|-------|
| `hublab` | HubLab.dev UI capsules (8,150+) | search, browse, suggest, code |

### External Data

| Skill | Description | Tools |
|-------|-------------|-------|
| `weather` | Weather information | current, forecast, alerts |

### Extensibility

| Skill | Description | Tools |
|-------|-------------|-------|
| `plugin` | Plugin management | install, uninstall, list, create |

## Configuration

Full configuration options in `~/.r-cli/config.yaml`:

```yaml
llm:
  backend: ollama          # ollama, lm-studio, auto
  model: qwen3:4b
  base_url: http://localhost:11434/v1
  temperature: 0.7
  max_tokens: 4096
  request_timeout: 60.0    # Timeout for LLM requests
  max_context_tokens: 8192 # Max context window

ui:
  theme: ps2               # ps2, matrix, minimal, retro
  show_thinking: true
  show_tool_calls: true

rag:
  enabled: true
  chunk_size: 1000
  persist_directory: ~/.r-cli/vectordb

skills:
  mode: blacklist          # blacklist or whitelist
  disabled: []             # Skills to disable
  enabled: []              # Skills to enable (whitelist mode)
  require_confirmation:    # Skills requiring confirmation
    - ssh
    - docker
```

## Themes

```bash
r --theme ps2      # Blue PlayStation 2 style
r --theme matrix   # Green Matrix style
r --theme minimal  # Clean and simple
r --theme retro    # CRT vintage look
```

## Create Your Own Skill

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
                parameters={
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Input text"}
                    },
                    "required": ["input"]
                },
                handler=self.my_function,
            )
        ]

    def my_function(self, input: str) -> str:
        return f"Processed: {input}"
```

## Plugin System

Install community plugins:

```bash
# Install from GitHub
r plugin install https://github.com/user/r-cli-plugin

# List installed
r plugin list

# Create new plugin
r plugin create my_plugin --author "Your Name"
```

## Troubleshooting

### Command `r` not working

The `r` command may conflict with shell built-in. Solutions:

```bash
# Option 1: Use full path
/path/to/python/bin/r chat "hello"

# Option 2: Create alias in ~/.zshrc or ~/.bashrc
alias r="/path/to/python/bin/r"
source ~/.zshrc
```

### Connection errors

1. Verify LLM server is running:
   ```bash
   curl http://localhost:11434/v1/models  # Ollama
   curl http://localhost:1234/v1/models   # LM Studio
   ```

2. Check config:
   ```bash
   cat ~/.r-cli/config.yaml
   ```

## Development

```bash
# Clone
git clone https://github.com/raym33/r.git
cd r

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check .
ruff format .
```

## Contributing

1. Fork the repository
2. Create a branch (`git checkout -b feature/new-feature`)
3. Commit changes (`git commit -m 'Add new feature'`)
4. Push (`git push origin feature/new-feature`)
5. Open a Pull Request

## License

MIT License - Use R CLI however you want.

## Author

Created by Ramón Guillamón

- Twitter/X: [@learntouseai](https://x.com/learntouseai)
- Email: [learntouseai@gmail.com](mailto:learntouseai@gmail.com)

---

**R CLI** - Your AI, your machine, your rules.
