# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Principles

R CLI is designed with privacy and security in mind:

1. **100% Local**: All processing happens on your machine. No data is sent to external servers.
2. **No Telemetry**: We don't collect any usage data or analytics.
3. **Open Source**: All code is open for inspection.
4. **Local LLMs Only**: We only connect to local LLM servers (LM Studio, Ollama) that you control.

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

## Known Limitations

- The `code` skill executes Python code directly - only use with trusted input
- SQL skill can access any CSV/database file the user has access to
- Voice skill may save temporary audio files

## Dependency Security

We regularly audit our dependencies. Key dependencies:
- `openai`: For LLM communication (connects only to local servers)
- `click`: CLI framework
- `rich`: Terminal UI
- `pydantic`: Data validation

All dependencies are pinned with minimum versions in `pyproject.toml`.
