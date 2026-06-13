# R Security Model

R is designed for people who run one or more AI agents and LLMs on their own computer.
Its default policy is local-only and deny-by-default.

## Security Invariants

Under the default configuration:

1. Prompts may only be sent to an LLM endpoint on `localhost`, `127.0.0.1`, or `::1`.
2. Tool skills with outbound network capability are denied.
3. Agent network access requires both `network_access: true` and explicit allowed hosts.
4. Agent file access can be constrained to resolved filesystem roots.
5. MCP calls are classified as critical and require approval.
6. MCP auto-loading is disabled.
7. API servers bind to loopback and refuse broader binds without `--expose`.
8. Secrets in permission audit arguments are redacted.
9. Every tool execution receives a trace ID, source, decision, and duration.

Inspect the effective policy with:

```bash
r doctor
r os security
r permissions audit
r traces summary
```

## Agent Policy

```yaml
name: private-agent
description: Works only inside one project
kind: assistant
skills: [fs, pdf, text]
network_access: false
filesystem_roots:
  - ./project
```

Network access is exceptional:

```yaml
network_access: true
allowed_hosts:
  - internal.example.com
```

Host allowlists constrain URL-bearing tool arguments. Skills that internally contact a
fixed service must still be treated as trusted code and reviewed before being granted.

## Trust Boundaries

R controls calls that pass through its tool and permission runtime. It cannot fully confine
arbitrary native code inside the same host process.

The following capabilities are intentionally reported as broad host access:

- `code`
- `docker`
- `plugin`
- `power`
- `ssh`
- `system`

A manifest must set `unsafe_capabilities: true` before any of these capabilities can be
installed. This is an acknowledgement, not a sandbox.

A malicious dependency, plugin, MCP server, model runtime, or explicitly approved shell
command may bypass application-level path checks. Filesystem roots are a policy boundary,
not yet an operating-system sandbox.

## Platform Strategy

The next isolation layer should use native mechanisms:

| Platform | Planned isolation |
|----------|-------------------|
| Linux | namespaces, seccomp, cgroups, Landlock, rootless containers |
| macOS | sandbox profiles, restricted child processes, container fallback |
| Windows | AppContainer, Job Objects, restricted tokens |
| Termux | Android app sandbox, proot/container fallback, scoped storage |

Until native sandbox providers land, do not grant broad capabilities to untrusted agents
or install unreviewed MCP servers and plugins.

## Deployment Checklist

1. Use a local model runtime such as Ollama, LM Studio, MLX, llama.cpp, or LocalAI.
2. Confirm `r os security` has no errors.
3. Give each agent the minimum skills and filesystem roots it needs.
4. Keep network access disabled unless a concrete task requires it.
5. Keep `mcp.auto_load: false`.
6. Do not use `--expose` without authentication and firewall rules.
7. Review permission and trace logs regularly.
