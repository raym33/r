# R CLI Complete Guide

**Local AI Agent Runtime** - Tool orchestrator connecting local LLMs to system tools via function calling.

This comprehensive guide covers everything you can do with R CLI.

---

## Table of Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Basic Usage](#basic-usage)
4. [API Server (Daemon Mode)](#api-server-daemon-mode)
5. [R OS - Terminal UI (Experimental)](#r-os---terminal-ui-experimental)
6. [All 74 Skills](#all-74-skills)
7. [Interactive Mode](#interactive-mode)
8. [Direct Commands](#direct-commands)
9. [Plugin System](#plugin-system)
10. [Creating Custom Skills](#creating-custom-skills)
11. [Memory & RAG System](#memory--rag-system)
12. [Themes & UI](#themes--ui)
13. [Troubleshooting](#troubleshooting)
14. [API Reference](#api-reference)

---

## Installation

### From PyPI (Recommended)

```bash
# Basic installation
pip install r-cli-ai

# With semantic search (RAG with ChromaDB)
pip install r-cli-ai[rag]

# With voice mode (Whisper transcription + Piper TTS)
pip install r-cli-ai[audio]

# With image generation (Stable Diffusion)
pip install r-cli-ai[design]

# With OCR (Tesseract)
pip install r-cli-ai[ocr]

# Everything included
pip install r-cli-ai[all]

# R OS Terminal UI (experimental)
pip install r-cli-ai[simulator]

# Raspberry Pi with GPIO
pip install r-cli-ai[all-rpi]
```

### From Source

```bash
git clone https://github.com/raym33/r.git
cd r
pip install -e .

# With all optional dependencies
pip install -e ".[all]"
```

### Requirements

- Python 3.10+
- [Ollama](https://ollama.ai/) or [LM Studio](https://lmstudio.ai/)
- 8GB+ RAM (16GB+ recommended)
- macOS, Linux, or Windows

### Setting Up the LLM Backend

**Option 1: Ollama (Recommended)**

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Download a model
ollama pull qwen3:4b      # Fast, 4GB
ollama pull qwen2.5:7b    # Balanced, 8GB
ollama pull qwen2.5:32b   # High quality, 20GB

# Start the server
ollama serve
```

**Option 2: LM Studio**

1. Download from [lmstudio.ai](https://lmstudio.ai/)
2. Load a model (e.g., Qwen2.5-7B-Instruct)
3. Start the local server (default port: 1234)

---

## Configuration

### Config File Location

```
~/.r-cli/config.yaml
```

### Complete Configuration Options

```yaml
# LLM Configuration
llm:
  backend: ollama              # ollama, lm-studio, openai-compatible, auto
  model: qwen3:4b              # Model name
  base_url: http://localhost:11434/v1  # API endpoint
  api_key: not-needed          # API key (not needed for local)
  temperature: 0.7             # Creativity (0.0-1.0)
  max_tokens: 4096             # Max response length

  # Timeouts (seconds)
  request_timeout: 60.0        # Timeout for LLM requests
  skill_timeout: 120.0         # Timeout for skill execution
  connection_timeout: 10.0     # Timeout for initial connection

  # Token limits
  max_context_tokens: 8192     # Maximum context window
  token_warning_threshold: 0.8 # Warn at 80% of limit

  # Specialized models (optional)
  coder_model: null            # Model for code tasks
  vision_model: null           # Model for vision tasks

# RAG (Retrieval Augmented Generation)
rag:
  enabled: true
  chunk_size: 1000             # Text chunk size
  chunk_overlap: 200           # Overlap between chunks
  collection_name: r_cli_knowledge
  persist_directory: ~/.r-cli/vectordb

# User Interface
ui:
  theme: ps2                   # ps2, matrix, minimal, retro
  show_thinking: true          # Show agent reasoning
  show_tool_calls: true        # Show tool executions
  animation_speed: 0.05        # Animation speed

# Skills Configuration
skills:
  mode: blacklist              # blacklist or whitelist
  disabled: []                 # Skills to disable
  enabled: []                  # Skills to enable (whitelist mode)
  require_confirmation:        # Skills that need user confirmation
    - ssh
    - docker
    - email

# Directories
home_dir: ~/.r-cli
skills_dir: ~/.r-cli/skills
output_dir: ~/r-cli-output
```

### Quick Setup for Ollama

```bash
mkdir -p ~/.r-cli
cat > ~/.r-cli/config.yaml << 'EOF'
llm:
  backend: ollama
  model: qwen3:4b
  base_url: http://localhost:11434/v1
EOF
```

### Quick Setup for LM Studio

```bash
mkdir -p ~/.r-cli
cat > ~/.r-cli/config.yaml << 'EOF'
llm:
  backend: lm-studio
  model: local-model
  base_url: http://localhost:1234/v1
EOF
```

---

## Basic Usage

### Command Line Alias

The `r` command may conflict with shell built-ins. Set up an alias:

```bash
# Add to ~/.zshrc or ~/.bashrc
echo 'alias r="/path/to/python/bin/r"' >> ~/.zshrc
source ~/.zshrc

# Find your Python bin path
pip show r-cli-ai | grep Location
```

### Interactive Mode

```bash
r                    # Start interactive mode
r --theme matrix     # With Matrix theme
r --no-animation     # Without animations
```

### Direct Chat

```bash
r chat "What is Python?"
r chat "Explain machine learning in simple terms"
r chat --stream "Write a story about a robot"  # With streaming

# Start API server (daemon mode)
r serve --port 8765
```

### Direct Skill Execution

```bash
r pdf "My document content" --title "Report"
r code "fibonacci function" --lang python
r sql data.csv "SELECT * FROM data WHERE value > 100"
```

---

## API Server (Daemon Mode)

R CLI can run as a REST API server for integration with IDEs, scripts, and other applications.

### Starting the Server

```bash
# Default: localhost:8765
r serve

# Custom port
r serve --port 8080

# Listen on all interfaces
r serve --host 0.0.0.0

# Development mode with auto-reload
r serve --reload

# Multiple workers
r serve --workers 4
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/health` | GET | Simple health status |
| `/v1/status` | GET | Detailed status (LLM connection, skills, uptime) |
| `/v1/chat` | POST | Chat completions (OpenAI-compatible, supports streaming) |
| `/v1/skills` | GET | List all skills and their tools |
| `/v1/skills/{name}` | GET | Get details about a specific skill |
| `/v1/skills/call` | POST | Direct tool invocation |

### API Documentation

When the server is running, interactive documentation is available at:
- **Swagger UI**: http://localhost:8765/docs
- **ReDoc**: http://localhost:8765/redoc

### Example: Chat Request

```bash
# Non-streaming
curl -X POST http://localhost:8765/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'

# Streaming
curl -X POST http://localhost:8765/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Tell me a story"}],
    "stream": true
  }'
```

### Example: Direct Tool Call

```bash
curl -X POST http://localhost:8765/v1/skills/call \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "pdf",
    "tool": "generate_pdf",
    "arguments": {"content": "Hello World", "output": "test.pdf"}
  }'
```

### Example: List All Skills

```bash
curl http://localhost:8765/v1/skills | jq
```

### Running as a Service

**macOS (launchd):**
```bash
cp services/com.rcli.agent.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.rcli.agent.plist

# Check status
launchctl list | grep rcli

# Stop
launchctl unload ~/Library/LaunchAgents/com.rcli.agent.plist
```

**Linux (systemd):**
```bash
sudo cp services/r-cli.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable r-cli
sudo systemctl start r-cli

# Check status
sudo systemctl status r-cli

# View logs
journalctl -u r-cli -f
```

---

## R OS - Terminal UI (Experimental)

R OS is a terminal-based interface (TUI) for R CLI built with [Textual](https://textual.textualize.io/). It provides an Android-like visual experience in the terminal.

**Note:** This is NOT an operating system. It's a TUI that runs on top of your existing OS.

### Launch

```bash
# Install
pip install r-cli-ai[simulator]

# Run
r-os                    # Material theme (default)
r-os --theme amoled     # AMOLED black theme
r-os --theme light      # Light theme
```

### Interface

```
┌─────────────────────────────────────────────────────────┐
│ ▁▂▄█ 📶 R OS          12:45          🔋 85%             │
├─────────────────────────────────────────────────────────┤
│   💬 Messages   📞 Phone     📧 Email     🌐 Browser   │
│   📷 Camera     🖼️ Gallery   🎵 Music     🎬 Video     │
│   📁 Files      📅 Calendar  ⏰ Clock     🔢 Calculator │
│   🤖 R Chat     🎤 Voice     🌍 Translate 📝 Notes     │
│   ⚙️ Settings   📶 WiFi      🔵 Bluetooth 🔋 Battery   │
│   💡 GPIO       💻 Terminal  🔌 Network   📊 System    │
├─────────────────────────────────────────────────────────┤
│           ◀ Back      ● Home      ▢ Recent             │
└─────────────────────────────────────────────────────────┘
```

### Features

- **24 App Icons** - Each launching R CLI skills
- **Real-time Status Bar** - Clock, battery, WiFi indicator
- **3 Themes** - Material, AMOLED, Light
- **Keyboard Navigation** - Full keyboard support
- **Quick Settings Panel** - Toggle WiFi, Bluetooth, etc.

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `t` | Cycle themes (Material → AMOLED → Light) |
| `n` | Toggle notifications/quick settings |
| `h` | Go to home screen |
| `Esc` | Go back |
| `q` | Quit simulator |

### Hardware Skills

R OS includes 5 hardware control skills:

| Skill | Description | Example |
|-------|-------------|---------|
| `gpio` | Raspberry Pi GPIO | `r gpio write 17 1` |
| `bluetooth` | Bluetooth devices | `r bluetooth scan` |
| `wifi` | WiFi networks | `r wifi connect "MyNet" "pass"` |
| `power` | Power management | `r power brightness 70` |
| `android` | Android via ADB | `r android sms "+123" "Hello"` |

### Raspberry Pi Setup

```bash
# One-command installer
curl -sSL https://raw.githubusercontent.com/raym33/r/main/r_os/rpi/install.sh | bash

# Or manual
pip install r-cli-ai[all-rpi]
```

### Voice Interface

R OS supports hands-free operation:

```python
from r_cli.core.voice_interface import create_voice_interface

voice = create_voice_interface(config={
    "wake_word": "hey_r",
    "stt": "whisper",
    "tts": "piper"
})
voice.run()
```

**[Full R OS Documentation](../r_os/README.md)**

---

## All 74 Skills

### 1. PDF Skill

Generate PDF documents from text.

```bash
# Basic usage
r pdf "This is my document content"

# With options
r pdf "Report content" --title "Q4 Report" --author "John Doe"
r pdf "Meeting notes" --template business
r pdf "$(cat notes.txt)" --output ~/Documents/notes.pdf
```

**In chat:**
```
▶ Generate a PDF with a summary of Python features
▶ Create a PDF report about climate change
```

### 2. LaTeX Skill

Compile LaTeX documents to professional PDFs.

```bash
# Compile a .tex file
r latex document.tex

# With output path
r latex thesis.tex --output ~/Documents/thesis.pdf
```

**In chat:**
```
▶ Compile my LaTeX document at ~/paper.tex
▶ Create a LaTeX document about quantum physics and compile it
```

### 3. Code Skill

Generate, analyze, and execute code.

```bash
# Generate code
r code "sorting algorithm" --lang python
r code "REST API client" --lang javascript
r code "binary search tree" --lang rust

# Generate and run
r code "hello world" --lang python --run

# Analyze existing code
r code --analyze ~/project/main.py
```

**In chat:**
```
▶ Write a Python function to calculate prime numbers
▶ Create a JavaScript async function to fetch data from an API
▶ Analyze the code in ~/myproject/app.py
```

### 4. SQL Skill

Query CSV files and databases using natural language.

```bash
# Query a CSV file
r sql sales.csv "SELECT * FROM data"
r sql customers.csv "SELECT name, email FROM data WHERE country = 'USA'"
r sql orders.csv "SELECT product, SUM(quantity) FROM data GROUP BY product"

# Query a SQLite database
r sql database.db "SELECT * FROM users WHERE active = 1"

# Natural language queries
r sql data.csv "show me the top 10 products by revenue"
```

**In chat:**
```
▶ Query sales.csv and show total revenue by month
▶ Find all customers from the CSV who made purchases over $1000
```

### 5. Resume Skill

Summarize long documents and texts.

```bash
# Summarize a PDF
r resume document.pdf
r resume report.pdf --style brief
r resume thesis.pdf --style detailed

# Summarize text
r resume "$(cat long_article.txt)"

# Different styles
r resume paper.pdf --style bullets    # Bullet points
r resume paper.pdf --style executive  # Executive summary
```

**In chat:**
```
▶ Summarize the PDF at ~/Downloads/report.pdf
▶ Give me a brief summary of this research paper
```

### 6. File System (FS) Skill

Manage files and directories.

```bash
# List files
r fs --list "*.py"
r fs --list ~/Documents --recursive

# Read files
r fs --read ~/notes.txt

# Search in files
r fs --search "TODO" --path ~/project

# File info
r fs --info ~/Documents/report.pdf
```

**In chat:**
```
▶ List all Python files in my project
▶ Search for "API_KEY" in all files under ~/code
▶ Show me the contents of ~/.bashrc
```

### 7. OCR Skill

Extract text from images and scanned documents.

```bash
# Extract text from image
r ocr image.png
r ocr screenshot.jpg --lang eng

# Multiple languages
r ocr document.png --lang eng+spa

# From PDF (scanned)
r ocr scanned_document.pdf
```

**Supported languages:** eng, spa, fra, deu, ita, por, rus, chi_sim, jpn, kor, ara

**In chat:**
```
▶ Extract text from the image at ~/Downloads/receipt.jpg
▶ OCR this scanned document and translate it to English
```

### 8. Voice Skill

Speech-to-text transcription and text-to-speech synthesis.

```bash
# Transcribe audio (requires Whisper)
r voice --transcribe audio.mp3
r voice --transcribe meeting.wav --model medium

# Text-to-speech (requires Piper)
r voice --speak "Hello, this is R CLI"
r voice --speak "$(cat script.txt)" --output speech.wav

# Transcribe and summarize
r voice --transcribe lecture.mp3 --summarize
```

**In chat:**
```
▶ Transcribe the audio file at ~/recordings/meeting.mp3
▶ Read this text aloud: "Welcome to R CLI"
```

### 9. Design Skill

Generate images using Stable Diffusion.

```bash
# Generate image
r design "a sunset over mountains"
r design "cyberpunk city at night" --style anime
r design "portrait of a scientist" --steps 30

# With specific dimensions
r design "landscape painting" --width 1024 --height 768

# Check GPU status
r design --vram-status

# Unload model to free memory
r design --unload
```

**Styles:** realistic, anime, digital-art, oil-painting, watercolor, sketch

**In chat:**
```
▶ Generate an image of a futuristic spaceship
▶ Create an anime-style portrait of a wizard
```

### 10. Calendar Skill

Manage local calendar and tasks.

```bash
# View today's events
r calendar --today

# Add event
r calendar --add "Team meeting" --date "2024-01-15 10:00"
r calendar --add "Doctor appointment" --date "tomorrow 14:30"

# List events
r calendar --list --from "2024-01-01" --to "2024-01-31"

# Delete event
r calendar --delete <event_id>

# Tasks
r calendar --task "Buy groceries" --due "2024-01-10"
r calendar --tasks  # List all tasks
```

**In chat:**
```
▶ What do I have scheduled for today?
▶ Add a meeting with John tomorrow at 3pm
▶ Show me my tasks for this week
```

### 11. RAG Skill

Semantic search and knowledge base management.

```bash
# Add documents to knowledge base
r rag --add document.pdf
r rag --add ~/notes/*.txt
r rag --add "Important fact: Python was created in 1991"

# Search knowledge base
r rag --query "What is machine learning?"
r rag --search "python best practices"

# List indexed documents
r rag --list

# Clear knowledge base
r rag --clear
```

**In chat:**
```
▶ Add all PDFs from ~/research to my knowledge base
▶ Search my documents for information about neural networks
```

### 12. Multiagent Skill

Orchestrate multiple AI agents for complex tasks.

```bash
# Complex task with multiple steps
r multiagent "Research and write a report about AI trends"
r multiagent "Analyze code, find bugs, and suggest fixes"
```

**In chat:**
```
▶ Use multiple agents to research, summarize, and create a presentation about renewable energy
```

### 13. Plugin Skill

Manage community plugins.

```bash
# Install from GitHub
r plugin install https://github.com/user/r-cli-plugin

# List installed plugins
r plugin list

# Create new plugin
r plugin create my_plugin --author "Your Name" --description "My custom plugin"

# Enable/disable
r plugin enable my_plugin
r plugin disable my_plugin

# Uninstall
r plugin uninstall my_plugin
```

### 14. Web Skill

Web scraping and content extraction.

```bash
# Fetch webpage
r web --fetch https://example.com
r web --fetch https://news.site.com --extract text

# Extract specific elements
r web --fetch https://site.com --selector "article h1"

# Download page
r web --download https://example.com --output page.html
```

**In chat:**
```
▶ Scrape the main content from https://example.com/article
▶ Extract all links from this webpage
```

### 15. Git Skill

Git operations and repository management.

```bash
# Status
r git --status
r git --log --limit 10

# Commit
r git --add .
r git --commit "Fix bug in login"
r git --push

# Branches
r git --branch new-feature
r git --checkout main
r git --merge feature-branch

# Diff
r git --diff
r git --diff HEAD~1
```

**In chat:**
```
▶ Show me the git status of my project
▶ Create a new branch called "feature-auth" and switch to it
▶ Commit all changes with message "Add user authentication"
```

### 16. Docker Skill

Container management.

```bash
# List containers
r docker --ps
r docker --ps --all

# Container operations
r docker --start container_name
r docker --stop container_name
r docker --logs container_name --tail 100

# Images
r docker --images
r docker --pull nginx:latest

# Run container
r docker --run "nginx:latest" --name my-nginx --port 8080:80
```

**In chat:**
```
▶ List all running Docker containers
▶ Show the logs from my postgres container
▶ Start a new Redis container
```

### 17. SSH Skill

Remote server connections.

```bash
# Execute command
r ssh user@host "ls -la"
r ssh server.example.com "df -h"

# Interactive session (if supported)
r ssh --connect user@host

# With key
r ssh user@host "uptime" --key ~/.ssh/id_rsa

# Copy files
r ssh --scp local_file.txt user@host:/remote/path/
```

**In chat:**
```
▶ Connect to my server and check disk space
▶ Run "systemctl status nginx" on production server
```

### 18. HTTP Skill

Make HTTP requests.

```bash
# GET request
r http --get https://api.example.com/data
r http --get https://api.github.com/users/octocat

# POST request
r http --post https://api.example.com/users \
  --data '{"name": "John", "email": "john@example.com"}'

# With headers
r http --get https://api.example.com \
  --header "Authorization: Bearer token123"

# Download file
r http --download https://example.com/file.zip
```

**In chat:**
```
▶ Make a GET request to the GitHub API for user info
▶ POST data to my webhook endpoint
```

### 19. JSON Skill

Parse, query, and transform JSON data.

```bash
# Parse JSON file
r json data.json

# Query with JSONPath
r json data.json --query "$.users[*].name"
r json data.json --query "$.items[?(@.price > 100)]"

# Format/prettify
r json data.json --format

# Convert to other formats
r json data.json --to csv
r json data.json --to yaml
```

**In chat:**
```
▶ Parse the JSON file and extract all email addresses
▶ Convert this JSON to CSV format
```

### 20. Email Skill

Send emails via SMTP.

```bash
# Send email
r email --to recipient@example.com \
  --subject "Hello" \
  --body "This is a test email"

# With attachment
r email --to user@example.com \
  --subject "Report" \
  --body "Please find attached" \
  --attach report.pdf

# Configure SMTP (in config.yaml or environment)
# SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
```

**In chat:**
```
▶ Send an email to john@example.com with the project status
```

### 21. Translate Skill

Translate text between languages.

```bash
# Translate text
r translate "Hello world" --to spanish
r translate "Bonjour" --to english
r translate "$(cat document.txt)" --to german

# Detect language
r translate --detect "Ciao mondo"
```

**Supported languages:** english, spanish, french, german, italian, portuguese, russian, chinese, japanese, korean, arabic, and more.

**In chat:**
```
▶ Translate "Good morning" to Japanese
▶ Translate this paragraph to French
```

### 22. Clipboard Skill

System clipboard operations.

```bash
# Copy to clipboard
r clipboard --copy "Text to copy"
r clipboard --copy "$(cat file.txt)"

# Paste from clipboard
r clipboard --paste

# Clear clipboard
r clipboard --clear
```

**In chat:**
```
▶ Copy this code to clipboard
▶ What's currently in my clipboard?
```

### 23. Archive Skill

Compress and extract archives.

```bash
# Create archive
r archive --create backup.zip folder/
r archive --create data.tar.gz ~/Documents/data/

# Extract archive
r archive --extract backup.zip
r archive --extract data.tar.gz --output ~/extracted/

# List contents
r archive --list backup.zip

# Supported formats: zip, tar, tar.gz, tar.bz2, 7z
```

**In chat:**
```
▶ Create a zip archive of my project folder
▶ Extract the downloaded archive to ~/Downloads
```

### 24. Screenshot Skill

Capture screen content.

```bash
# Full screen
r screenshot

# Specific region
r screenshot --region 0,0,800,600

# Specific window (if supported)
r screenshot --window "Terminal"

# With delay
r screenshot --delay 5

# Output path
r screenshot --output ~/Pictures/capture.png
```

**In chat:**
```
▶ Take a screenshot of my screen
▶ Capture just the top-left corner (800x600)
```

### 25. Logs Skill (New!)

Log analysis, tailing, and crash diagnosis for developer workflows.

**Tools:**
- `tail_logs` - Tail log files or Docker containers
- `summarize_logs` - AI-powered log summarization
- `explain_crash` - Analyze crash logs and suggest fixes
- `diff_runs` - Compare test run outputs
- `watch_logs` - Watch logs in real-time with filtering

```bash
# In chat:
▶ Tail the last 100 lines of /var/log/nginx/error.log
▶ Explain the crash in my application logs
▶ Summarize errors from the Docker container logs
▶ Compare the pytest output from yesterday vs today
```

### 26. Benchmark Skill (New!)

Python profiling, command benchmarks, and performance comparison.

**Tools:**
- `profile_python` - Profile Python code with cProfile
- `benchmark_command` - Time shell commands
- `benchmark_python` - Benchmark Python functions
- `compare_benchmarks` - Compare two performance runs
- `memory_profile` - Analyze memory usage

```bash
# In chat:
▶ Profile the function in ~/myproject/slow_function.py
▶ Benchmark the command "python process_data.py"
▶ Compare performance before and after my changes
▶ Analyze memory usage of my Python script
```

### 27. OpenAPI Skill (New!)

Load OpenAPI specs, discover services, and call endpoints.

**Tools:**
- `load_openapi_spec` - Load an OpenAPI/Swagger spec
- `list_endpoints` - List all endpoints from a spec
- `describe_endpoint` - Get details about an endpoint
- `call_endpoint` - Make API calls based on spec
- `discover_services` - Find OpenAPI specs on common ports
- `generate_curl` - Generate curl commands for endpoints

```bash
# In chat:
▶ Load the OpenAPI spec from http://localhost:8000/openapi.json
▶ List all endpoints in the API
▶ Call the /users endpoint with GET method
▶ Generate curl commands for the POST /orders endpoint
▶ Discover services running on my localhost
```

### 28. CSV Skill

CSV file manipulation.

**Tools:** `read_csv`, `write_csv`, `query_csv`, `transform_csv`

```bash
# In chat:
▶ Read the CSV file and show the first 10 rows
▶ Filter customers.csv where country = "USA"
▶ Convert this CSV to JSON format
```

### 29. YAML Skill

YAML file operations.

**Tools:** `parse_yaml`, `validate_yaml`, `yaml_to_json`, `json_to_yaml`

```bash
# In chat:
▶ Validate my kubernetes config.yaml
▶ Convert this YAML to JSON
```

### 30. Markdown Skill

Markdown processing.

**Tools:** `md_to_html`, `md_lint`, `md_toc`, `md_format`

```bash
# In chat:
▶ Convert README.md to HTML
▶ Generate a table of contents for my documentation
▶ Check markdown formatting issues
```

### 31. Regex Skill

Regular expression utilities.

**Tools:** `regex_match`, `regex_replace`, `regex_extract`, `regex_test`

```bash
# In chat:
▶ Extract all email addresses from this text
▶ Replace all phone numbers with [REDACTED]
▶ Test if this string matches the pattern
```

### 32. Crypto Skill

Hashing, passwords, and encoding.

**Tools:** `hash_text`, `generate_password`, `encrypt`, `decrypt`, `sign`

```bash
# In chat:
▶ Generate a SHA-256 hash of this file
▶ Create a secure 32-character password
▶ Encode this text as base64
```

### 33. QR Skill

QR code generation and reading.

**Tools:** `generate_qr`, `read_qr`, `batch_qr`

```bash
# In chat:
▶ Generate a QR code for my website URL
▶ Read the QR code from this image
```

### 34. Video Skill

Video manipulation with ffmpeg.

**Tools:** `convert_video`, `trim_video`, `extract_audio`, `merge_videos`, `video_info`

```bash
# In chat:
▶ Convert video.mp4 to webm format
▶ Trim the video from 00:30 to 02:00
▶ Extract audio from this video
```

### 35. Math Skill

Mathematical operations.

**Tools:** `evaluate`, `statistics`, `convert_units`, `solve_equation`

```bash
# In chat:
▶ Calculate the mean and standard deviation of these numbers
▶ Convert 100 kilometers to miles
▶ Evaluate this mathematical expression
```

### 36. Network Skill

Network utilities.

**Tools:** `ping`, `dns_lookup`, `port_scan`, `interfaces`, `traceroute`

```bash
# In chat:
▶ Ping google.com and check latency
▶ What ports are open on localhost?
▶ Look up the DNS records for example.com
```

### 37. System Skill

System information and processes.

**Tools:** `cpu_info`, `memory_info`, `disk_info`, `processes`, `kill_process`

```bash
# In chat:
▶ Show system memory usage
▶ List running processes sorted by CPU
▶ Show disk space on all drives
```

### 38. Image Skill

Image manipulation with Pillow.

**Tools:** `resize_image`, `crop_image`, `convert_format`, `apply_filter`, `image_info`

```bash
# In chat:
▶ Resize image.png to 800x600
▶ Convert all JPGs to PNG format
▶ Apply a blur filter to this image
```

### 39. Audio Skill

Audio manipulation with ffmpeg.

**Tools:** `convert_audio`, `trim_audio`, `normalize`, `mix_audio`, `audio_info`

```bash
# In chat:
▶ Convert audio.wav to MP3
▶ Normalize the volume of this audio file
▶ Trim audio from 0:00 to 1:30
```

### 40. Text Skill

Text processing utilities.

**Tools:** `word_count`, `clean_text`, `change_case`, `truncate`, `extract_sentences`

```bash
# In chat:
▶ Count words in this document
▶ Clean up this text (remove extra whitespace)
▶ Convert this text to uppercase
```

### 41. DateTime Skill

Date and time operations.

**Tools:** `parse_date`, `format_date`, `date_diff`, `timezone_convert`, `add_time`

```bash
# In chat:
▶ Convert this timestamp to human readable format
▶ How many days between these two dates?
▶ Convert 3pm EST to PST
```

### 42. Color Skill

Color conversion and palettes.

**Tools:** `hex_to_rgb`, `rgb_to_hex`, `generate_palette`, `contrast_check`

```bash
# In chat:
▶ Convert #FF5733 to RGB
▶ Generate a 5-color palette from this base color
▶ Check contrast ratio between these colors
```

### 43. Weather Skill

Weather information.

**Tools:** `current_weather`, `forecast`, `alerts`

```bash
# In chat:
▶ What's the weather in New York?
▶ Show me the 5-day forecast for London
```

### 44. Currency Skill

Currency conversion.

**Tools:** `convert_currency`, `exchange_rates`, `format_currency`

```bash
# In chat:
▶ Convert 100 USD to EUR
▶ Show current exchange rates for USD
```

### 45. Barcode Skill

Barcode generation and reading.

**Tools:** `generate_barcode`, `read_barcode`, `batch_barcodes`

```bash
# In chat:
▶ Generate a barcode for product ID 12345
▶ Read the barcode from this image
```

### 46. PDFTools Skill

Advanced PDF operations.

**Tools:** `split_pdf`, `merge_pdfs`, `compress_pdf`, `watermark_pdf`, `pdf_to_images`

```bash
# In chat:
▶ Split this PDF into individual pages
▶ Merge all PDFs in this folder
▶ Add a watermark to my document
▶ Compress this PDF to reduce file size
```

### 47. Cron Skill

Cron expression utilities.

**Tools:** `parse_cron`, `next_runs`, `validate_cron`, `cron_to_text`

```bash
# In chat:
▶ When will this cron expression run next? "0 9 * * MON"
▶ Explain this cron expression in plain English
▶ Create a cron for "every weekday at 9am"
```

### 48. JWT Skill

JWT token handling.

**Tools:** `decode_jwt`, `verify_jwt`, `generate_jwt`, `jwt_info`

```bash
# In chat:
▶ Decode this JWT token
▶ When does this token expire?
▶ Generate a JWT with this payload
```

### 49. HTML Skill

HTML parsing and cleaning.

**Tools:** `parse_html`, `clean_html`, `extract_text`, `html_to_text`

```bash
# In chat:
▶ Extract all links from this HTML
▶ Clean this HTML and remove all scripts
▶ Convert HTML to plain text
```

### 50. XML Skill

XML parsing and XPath.

**Tools:** `parse_xml`, `xpath_query`, `transform_xml`, `validate_xml`

```bash
# In chat:
▶ Query this XML with XPath "//book/title"
▶ Validate this XML against the schema
▶ Transform XML to JSON
```

### 51. Template Skill

Jinja2 template rendering.

**Tools:** `render_template`, `render_string`, `validate_template`

```bash
# In chat:
▶ Render this template with these variables
▶ Create an email template for order confirmation
```

### 52. Env Skill

.env file management.

**Tools:** `get_env`, `set_env`, `load_env`, `export_env`

```bash
# In chat:
▶ Show all variables in .env
▶ Set DATABASE_URL in .env
▶ Load environment from .env.production
```

### 53. Faker Skill

Random data generation.

**Tools:** `fake_person`, `fake_address`, `fake_company`, `fake_text`, `fake_data`

```bash
# In chat:
▶ Generate 10 fake user profiles
▶ Create fake company data for testing
▶ Generate sample addresses
```

### 54. IP Skill

IP address utilities.

**Tools:** `ip_info`, `validate_ip`, `ip_range`, `geolocation`

```bash
# In chat:
▶ Get geolocation info for this IP
▶ Is this a valid IPv6 address?
▶ Calculate IP range for 192.168.1.0/24
```

### 55. URL Skill

URL parsing and manipulation.

**Tools:** `parse_url`, `build_url`, `encode_url`, `decode_url`

```bash
# In chat:
▶ Parse this URL and extract components
▶ URL encode this string
▶ Build a URL with these query parameters
```

### 56. Encoding Skill

Text encoding conversion.

**Tools:** `convert_encoding`, `detect_encoding`, `to_base64`, `from_base64`, `to_hex`

```bash
# In chat:
▶ Detect the encoding of this file
▶ Convert from UTF-8 to ISO-8859-1
▶ Encode this text as hex
```

### 57. Metrics Skill

System metrics collection.

**Tools:** `cpu_metrics`, `memory_metrics`, `disk_metrics`, `network_metrics`

```bash
# In chat:
▶ Show real-time CPU usage
▶ Monitor memory usage over time
▶ Track network bandwidth
```

### 58. Diff Skill

Text and file comparison.

**Tools:** `diff_texts`, `diff_files`, `apply_patch`, `create_patch`

```bash
# In chat:
▶ Compare these two files
▶ Show differences between these strings
▶ Create a patch file from the diff
```

### 59. Schema Skill

JSON Schema validation.

**Tools:** `validate_schema`, `generate_schema`, `document_schema`

```bash
# In chat:
▶ Validate this JSON against the schema
▶ Generate a JSON Schema from this data
▶ Document this schema in markdown
```

### 60. RSS Skill

RSS/Atom feed parsing.

**Tools:** `parse_feed`, `generate_feed`, `validate_feed`

```bash
# In chat:
▶ Parse this RSS feed and list articles
▶ Generate an RSS feed from this data
```

### 61. iCal Skill

iCalendar (ICS) files.

**Tools:** `parse_ical`, `create_event`, `generate_ics`

```bash
# In chat:
▶ Parse this .ics file and list events
▶ Create an ICS file for this meeting
```

### 62. vCard Skill

vCard (VCF) contacts.

**Tools:** `parse_vcard`, `create_vcard`, `merge_vcards`

```bash
# In chat:
▶ Parse this contact file
▶ Create a vCard for this person
▶ Merge multiple VCF files
```

### 63. SemVer Skill

Semantic versioning.

**Tools:** `parse_version`, `compare_versions`, `bump_version`, `validate_version`

```bash
# In chat:
▶ Bump the minor version of 1.2.3
▶ Compare these two versions
▶ Is this a valid semver?
```

### 64. MIME Skill

MIME type detection.

**Tools:** `detect_mime`, `extension_for_mime`, `mime_info`

```bash
# In chat:
▶ What's the MIME type of this file?
▶ What extension should I use for application/json?
```

### 65. Sitemap Skill

XML sitemap generation.

**Tools:** `parse_sitemap`, `generate_sitemap`, `validate_sitemap`

```bash
# In chat:
▶ Generate a sitemap for my website URLs
▶ Parse this sitemap and list all URLs
```

### 66. Manifest Skill

Web app manifest.

**Tools:** `generate_manifest`, `validate_manifest`, `manifest_icons`, `manifest_html_tags`

```bash
# In chat:
▶ Generate a manifest.json for my PWA
▶ Validate this manifest file
▶ Generate HTML meta tags for PWA
```

### 67. Changelog Skill

Changelog parsing and generation.

**Tools:** `parse_changelog`, `generate_entry`, `add_entry`, `changelog_init`

```bash
# In chat:
▶ Parse CHANGELOG.md and show latest version
▶ Add a new entry to the changelog
▶ Generate a changelog entry for version 1.2.0
```

### 68. HubLab Skill

HubLab.dev UI capsules integration (8,150+ components).

**Tools:** `hublab_search`, `hublab_capsule`, `hublab_categories`, `hublab_browse`, `hublab_suggest`, `hublab_code`, `hublab_stats`, `hublab_compose`

```bash
# In chat:
▶ Search HubLab for authentication components
▶ Find React components for dashboard layouts
▶ Suggest capsules for an e-commerce app
```

#### App Composition with HubLab

Generate complete applications from natural language descriptions:

```bash
▶ Create an inventory management app with login, dashboard, and product CRUD
```

R CLI will:
1. **Detect features** - auth, dashboard, crud, navigation
2. **Select capsules** - Find matching components from 8,150+ options
3. **Generate project** - Create Next.js 14 + Tailwind CSS structure
4. **Output code** - Ready-to-run application

**Feature Detection:** auth, dashboard, ecommerce, chat, social, forms, crud, media, navigation, notifications, settings, landing

**Platforms:** Web (Next.js), Mobile (React Native/Expo), Desktop (Tauri)

### 69. Plugin Skill

Plugin management.

**Tools:** `install_plugin`, `uninstall_plugin`, `list_plugins`, `create_plugin`

```bash
# In chat:
▶ Install plugin from GitHub URL
▶ List all installed plugins
▶ Create a new plugin template
```

### 70. GPIO Skill (Raspberry Pi)

Raspberry Pi GPIO pin control for hardware projects.

**Tools:** `gpio_setup`, `gpio_read`, `gpio_write`, `gpio_pwm_start`, `gpio_pwm_stop`, `gpio_servo`, `gpio_blink`

```bash
# Setup pin as output
r gpio setup 17 out

# Write HIGH/LOW
r gpio write 17 1
r gpio write 17 0

# Read pin state
r gpio read 18

# PWM control (50% duty cycle)
r gpio pwm 18 50

# Servo control (90 degrees)
r gpio servo 12 90

# Blink LED
r gpio blink 17 5 0.5
```

### 71. Bluetooth Skill

Bluetooth device management.

**Tools:** `bluetooth_scan`, `bluetooth_pair`, `bluetooth_connect`, `bluetooth_disconnect`, `bluetooth_power`

```bash
# Scan for devices
r bluetooth scan

# Pair with device
r bluetooth pair AA:BB:CC:DD:EE:FF

# Connect
r bluetooth connect AA:BB:CC:DD:EE:FF

# Disconnect
r bluetooth disconnect AA:BB:CC:DD:EE:FF

# Power on/off
r bluetooth power on
r bluetooth power off
```

### 72. WiFi Skill

WiFi network management.

**Tools:** `wifi_scan`, `wifi_connect`, `wifi_disconnect`, `wifi_status`, `wifi_hotspot`

```bash
# Scan for networks
r wifi scan

# Connect to network
r wifi connect "NetworkName" "password123"

# Check status
r wifi status

# Create hotspot
r wifi hotspot "R-OS-AP" "mypassword"

# Disconnect
r wifi disconnect
```

### 73. Power Skill

System power management.

**Tools:** `power_shutdown`, `power_reboot`, `power_brightness`, `power_volume`, `power_battery`

```bash
# Shutdown/Reboot
r power shutdown
r power reboot

# Screen brightness (0-100)
r power brightness 70

# Volume (0-100)
r power volume 50

# Battery status
r power battery
```

### 74. Android Skill

Android device control via ADB.

**Tools:** `android_sms`, `android_call`, `android_photo`, `android_notification`, `android_location`, `android_volume`, `android_launch`

```bash
# Send SMS
r android sms "+1234567890" "Hello from R OS!"

# Make call
r android call "+1234567890"

# Take photo
r android photo ~/photo.jpg

# Show notification
r android notify "Title" "Message body"

# Get location
r android location

# Set volume
r android volume 70

# Launch app
r android launch com.whatsapp
```

---

## Interactive Mode

### Starting Interactive Mode

```bash
r                        # Default
r --theme matrix         # With theme
r --no-animation         # No animations
```

### Interactive Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/clear` | Clear conversation history |
| `/exit` or `/quit` | Exit R CLI |
| `/skills` | List available skills |
| `/config` | Show configuration |
| `/theme <name>` | Change theme |

### Example Session

```
▶ Hello!
R: ¡Hola! ¿En qué puedo ayudarte?

▶ Generate a Python function to calculate factorial
R: [Generates code using code skill]

▶ Now create a PDF with that code
R: [Creates PDF using pdf skill]

▶ /clear
Conversation cleared.

▶ /exit
¡Hasta luego!
```

---

## Direct Commands

### Available Commands

```bash
r                      # Interactive mode
r chat "message"       # Direct chat
r pdf "content"        # Generate PDF
r code "description"   # Generate code
r sql file "query"     # SQL query
r config              # Show config
r demo                # UI demo
r skills              # List skills
```

### Global Options

```bash
--version, -v         # Show version
--theme, -t NAME      # Set theme (ps2, matrix, minimal, retro)
--no-animation        # Disable animations
--help                # Show help
```

### Chat Options

```bash
r chat "message"
r chat --stream "message"   # Enable streaming
```

---

## Plugin System

### Plugin Structure

```
~/.r-cli/plugins/my_plugin/
├── plugin.yaml         # Metadata
├── __init__.py         # Entry point
├── skill.py            # Skill implementation
└── requirements.txt    # Dependencies (optional)
```

### plugin.yaml Format

```yaml
name: my_plugin
version: 1.0.0
description: My custom plugin
author: Your Name
skills:
  - MyCustomSkill
dependencies:
  - requests>=2.28.0
```

### Skill Implementation

```python
# skill.py
from r_cli.core.agent import Skill
from r_cli.core.llm import Tool

class MyCustomSkill(Skill):
    name = "my_skill"
    description = "Does something custom"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="my_function",
                description="Performs a custom action",
                parameters={
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "string",
                            "description": "Input text"
                        }
                    },
                    "required": ["input"]
                },
                handler=self.my_function,
            )
        ]

    def my_function(self, input: str) -> str:
        # Your logic here
        return f"Processed: {input}"

    def execute(self, **kwargs) -> str:
        """Direct execution without LLM."""
        return self.my_function(kwargs.get("input", ""))
```

---

## Creating Custom Skills

### Basic Skill Template

```python
from r_cli.core.agent import Skill
from r_cli.core.llm import Tool

class MySkill(Skill):
    name = "myskill"
    description = "Description of what this skill does"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="tool_name",
                description="What this tool does",
                parameters={
                    "type": "object",
                    "properties": {
                        "param1": {"type": "string", "description": "First parameter"},
                        "param2": {"type": "integer", "description": "Second parameter"}
                    },
                    "required": ["param1"]
                },
                handler=self.tool_handler,
            )
        ]

    def tool_handler(self, param1: str, param2: int = 10) -> str:
        # Implementation
        return f"Result: {param1}, {param2}"
```

### Registering Custom Skills

Place your skill file in `~/.r-cli/skills/` and it will be automatically loaded.

---

## Memory & RAG System

### Memory Layers

R CLI uses a three-tier memory system:

1. **Short-term**: Current conversation context
2. **Medium-term**: Session history (persisted to `~/.r-cli/session.json`)
3. **Long-term**: ChromaDB vector database for semantic search

### Managing Memory

```bash
# Clear session history
rm ~/.r-cli/session.json

# Clear RAG database
rm -rf ~/.r-cli/vectordb

# In interactive mode
/clear   # Clears short-term memory
```

### Adding Documents to RAG

```bash
# Via command
r rag --add document.pdf

# Via chat
▶ Add ~/research/*.pdf to my knowledge base
```

---

## Themes & UI

### Available Themes

| Theme | Description |
|-------|-------------|
| `ps2` | Blue PlayStation 2 style (default) |
| `matrix` | Green Matrix/hacker style |
| `minimal` | Clean, simple interface |
| `retro` | Vintage CRT look |

### Setting Theme

```bash
# Command line
r --theme matrix

# In config.yaml
ui:
  theme: matrix

# In interactive mode
/theme matrix
```

### UI Features

- **Streaming**: Real-time response display
- **Animations**: Loading spinners, transitions
- **Panels**: Formatted response boxes
- **Syntax highlighting**: Code blocks
- **Markdown rendering**: Rich text formatting

---

## Troubleshooting

### LLM Connection Issues

```bash
# Check if Ollama is running
curl http://localhost:11434/v1/models

# Check if LM Studio is running
curl http://localhost:1234/v1/models

# Verify config
cat ~/.r-cli/config.yaml
```

### "r" Command Not Found

```bash
# The 'r' command conflicts with shell built-in
# Solution 1: Use full path
/path/to/python/bin/r

# Solution 2: Create alias
alias r="/path/to/python/bin/r"
```

### Context Too Long Error

```bash
# Clear session history
rm ~/.r-cli/session.json

# Or increase Ollama context
OLLAMA_CONTEXT_LENGTH=8192 ollama serve
```

### ChromaDB Errors

```bash
# Update ChromaDB
pip install --upgrade chromadb

# Clear vector database
rm -rf ~/.r-cli/vectordb
```

### Skill Not Loading

```bash
# Check for missing dependencies
pip install r-cli-ai[all]

# Check skill logs
r --debug
```

---

## API Reference

### LLMClient

```python
from r_cli.core.llm import LLMClient
from r_cli.core.config import Config

config = Config.load()
client = LLMClient(config)

# Simple chat
response = client.chat("Hello!")
print(response.content)

# With streaming
for chunk in client.chat_stream("Tell me a story"):
    print(chunk, end="")
```

### Agent

```python
from r_cli.core.agent import Agent
from r_cli.core.config import Config

config = Config.load()
agent = Agent(config)
agent.load_skills()

# Run a query
response = agent.run("Generate a PDF about Python")
print(response)

# Check available skills
print(agent.get_available_skills())
```

### Memory

```python
from r_cli.core.memory import Memory
from r_cli.core.config import Config

config = Config.load()
memory = Memory(config)

# Add to short-term memory
memory.add_short_term("User said hello", entry_type="user_input")

# Add document to RAG
doc_id = memory.add_document("Content here", metadata={"source": "file.txt"})

# Search RAG
results = memory.search("query", n_results=5)
```

---

## License

MIT License - Use R CLI however you want.

## Author

Created by Ramón Guillamón

- Twitter/X: [@learntouseai](https://x.com/learntouseai)
- Email: [learntouseai@gmail.com](mailto:learntouseai@gmail.com)
- GitHub: [github.com/raym33/r](https://github.com/raym33/r)

---

**R CLI** - Your AI, your machine, your rules.
