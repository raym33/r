# Contributing to R

Thank you for helping build a private, local-first operating layer for AI agents.

## Before You Start

- Use English for code, documentation, issues, and pull requests.
- Search existing issues before opening a new one.
- Discuss large architectural changes in an issue before implementation.
- Report vulnerabilities privately according to [SECURITY.md](SECURITY.md).
- Keep changes focused. Unrelated refactors make security review harder.

By contributing, you agree that your contribution is licensed under the
[MIT License](LICENSE).

## High-Priority Areas

The current priorities are listed in [ROADMAP.md](ROADMAP.md). The most valuable
contributions are:

- native sandbox providers for Linux, macOS, Windows, and Termux;
- adversarial security tests and privacy boundary reviews;
- reliable installation and packaging on supported platforms;
- local model runtime adapters and detection;
- Agent OS scheduling, cancellation, budgets, and delegation;
- documentation, examples, accessibility, and onboarding;
- focused fixes to existing skills.

New network-enabled skills, plugins, or broad host capabilities require a clear threat
model and tests for deny-by-default behavior.

## Development Setup

Requirements:

- Python 3.10 or newer;
- Git;
- a local LLM runtime only when testing model-dependent behavior.

```bash
git clone https://github.com/raym33/r.git
cd r
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Repository Map

```text
r_cli/
  agent_os.py       persistent identities, tasks, and events
  workflows.py      declarative workflow runtime
  security.py       local-only and capability boundaries
  core/             agents, LLM client, memory, permissions, configuration
  skills/           built-in capabilities
  api/              local REST API
r_os/               experimental visual and edge-device shells
tests/              unit and integration tests
docs/               user and architecture documentation
sdks/               API client SDKs
```

## Development Workflow

1. Fork the repository and create a focused branch.
2. Add or update tests before changing security-sensitive behavior.
3. Follow existing patterns and keep the change narrowly scoped.
4. Update relevant documentation.
5. Run the same checks used by CI.

```bash
pytest -q
ruff check r_cli/ r_os/
ruff format --check r_cli/ r_os/
python -m build
twine check dist/*
```

Use `ruff format` to apply formatting:

```bash
ruff format r_cli/ r_os/ tests/
```

## Security Requirements

Changes must preserve the default security invariants:

- LLM endpoints remain loopback-only unless local-only enforcement is deliberately disabled.
- Outbound networking remains denied by default.
- Network destinations must be explicit and allowlisted.
- Agent filesystem roots must not be bypassed with relative paths or traversal.
- MCP remains opt-in and critical-risk.
- public API binding requires explicit `--expose`.
- audit logs must not persist plaintext secrets.
- broad capabilities must not be granted silently.

Security-sensitive pull requests should include:

- the threat being addressed;
- the trust boundary affected;
- negative or adversarial tests;
- platform-specific limitations;
- migration or compatibility impact.

Do not describe application-level policy checks as a complete sandbox.

## Adding a Skill

Create `r_cli/skills/<name>_skill.py` and expose tools through the existing `Skill` and
`Tool` interfaces. Register the skill in `r_cli/skills/__init__.py`.

Every new skill must include:

- a narrow purpose and clear tool schemas;
- input validation;
- tests;
- a risk classification review;
- documentation;
- optional dependency handling;
- no hidden network access.

If the skill can access the network, execute code, launch processes, modify the system, or
read broad filesystem areas, explain why it is necessary and how it is constrained.

## Documentation Contributions

- Keep all public documentation in English.
- Prefer tested commands over hypothetical examples.
- Mark experimental features explicitly.
- Avoid absolute claims such as "zero risk" or "100% secure."
- Link to the canonical [security model](docs/SECURITY_MODEL.md) and
  [roadmap](ROADMAP.md) instead of duplicating promises.

## Pull Requests

Use a conventional commit prefix when practical:

- `feat:` new capability;
- `fix:` bug or regression;
- `docs:` documentation only;
- `test:` tests only;
- `refactor:` behavior-preserving restructuring;
- `chore:` maintenance.

A good pull request contains:

- a concise problem statement;
- implementation summary;
- security impact;
- verification commands and results;
- related issue links;
- screenshots only when UI behavior changes.

Maintainers may request smaller follow-up pull requests when a change is difficult to
review safely.

## Reporting Bugs

Include:

- R version from `r --version`;
- Python version;
- operating system and architecture;
- local LLM runtime and model;
- minimal reproduction steps;
- expected and actual behavior;
- sanitized logs.

Never publish API keys, tokens, private prompts, personal files, or unredacted audit logs.

## Community Standards

Be respectful, technically honest, and patient with contributors working across languages,
platforms, and experience levels. Critique code and ideas, not people.
