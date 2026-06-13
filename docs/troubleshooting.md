# R Troubleshooting

Start every diagnosis with:

```bash
r doctor
r os security
```

Use `r doctor --json` when attaching sanitized diagnostics to an issue.

## Local Model Not Detected

Confirm that the model server is running on loopback:

```bash
# Ollama
curl http://127.0.0.1:11434/v1/models

# LM Studio
curl http://127.0.0.1:1234/v1/models
```

Then check `~/.r-cli/config.yaml`:

```yaml
llm:
  backend: ollama
  model: qwen2.5:7b
  base_url: http://127.0.0.1:11434/v1
```

Do not use a LAN address or public hostname while `security.local_only` is enabled.

## Remote LLM Endpoint Rejected

R intentionally rejects non-loopback inference endpoints in local-only mode. Run the model
on the same device, or place a locally controlled proxy on loopback.

Disabling local-only enforcement weakens R's privacy boundary. Review
[SECURITY_MODEL.md](SECURITY_MODEL.md) before changing it.

## Context Length Exceeded

R can expose many tool schemas. Small models may not have enough context for all of them.

Use a smaller mode:

```bash
r --skills-mode lite chat "Hello"
```

Or allow only required skills:

```yaml
skills:
  mode: whitelist
  enabled:
    - datetime
    - math
    - text
    - fs
```

Increasing the model context window may also help, but a narrow capability set is easier to
review and usually more reliable.

## Outbound Network Access Denied

Network access is denied by default. For an agent that genuinely needs it, declare both the
permission and exact destination hosts:

```yaml
name: documentation-agent
skills: [http]
network_access: true
network_hosts:
  - docs.example.com
```

Avoid wildcard hosts. A deny rule always overrides an allow rule.

## Filesystem Access Denied

An Agent OS identity can access only its declared roots:

```yaml
filesystem_roots:
  - ./documents
  - ./output
```

Use absolute paths when diagnosing path ambiguity. Symlinks and traversal outside allowed
roots are rejected.

## API Binding Refused

The API binds to loopback by default:

```bash
r serve --port 8765
```

A non-loopback bind requires explicit acknowledgement:

```bash
r serve --host 0.0.0.0 --port 8765 --expose
```

Do not expose the API without authentication, TLS, and firewall restrictions.

## Port Already in Use

Choose another port:

```bash
r serve --port 8766
```

On macOS or Linux, inspect port `8765` with:

```bash
lsof -i :8765
```

## Timeout Errors

Local inference can be slow on limited hardware.

```yaml
llm:
  request_timeout: 120.0
```

Also try a smaller model, a shorter prompt, or `--skills-mode lite`.

## Missing Optional Dependencies

Install only the feature group you need when possible:

```bash
python -m pip install "r-cli-ai[all]"
```

For a development checkout:

```bash
python -m pip install -e ".[dev]"
```

Run `r doctor` again after installation.

## Skill Loading Errors

Update to the latest source version:

```bash
python -m pip install --upgrade \
  "r-cli-ai @ git+https://github.com/raym33/r.git"
```

Then inspect available skills:

```bash
r skills
r skills --json
```

## Permission or Trace Investigation

```bash
r permissions explain <skill> <tool>
r permissions audit
r traces list
r traces summary
```

Sanitize paths, prompts, tokens, and personal data before sharing output.

## Getting Help

- [GitHub issues](https://github.com/raym33/r/issues)
- [Quick start](QUICKSTART.md)
- [Complete guide](COMPLETE_GUIDE.md)
- [Security policy](../SECURITY.md)
