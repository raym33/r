# R CLI 🚀

**Your Local AI Operating System** - 100% private, 100% offline, 100% yours.

R CLI is a terminal-based AI agent powered by local open source LLMs (LM Studio, Ollama). Inspired by Paul Klein's viral CEO CLI, but designed to run **completely offline**.

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

## ✨ Features

- 🔒 **100% Local** - Your data never leaves your machine
- 🚀 **Modular Skills** - PDF, SQL, code generation, summaries and more
- 🎮 **Epic UI** - PS2/Matrix-style terminal animations
- 🧠 **Built-in RAG** - Persistent knowledge base
- 🔌 **Extensible** - Create your own skills easily
- 💰 **Free** - No paid APIs or subscriptions

## 🛠️ Requirements

- Python 3.10+
- [LM Studio](https://lmstudio.ai/) or [Ollama](https://ollama.ai/)
- 16GB+ RAM (24GB VRAM recommended for large models)

### Recommended Models

| Model | VRAM | Use Case |
|-------|------|----------|
| Qwen2.5-7B | 8GB | Fast, simple tasks |
| Qwen2.5-32B | 20GB | Balanced |
| Qwen2.5-72B (Q4) | 24GB | Maximum quality |
| DeepSeek-Coder | 16GB | Code specialized |

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/raym33/r.git
cd r

# Install with pip
pip install -e .

# Or with uv (faster)
uv pip install -e .
```

## 🚀 Quick Start

### 1. Start your LLM server

**LM Studio:**
1. Open LM Studio
2. Load a model (e.g., Qwen2.5-32B-Instruct)
3. Start the local server (port 1234)

**Ollama:**
```bash
ollama run qwen2.5:32b
```

### 2. Launch R CLI

```bash
# Interactive mode
python -m r_cli.main

# Direct chat
python -m r_cli.main chat "Explain what machine learning is"

# Direct skills
python -m r_cli.main pdf "My AI report" --title "Q4 Report"
python -m r_cli.main sql sales.csv "SELECT * FROM data WHERE year = 2024"
python -m r_cli.main resume document.pdf --style detailed
python -m r_cli.main code "sorting function" --run
```

## 📚 Available Skills

| Skill | Description | Example |
|-------|-------------|---------|
| `pdf` | Generate PDF documents | `r pdf "content" --template business` |
| `resume` | Summarize long documents | `r resume file.pdf` |
| `sql` | SQL queries on CSVs/DBs | `r sql data.csv "SELECT *"` |
| `code` | Generate and execute code | `r code "hello world" --run` |
| `fs` | File operations | `r ls --pattern "*.py"` |

## ⚙️ Configuration

Create `~/.r-cli/config.yaml`:

```yaml
llm:
  provider: lm-studio  # or 'ollama'
  base_url: http://localhost:1234/v1
  model: local-model
  temperature: 0.7

ui:
  theme: ps2  # ps2, matrix, minimal, retro, cyberpunk

rag:
  enabled: true
  persist_directory: ~/.r-cli/vectordb
```

## 🎨 Themes

```bash
python -m r_cli.main --theme matrix   # Green Matrix style
python -m r_cli.main --theme ps2      # Blue PlayStation 2
python -m r_cli.main --theme minimal  # Clean and simple
python -m r_cli.main --theme retro    # CRT vintage
```

## 🔧 Create Your Own Skill

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
                parameters={...},
                handler=self.my_function,
            )
        ]

    def my_function(self, arg1: str) -> str:
        return f"Result: {arg1}"
```

## 🗺️ Roadmap

- [x] Agentic core with LM Studio/Ollama
- [x] Skills: PDF, SQL, Code, Resume, Filesystem
- [x] UI with PS2/Matrix animations
- [x] Persistent RAG
- [ ] Voice mode (Whisper + Piper TTS)
- [ ] Stable Diffusion integration for design
- [ ] Multi-agent orchestration
- [ ] Plugin marketplace

## 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -m 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Open a Pull Request

## 📄 License

MIT License - Use R CLI however you want.

## 👤 Author

Created by Ramón Guillamón

- Twitter/X: [@learntouseai](https://x.com/learntouseai)
- Email: [learntouseai@gmail.com](mailto:learntouseai@gmail.com)

---

**R CLI** - Because your AI should be yours. 🔒
