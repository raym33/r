# R

<div align="center">

**A local-first operating layer for private AI agents**

[![CI](https://github.com/raym33/r/actions/workflows/ci.yml/badge.svg)](https://github.com/raym33/r/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

[Quick start](#quick-start) · [Security](#security-first) · [Agent OS](#agent-os) ·
[Roadmap](ROADMAP.md) · [Contributing](CONTRIBUTING.md)

</div>

R lets people run one or more AI agents on their own computer using local language models.
It combines agent identities, tools, workflows, permissions, persistent tasks, isolated
memory, audit trails, and a local API in one open-source runtime.

The project targets Linux, macOS, Windows, and Android through Termux. Local model runtimes
such as Ollama, LM Studio, MLX, llama.cpp, and LocalAI remain under the user's control.

> R is an application-level agent operating layer. It does not replace the host operating
> system. Native sandboxing for each supported platform is an active roadmap item.

## Why R

- **Local LLMs by default:** non-loopback inference endpoints are rejected.
- **Deny-by-default networking:** tools cannot make outbound connections unless an agent
  receives explicit network permission and destination hosts.
- **Capability-based agents:** each identity receives only its declared skills and paths.
- **Persistent processes:** tasks and lifecycle events survive CLI restarts in SQLite.
- **Deterministic automation:** YAML workflows compose validated tools with dependencies,
  variables, retries, conditions, and dry runs.
- **Human control:** high-risk actions require approval and explicit deny rules always win.
- **Observable execution:** tool calls include trace IDs, sources, outcomes, and latency.
- **Portable foundation:** Python 3.10+ and local model APIs work across major desktop
  platforms and Termux.

R currently ships **82 skills exposing about 560 tools**. Availability depends on the host
platform and installed optional dependencies.

## Quick Start

### 1. Install R

```bash
python -m pip install "r-cli-ai @ git+https://github.com/raym33/r.git"
```

For development:

```bash
git clone https://github.com/raym33/r.git
cd r
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

### 2. Start a Local Model

Ollama example:

```bash
ollama pull qwen2.5:7b
ollama serve
```

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
```

### 3. Verify the Security Posture

```bash
r doctor
r os security
```

### 4. Use R

```bash
r chat "Summarize this repository"
r tool math calculate --arg 'expression=sqrt(144)'
r project inspect .
r skills --search pdf
```

Machine-readable output is available across core commands:

```bash
r doctor --json
r config --json
r os status --json
r traces summary --json
```

## Agent OS

Agent manifests define identity, instructions, capabilities, network policy, and filesystem
scope:

```yaml
name: private-researcher
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

Install and run the agent:

```bash
r os agent install researcher.yaml
r os agent list
r os run private-researcher "Compare the PDF reports"
r os tasks --agent private-researcher
r os pause <task-id>
r os resume <task-id>
r os cancel <task-id>
r os events
```

Agent tasks move through `queued`, `paused`, `running`, `completed`, `failed`, and
`cancelled`. Each identity has separate session memory. Broad host capabilities such as
`code`, `docker`, `ssh`, `system`, and plugins require the manifest to acknowledge
`unsafe_capabilities: true`.

See [Agent OS architecture](docs/AGENT_OS.md).

## Workflows

Workflows provide reproducible execution without arbitrary shell access:

```yaml
version: 1
name: calculation-report

variables:
  multiplier: 2

steps:
  - id: calculate
    uses: math.calculate
    with:
      expression: "6 * 7"

  - id: scale
    uses: math.calculate
    depends_on: [calculate]
    with:
      expression: "{{ steps.calculate.result }} * {{ vars.multiplier }}"
```

```bash
r workflow validate workflow.yaml
r workflow run workflow.yaml --dry-run
r workflow run workflow.yaml --var multiplier=3 --json
```

## Security First

The default policy enforces these boundaries:

1. LLM requests stay on loopback.
2. Outbound tool networking is denied.
3. Network-enabled agents require explicit allowed hosts.
4. Filesystem arguments can be restricted to declared roots.
5. MCP calls are critical and MCP auto-loading is disabled.
6. The API binds to loopback unless `--expose` is supplied.
7. Secrets are redacted from permission audit arguments.
8. Every governed tool call is audited and traceable.

```bash
r permissions explain docker docker_run
r permissions audit
r traces list
r os security
```

R cannot yet perfectly confine arbitrary native code running under the same user account.
Read the [security model](docs/SECURITY_MODEL.md) before granting broad capabilities,
installing plugins, or running MCP servers.

To deliberately expose the API:

```bash
r serve --host 0.0.0.0 --expose
```

Use authentication, TLS, and firewall restrictions whenever the API is reachable from
another device.

## Tools and Projects

```bash
# Inspect tool schemas and execute tools directly
r tool pdf
r tool pdf generate_pdf --schema
r tool pdftools pdf_info --params '{"file_path":"report.pdf"}' --json

# Build a PDF from Markdown or stdin
r pdf --file report.md --template report --output report.pdf
printf '# Report\n\nLocal content.' | r pdf --output report.pdf

# Detect a project's stack and create a local profile
r project inspect .
r project init .
```

Configuration precedence:

1. `R_CLI_CONFIG`
2. nearest `.r-cli.yaml` or `.r-cli/config.yaml`
3. `~/.r-cli/config.yaml`

## MCP, P2P, and Distributed AI

These integrations are optional and expand the trust boundary.

- MCP servers are external processes and every call is treated as critical.
- P2P and distributed inference require explicit network access.
- Non-loopback API binds require `--expose`.

Read the dedicated guides before enabling them:

- [MCP usage](docs/COMPLETE_GUIDE.md#mcp-servers)
- [P2P agents](docs/P2P_AGENTS.md)
- [Distributed AI](docs/DISTRIBUTED_AI.md)

## Platform Status

| Platform | Core CLI | Local LLM APIs | Agent OS | Native sandbox |
|----------|----------|----------------|----------|----------------|
| Linux | Supported | Supported | Supported | Planned |
| macOS | Supported | Supported | Supported | Planned |
| Windows | Supported | Supported | Supported | Planned |
| Termux | Experimental | Runtime-dependent | Experimental | Planned |
| Raspberry Pi | Experimental | Small models | Experimental | Planned |

See the [roadmap](ROADMAP.md) for release phases and acceptance criteria.

## Documentation

- [Complete guide](docs/COMPLETE_GUIDE.md)
- [Quick start](docs/QUICKSTART.md)
- [Agent OS architecture](docs/AGENT_OS.md)
- [Security model](docs/SECURITY_MODEL.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Roadmap](ROADMAP.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

## Development

```bash
python -m pip install -e ".[dev]"
pytest -q
ruff check r_cli/ r_os/
ruff format --check r_cli/ r_os/
python -m build
twine check dist/*
```

Contributions are welcome, especially for native sandboxing, Windows and Termux support,
security testing, local model adapters, documentation, and accessibility.

## License

R is released under the [MIT License](LICENSE).
