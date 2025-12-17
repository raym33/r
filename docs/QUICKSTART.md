# R CLI Quick Start Guide

Get R CLI running in 5 minutes with your local LLM.

## 1. Install R CLI

```bash
pip install r-cli-ai
```

## 2. Set Up Your Local LLM

### Option A: LM Studio (Recommended)

1. Download [LM Studio](https://lmstudio.ai/)
2. Download a model (recommended: `Qwen 2.5 7B` or `Gemma 3 12B`)
3. Click "Start Server" (default port: 1234)
4. Verify it's running:
   ```bash
   curl http://localhost:1234/v1/models
   ```

### Option B: Ollama

1. Install [Ollama](https://ollama.ai/)
2. Pull a model:
   ```bash
   ollama pull qwen2.5:7b
   ```
3. Ollama runs automatically on port 11434

## 3. Configure R CLI

Create `~/.r-cli/config.yaml`:

### For LM Studio:
```yaml
llm:
  backend: auto
  base_url: http://localhost:1234/v1
  model: auto  # Will use the model loaded in LM Studio
```

### For Ollama:
```yaml
llm:
  backend: ollama
  base_url: http://localhost:11434/v1
  model: qwen2.5:7b
```

## 4. Run R CLI

```bash
# Interactive mode
r

# Direct chat
r chat "What is Python?"

# Use a skill directly
r pdf "My document content"
```

## 5. Troubleshooting Context Overflow

If you get errors like "context length exceeded", use lite mode:

```bash
# Use minimal skills (7 skills, ~50 tools)
r --skills-mode lite chat "Hello"

# Or configure in config.yaml:
skills:
  mode: lite
```

**Skill Modes:**
| Mode | Skills | Tools | Best For |
|------|--------|-------|----------|
| `lite` | 7 | ~50 | Small context (4k-8k) |
| `standard` | 17 | ~120 | Medium context (8k-16k) |
| `full` | 74 | ~480 | Large context (32k+) |
| `auto` | varies | varies | Auto-detect |

## 6. Available Skills

```bash
# List all skills
r skills
```

Common skills:
- `datetime` - Current time, date parsing
- `math` - Calculations, statistics
- `pdf` - Generate PDF documents
- `sql` - Query CSV/databases
- `code` - Generate and analyze code
- `crypto` - Hashing, encoding
- `git` - Git operations
- `http` - API requests

## 7. API Server

Run R CLI as a REST API:

```bash
r serve --port 8765
```

Then access:
- Swagger UI: http://localhost:8765/docs
- Chat: POST http://localhost:8765/v1/chat
- Skills: GET http://localhost:8765/v1/skills

## Need Help?

- [Full Documentation](https://github.com/raym33/r#readme)
- [Report Issues](https://github.com/raym33/r/issues)
- [Changelog](https://github.com/raym33/r/blob/main/CHANGELOG.md)
