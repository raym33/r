# R Quick Start

Run a private AI agent with a local model in a few minutes.

## 1. Install R

Install the latest version from GitHub:

```bash
python -m pip install "r-cli-ai @ git+https://github.com/raym33/r.git"
```

Verify the installation:

```bash
r --version
r doctor
```

## 2. Start a Local Model

### Ollama

```bash
ollama pull qwen2.5:7b
ollama serve
```

### LM Studio

1. Install [LM Studio](https://lmstudio.ai/).
2. Download and load a model.
3. Start its local API server on `127.0.0.1`.

R rejects non-loopback model endpoints while local-only security is enabled.

## 3. Configure R

Create `~/.r-cli/config.yaml`:

```yaml
llm:
  backend: ollama
  model: qwen2.5:7b
  base_url: http://127.0.0.1:11434/v1

security:
  local_only: true
  network_access: false
  mode: ask

skills:
  mode: auto
```

For LM Studio, use its loopback URL, usually
`http://127.0.0.1:1234/v1`.

## 4. Check Security

```bash
r doctor
r os security
```

Review the output before enabling network access, plugins, MCP servers, code execution, or
other broad host capabilities.

## 5. Start Using R

```bash
r chat "Explain what this repository does"
r skills --search pdf
r tool math calculate --arg 'expression=sqrt(144)'
r project inspect .
```

Generate a PDF from Markdown:

```bash
r pdf --file report.md --output report.pdf
```

## 6. Create an Agent

Create `researcher.yaml`:

```yaml
name: private-researcher
description: Analyze documents inside one project
kind: assistant
system_prompt: |
  Use only the available local evidence.
  State clearly when information is missing.
skills: [fs, pdf, pdftools, rag, text]
network_access: false
filesystem_roots:
  - ./documents
```

Install and run it:

```bash
r os agent install researcher.yaml
r os submit private-researcher "Summarize the documents" --priority high
r os start <task-id>
r os reprioritize <task-id> critical
r os run private-researcher "Summarize the documents"
r os tasks --agent private-researcher
```

## 7. Handle Small Context Windows

If a model cannot accept all tool schemas, use a smaller skill set:

```bash
r --skills-mode lite chat "Hello"
```

Or configure:

```yaml
skills:
  mode: lite
```

Use `whitelist` mode when an agent needs only specific skills.

## 8. Run the Local API

```bash
r serve --port 8765
```

Open `http://127.0.0.1:8765/docs`.

The server binds to loopback by default. Exposing it to other devices requires the explicit
`--expose` flag and appropriate authentication, TLS, and firewall controls.

## Next Steps

- [Complete guide](COMPLETE_GUIDE.md)
- [Security model](SECURITY_MODEL.md)
- [Agent OS architecture](AGENT_OS.md)
- [Roadmap](../ROADMAP.md)
- [Troubleshooting](troubleshooting.md)
- [Contributing](../CONTRIBUTING.md)
