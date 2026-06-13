# R Agent OS

R Agent OS is an application-level operating layer for local AI agents. It does not replace
Linux, macOS, or Windows. It provides the primitives agents need to run as governed,
persistent processes on top of the host operating system.

## Current Kernel

- **Identity:** YAML manifests define an agent's name, prompt, capabilities, and executor.
- **Processes:** Tasks move through `queued`, `paused`, `running`, `completed`, `failed`,
  and `cancelled`.
- **Persistence:** SQLite stores identities, task history, and events.
- **Memory:** Every agent receives an isolated session namespace.
- **Capabilities:** Skills are explicitly assigned to assistant agents.
- **Execution:** Agents can use an LLM or deterministic R workflows.
- **Security:** Existing permission policy, approvals, redaction, and audit traces remain active.
- **Privacy:** LLM inference is restricted to loopback endpoints under local-only mode.
- **Isolation:** Agents declare network allowlists and filesystem roots.
- **Observability:** Tasks emit lifecycle events and tool calls appear in `r traces`.

## Architecture

```mermaid
flowchart TD
    CLI["r os"] --> Kernel["Agent OS runtime"]
    Manifest["Agent manifests"] --> Kernel
    Kernel --> Registry["Identity registry"]
    Kernel --> Scheduler["Task supervisor"]
    Scheduler --> Assistant["Assistant executor"]
    Scheduler --> Workflow["Workflow executor"]
    Assistant --> Capabilities["Skills and MCP tools"]
    Workflow --> Capabilities
    Capabilities --> Permissions["Permissions and approvals"]
    Permissions --> Host["Host operating system"]
    Kernel --> Events["Event stream"]
    Kernel --> Memory["Per-agent memory"]
    Permissions --> Traces["Execution traces"]
```

## Commands

```bash
r os init researcher.yaml
r os agent install researcher.yaml
r os agent list
r os agent show researcher
r os run researcher "Analyze this project"
r os tasks --status completed
r os pause <task-id>
r os resume <task-id>
r os cancel <task-id>
r os events
r os status
r os security
```

Tasks can be paused while they are still queued. A paused task will not be moved to
`running` until it is resumed, which gives operators a simple approval checkpoint before
future background workers pick up queued work. Running tasks cannot be paused yet; cancel
them instead.

## Workflow Agents

A deterministic agent points to an existing R workflow:

```yaml
name: nightly-report
description: Builds the local report from validated steps
kind: workflow
workflow: ./report.workflow.yaml
```

The submitted task is available to the workflow as `{{ vars.task }}`.

## Roadmap

The canonical project roadmap, phases, and exit criteria are maintained in
[ROADMAP.md](../ROADMAP.md).
