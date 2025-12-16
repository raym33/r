# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.3.x   | :white_check_mark: |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :x:                |

## Security Principles

R CLI is designed with privacy and security in mind:

1. **100% Local**: All processing happens on your machine. No data is sent to external servers.
2. **No Telemetry**: We don't collect any usage data or analytics.
3. **Open Source**: All code is open for inspection.
4. **Local LLMs Only**: We only connect to local LLM servers (LM Studio, Ollama) that you control.

## API Server Security

When running R CLI in daemon mode (`r serve`):

1. **Default Binding**: The API server binds to `127.0.0.1` (localhost only) by default
2. **No Authentication**: The API currently has no authentication - only expose on trusted networks
3. **CORS**: Configured to allow all origins by default - restrict in production
4. **Network Exposure**: Only use `--host 0.0.0.0` on trusted networks

### Recommendations for Production

```yaml
# If exposing the API:
# 1. Use a reverse proxy (nginx, caddy) with TLS
# 2. Add authentication at the proxy level
# 3. Restrict CORS origins
# 4. Use firewall rules to limit access
```

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public issue
2. Email the maintainer at: learntouseai@gmail.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will:
- Acknowledge receipt within 48 hours
- Investigate and respond within 7 days
- Credit you in the fix (unless you prefer anonymity)

## Security Best Practices

When using R CLI:

1. **Keep dependencies updated**: Regularly run `pip install -U r-cli-ai`
2. **Review skills before installing**: Third-party plugins may have security implications
3. **Be careful with code execution**: The `code` skill can execute Python code
4. **Protect your config files**: `~/.r-cli/config.yaml` may contain sensitive settings
5. **Limit API exposure**: Don't expose the daemon API to untrusted networks

## Known Limitations

- The `code` skill executes Python code directly - only use with trusted input
- The `sql` skill can access any CSV/database file the user has access to
- The `ssh` skill can execute remote commands - requires explicit confirmation
- The `docker` skill can manage containers - requires explicit confirmation
- The `openapi` skill can make HTTP requests to discovered services
- Voice skill may save temporary audio files

## Skill Confirmation

High-risk skills require user confirmation by default:
- `ssh` - Remote command execution
- `docker` - Container management
- `email` - Sending emails

Configure in `~/.r-cli/config.yaml`:
```yaml
skills:
  require_confirmation:
    - ssh
    - docker
    - email
```

## Dependency Security

We regularly audit our dependencies. Key dependencies:

| Package | Purpose | Security Note |
|---------|---------|---------------|
| `openai` | LLM communication | Connects only to configured local servers |
| `fastapi` | REST API | Modern, secure web framework |
| `uvicorn` | ASGI server | Production-ready server |
| `click` | CLI framework | No network access |
| `rich` | Terminal UI | No network access |
| `pydantic` | Data validation | Input validation and sanitization |

All dependencies are pinned with minimum versions in `pyproject.toml`.

## File System Access

R CLI has access to:
- Files in the current working directory
- Files explicitly referenced by the user
- Output directory (`~/r-cli-output` by default)
- Config directory (`~/.r-cli`)

The agent cannot access files outside these paths unless explicitly requested.

## Network Access

R CLI makes network connections only to:
- Local LLM servers (configurable base_url)
- The API daemon (localhost by default)
- URLs explicitly requested via `http` or `web` skills

## Audit Log

Consider enabling logging for audit purposes:
```yaml
# In config.yaml
logging:
  level: INFO
  file: ~/.r-cli/r-cli.log
```
