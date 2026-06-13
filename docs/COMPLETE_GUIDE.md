# R Complete Guide

R is a local-first runtime for running private AI agents with language models installed on
the user's own computer.

## Contents

1. [Install](#install)
2. [Configure a local model](#configure-a-local-model)
3. [Security baseline](#security-baseline)
4. [Chat and direct tools](#chat-and-direct-tools)
5. [Agent OS](#agent-os)
6. [Workflows](#workflows)
7. [Projects and configuration](#projects-and-configuration)
8. [Permissions and traces](#permissions-and-traces)
9. [MCP servers](#mcp-servers)
10. [Local API](#local-api)
11. [Platform notes](#platform-notes)
12. [Development](#development)

## Install

From GitHub:

```bash
python -m pip install "r-cli-ai @ git+https://github.com/raym33/r.git"
```

Optional feature groups:

```bash
python -m pip install "r-cli-ai[rag]"
python -m pip install "r-cli-ai[audio]"
python -m pip install "r-cli-ai[ocr]"
python -m pip install "r-cli-ai[mcp]"
python -m pip install "r-cli-ai[simulator]"
```

From source:

```bash
git clone https://github.com/raym33/r.git
cd r
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Requirements:

- Python 3.10 or newer;
- a local LLM runtime for model-backed agents;
- optional native programs for media, OCR, voice, hardware, or system integrations.

## Configure a Local Model

R requires loopback LLM endpoints while `security.local_only` is enabled.

Ollama:

```bash
ollama pull qwen2.5:7b
ollama serve
```

Configuration:

```yaml
# ~/.r-cli/config.yaml
llm:
  backend: ollama
  model: qwen2.5:7b
  base_url: http://127.0.0.1:11434/v1
  request_timeout: 60
  max_context_tokens: 8192

security:
  local_only: true
  network_access: false
  mode: ask
  confirm_risk: [high, critical]
  audit_enabled: true
  audit_path: audit.jsonl
```

LM Studio normally uses:

```yaml
llm:
  backend: lm-studio
  model: local-model
  base_url: http://127.0.0.1:1234/v1
```

Verify the installation:

```bash
r doctor
r os security
```

## Security Baseline

Default behavior:

- remote LLM endpoints are rejected;
- outbound tool networking is denied;
- network access requires explicit hosts;
- filesystem arguments may be restricted to allowed roots;
- MCP calls are critical-risk;
- non-loopback API binds require `--expose`;
- high-risk actions require approval;
- secrets are redacted from permission audit arguments.

Do not treat application-level path checks as a complete sandbox. Broad host capabilities
still run under the current user account. Read [SECURITY_MODEL.md](SECURITY_MODEL.md).

## Chat and Direct Tools

Interactive and direct chat:

```bash
r
r chat "Explain this project"
printf "Summarize this directory" | r
```

List skills:

```bash
r skills
r skills --search pdf
r skills --json
```

Inspect and execute tools without an LLM:

```bash
r tool math
r tool math calculate --schema
r tool math calculate --arg 'expression=2+3*4'
r tool pdftools pdf_info --params '{"file_path":"report.pdf"}' --json
```

Generate a PDF:

```bash
r pdf "Local report content" --output report.pdf
r pdf --file report.md --template report --output report.pdf
printf '# Report\n\nLocal content.' | r pdf --output report.pdf
```

## Agent OS

Create an agent manifest:

```bash
r os init researcher.yaml
```

Example:

```yaml
name: researcher
description: Analyze documents inside one project
kind: assistant
system_prompt: |
  You are a rigorous research agent.
  Cite local evidence and never invent missing facts.
skills: [fs, pdf, pdftools, rag, text]
network_access: false
filesystem_roots:
  - ./documents
```

Install and run:

```bash
r os agent install researcher.yaml
r os agent list
r os agent show researcher
r os run researcher "Compare the local reports"
```

Inspect the process table and events:

```bash
r os tasks
r os tasks --agent researcher --status completed
r os events
r os status
```

Broad capabilities require an explicit acknowledgement:

```yaml
skills: [code, git]
unsafe_capabilities: true
```

This acknowledgement does not create native sandboxing.

## Workflows

Create an example:

```bash
r workflow init workflow.yaml
```

Workflow structure:

```yaml
version: 1
name: local-report

variables:
  source: ./notes.txt

steps:
  - id: inspect
    uses: fs.read_file
    with:
      path: "{{ vars.source }}"

  - id: count
    uses: text.word_count
    depends_on: [inspect]
    with:
      text: "{{ steps.inspect.result }}"
```

Validate, plan, and run:

```bash
r workflow validate workflow.yaml
r workflow run workflow.yaml --dry-run
r workflow run workflow.yaml --var source=./other.txt --json
```

Supported step controls:

- `depends_on`;
- `if`;
- `retry`;
- `continue_on_error`;
- sandboxed native-value Jinja templates.

Workflow tool calls use the same permission and trace systems as interactive agents.

## Projects and Configuration

Inspect a repository:

```bash
r project inspect .
r project inspect . --json
r project init .
```

`project init` creates a project-local `.r-cli.yaml`.

Configuration precedence:

1. `R_CLI_CONFIG`;
2. nearest `.r-cli.yaml` or `.r-cli/config.yaml`;
3. `~/.r-cli/config.yaml`.

Show the active configuration:

```bash
r config
r config --json
r config --path
```

## Permissions and Traces

Explain effective risk:

```bash
r permissions explain fs read_file
r permissions explain docker docker_run --json
```

Review authorization decisions:

```bash
r permissions audit
r permissions audit --json
```

Review execution outcomes:

```bash
r traces list
r traces list --source agent-os:researcher
r traces summary
r traces export traces.csv
```

Security configuration:

```yaml
security:
  mode: ask
  local_only: true
  network_access: false
  allowed_hosts: []
  filesystem_roots: []
  allowed_skills: []
  denied_skills: [power]
  allowed_tools: [git.git_status]
  denied_tools: [fs.delete_file]
```

## MCP Servers

MCP servers are external processes and increase the trust boundary.

```bash
python -m pip install "r-cli-ai[mcp]"
r mcp add filesystem \
  --command npx \
  --arg -y \
  --arg @modelcontextprotocol/server-filesystem \
  --arg "$HOME/Documents"
r mcp list
r mcp tools filesystem
r mcp call filesystem read_file --arg path=README.md
```

MCP calls are classified as critical. `mcp.auto_load` is disabled by default.

Never place plaintext secrets directly in a manifest. Use environment references:

```bash
r mcp add private-api \
  --command uvx \
  --arg private-api-mcp \
  --env 'API_TOKEN=${PRIVATE_API_TOKEN}'
```

## Local API

Start the loopback API:

```bash
r serve
r serve --port 8080
```

Swagger UI is available at `http://127.0.0.1:8765/docs`.

R refuses public binds unless exposure is explicit:

```bash
r serve --host 0.0.0.0                  # refused
r serve --host 0.0.0.0 --expose         # explicit exposure
```

When exposing the API, configure authentication, TLS, CORS, and firewall rules.

## Platform Notes

### Linux

The core CLI and local model APIs are supported. Native sandboxing is planned.

### macOS

The core CLI is supported. MLX is optional on Apple Silicon. Native sandboxing is planned.

### Windows

Use PowerShell or Windows Terminal. Activate virtual environments with:

```powershell
.venv\Scripts\Activate.ps1
```

Windows-native sandboxing and broader CI coverage are roadmap items.

### Termux

Termux support is experimental:

```bash
pkg update
pkg install python git
python -m pip install "r-cli-ai @ git+https://github.com/raym33/r.git"
```

Local model availability depends on the device and runtime. Scoped storage and process
isolation remain roadmap work.

### Raspberry Pi

Use small local models and install only required optional dependencies. See
[the edge-device guide](../r_os/rpi/README.md).

## Development

```bash
python -m pip install -e ".[dev]"
pytest -q
ruff check r_cli/ r_os/
ruff format --check r_cli/ r_os/
python -m build
twine check dist/*
```

See [CONTRIBUTING.md](../CONTRIBUTING.md), [ROADMAP.md](../ROADMAP.md), and
[SECURITY.md](../SECURITY.md).
