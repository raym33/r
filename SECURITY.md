# Security Policy

Security and privacy are core product requirements for R.

## Supported Version

Security fixes are applied to the latest commit on `main`. The project is currently in
beta and does not yet maintain multiple supported release branches.

## Reporting a Vulnerability

Do not open a public issue for a suspected vulnerability.

Email **learntouseai@gmail.com** with:

- a clear description of the issue;
- affected commands, modules, and platforms;
- reproduction steps or a proof of concept;
- likely impact;
- suggested mitigations, if available.

Remove personal data, private prompts, credentials, and unrelated files from reports.

The maintainer will aim to acknowledge reports within 48 hours and provide an initial
assessment within seven days. Timing may vary for complex cross-platform issues.

## Security Scope

High-priority reports include:

- bypassing loopback-only LLM enforcement;
- unauthorized outbound network access;
- escaping declared filesystem roots;
- permission policy or approval bypasses;
- secret exposure in logs, traces, or errors;
- authentication or authorization flaws in the API;
- unsafe default API exposure;
- malicious manifest, workflow, plugin, or MCP behavior;
- task database corruption or privilege escalation;
- arbitrary command execution without an explicitly granted broad capability.

## Default Security Posture

R defaults to:

- local LLM endpoints on loopback;
- denied outbound tool networking;
- explicit agent host allowlists;
- optional per-agent filesystem roots;
- high-risk action confirmation;
- critical-risk MCP calls;
- disabled MCP auto-loading;
- loopback API binding;
- explicit `--expose` for non-loopback binds;
- redacted permission audit arguments;
- traceable governed tool execution.

Run:

```bash
r doctor
r os security
r permissions audit
r traces summary
```

## Known Limitations

R currently provides application-level policy enforcement, not complete native process
isolation. Code execution, Docker, plugins, SSH, system control, and other broad
capabilities may act with the permissions of the current user after explicit approval.

Third-party dependencies, model runtimes, plugins, and MCP servers are separate trust
boundaries. Review them before installation.

The complete guarantees, assumptions, and platform sandbox plan are documented in
[docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md).

## Safe Deployment

- Use a dedicated, non-administrator user when possible.
- Keep `security.local_only: true`.
- Keep `security.network_access: false` unless required.
- Assign minimum skills and filesystem roots to each agent.
- Keep `mcp.auto_load: false`.
- Do not use `--expose` without authentication, TLS, and firewall restrictions.
- Protect `~/.r-cli`, agent databases, configuration, and audit logs.
- Keep R, local model runtimes, and dependencies updated.
