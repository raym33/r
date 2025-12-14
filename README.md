# R CLI

**Your Local AI Operating System** - 100% private, 100% offline, 100% yours.

R CLI is a terminal-based AI agent powered by local open source LLMs (LM Studio, Ollama). Run AI completely offline on your machine.

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

## Features

- **100% Local** - Your data never leaves your machine
- **24 Skills** - PDF, SQL, code, voice, design, RAG and more
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
pip install r-cli-ai[rag]     # Semantic search
pip install r-cli-ai[audio]   # Voice mode
pip install r-cli-ai[design]  # Image generation
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
# Note: 'r' may conflict with shell built-in, use full path or alias
alias r="/path/to/your/python/bin/r"

# Interactive mode
r

# Direct chat
r chat "Explain what Python is"

# With streaming
r chat --stream "Write a haiku about coding"
```

## All 24 Skills

### Document Generation

| Skill | Description | Example |
|-------|-------------|---------|
| `pdf` | Generate PDF documents | `r pdf "My report content" --title "Q4 Report"` |
| `latex` | Compile LaTeX to PDF | `r latex document.tex` |
| `resume` | Summarize documents | `r resume long_document.pdf --style brief` |

### Code & Data

| Skill | Description | Example |
|-------|-------------|---------|
| `code` | Generate and run code | `r code "fibonacci function" --lang python --run` |
| `sql` | Query CSV/databases | `r sql sales.csv "SELECT * FROM data WHERE year=2024"` |
| `json` | Parse and transform JSON | `r json data.json --query "$.users[*].name"` |

### AI & Knowledge

| Skill | Description | Example |
|-------|-------------|---------|
| `rag` | Semantic search | `r rag --add document.pdf` / `r rag --query "machine learning"` |
| `multiagent` | Multi-agent tasks | `r multiagent "research and summarize topic"` |
| `translate` | Text translation | `r translate "Hello world" --to es` |

### Media & Vision

| Skill | Description | Example |
|-------|-------------|---------|
| `ocr` | Extract text from images | `r ocr scanned.png --lang eng` |
| `voice` | Speech-to-text + TTS | `r voice --transcribe audio.mp3` / `r voice --speak "Hello"` |
| `design` | Generate images (SD) | `r design "cyberpunk city at night" --style anime` |
| `screenshot` | Capture screen | `r screenshot --region 0,0,800,600` |

### File System

| Skill | Description | Example |
|-------|-------------|---------|
| `fs` | File operations | `r fs --list "*.py"` / `r fs --read file.txt` |
| `archive` | Compress/extract | `r archive --create backup.zip folder/` |
| `clipboard` | Copy/paste | `r clipboard --copy "text"` / `r clipboard --paste` |

### Productivity

| Skill | Description | Example |
|-------|-------------|---------|
| `calendar` | Local calendar | `r calendar --add "Meeting" --date "2024-01-15 10:00"` |
| `email` | Send emails (SMTP) | `r email --to user@example.com --subject "Hello"` |

### DevOps & System

| Skill | Description | Example |
|-------|-------------|---------|
| `git` | Git operations | `r git --status` / `r git --commit "fix bug"` |
| `docker` | Container management | `r docker --ps` / `r docker --logs container_id` |
| `ssh` | Remote connections | `r ssh user@host "ls -la"` |
| `http` | HTTP requests | `r http --get https://api.example.com/data` |
| `web` | Web scraping | `r web --fetch https://example.com --extract text` |

### Extensibility

| Skill | Description | Example |
|-------|-------------|---------|
| `plugin` | Manage plugins | `r plugin install https://github.com/user/plugin` |

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

## Streaming Mode

Real-time response display:

```bash
r chat --stream "Write a long story"
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

# Enable/disable
r plugin enable my_plugin
r plugin disable my_plugin
```

Plugin structure:
```
~/.r-cli/plugins/my_plugin/
├── plugin.yaml       # Metadata
├── __init__.py       # Entry point
├── skill.py          # Skill implementation
└── requirements.txt  # Dependencies
```

## GPU Memory Management (Design Skill)

For Stable Diffusion image generation:

```bash
# Check VRAM status
r design --vram-status

# Generate image
r design "beautiful sunset" --steps 30

# Unload model to free VRAM
r design --unload
```

## Troubleshooting

### Command `r` not working

The `r` command conflicts with zsh built-in. Solutions:

```bash
# Option 1: Use full path
/path/to/python/bin/r chat "hello"

# Option 2: Create alias in ~/.zshrc
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

### ChromaDB errors

If you see deprecated ChromaDB errors, update:
```bash
pip install --upgrade chromadb
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
