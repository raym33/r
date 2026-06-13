# R Roadmap

R aims to become a secure, local-first operating layer for AI agents on Linux, macOS,
Windows, and Android through Termux.

This roadmap describes outcomes, not fixed dates. Security work takes priority over feature
count. A phase is complete only when its exit criteria are met on supported platforms.

## Current Foundation

Available today:

- local LLM connectivity with loopback enforcement;
- 82 skills and approximately 560 tools;
- persistent agent identities, tasks, events, and isolated session memory;
- deterministic YAML workflows;
- capability declarations and broad-capability acknowledgement;
- deny-by-default tool networking and host allowlists;
- filesystem root policy checks;
- permission audit logs and execution traces;
- local REST API with explicit network exposure;
- optional MCP, P2P, distributed AI, voice, and edge-device modules.

## Phase 1: Secure Local Runtime

**Goal:** make the safe path the easiest path for a single user and a single computer.

Planned:

- installation profiles for Linux, macOS, Windows, and Termux;
- local model discovery and guided setup;
- platform-aware configuration directories and services;
- encrypted secret storage using native keychains;
- permission review and revocation commands;
- security policy schemas with migration support;
- automated privacy regression tests.

Exit criteria:

- clean install and first local response on every target platform;
- no remote endpoint or network access without an explicit policy change;
- documented uninstall and data deletion;
- CI coverage for supported Python and operating-system combinations.

## Phase 2: Native Sandboxing

**Goal:** enforce agent boundaries below the Python application layer.

Planned:

- a common sandbox provider interface;
- Linux namespaces, seccomp, cgroups, Landlock, and rootless container options;
- macOS restricted child processes and sandbox profiles or container fallback;
- Windows AppContainer, restricted tokens, and Job Objects;
- Termux scoped storage and proot/container fallback;
- CPU, memory, process, wall-time, and disk budgets;
- sandbox capability detection through `r os security`.

Exit criteria:

- untrusted code cannot read outside mounted roots;
- denied network access is enforced by the operating system;
- child processes terminate when task budgets expire;
- adversarial escape tests run in platform CI.

## Phase 3: Agent Process Manager

**Goal:** turn persistent tasks into a reliable local agent scheduler.

Planned:

- background workers and resumable queues;
- cancellation and queued-task pause controls (initial CLI support is available);
- retry, timeout, and priority controls;
- token, tool, and cost budgets;
- task checkpoints and recovery after restart;
- human approval inboxes;
- structured agent-to-agent messages;
- dead-letter queues and failure inspection.
- privacy-preserving task capsules for local audit and support (initial CLI support is
  available).

Exit criteria:

- tasks recover safely after process or device restart;
- every transition is auditable;
- users can stop agents immediately;
- resource limits are enforced consistently.

## Phase 4: Trusted Extensions

**Goal:** support a useful ecosystem without weakening the default trust model.

Planned:

- signed extension manifests;
- reproducible package metadata and checksums;
- isolated plugin and MCP processes;
- versioned capability requests;
- extension provenance and update review;
- local extension registry and optional public index.

Exit criteria:

- extensions cannot gain undeclared capabilities;
- upgrades show permission changes before installation;
- compromised extensions can be revoked locally.

## Phase 5: Private Multi-Device Agents

**Goal:** coordinate user-owned devices without turning local agents into a cloud service.

Planned:

- authenticated device pairing;
- encrypted transport and device identities;
- explicit data-sharing policies;
- distributed task placement and model routing;
- offline-first synchronization;
- encrypted backups controlled by the user.

Exit criteria:

- no peer is trusted before pairing;
- all shared data has an explicit destination and policy;
- nodes can be revoked without reinstalling the system.

## Phase 6: User Experience

**Goal:** make strong local security understandable to non-experts.

Planned:

- guided setup and model selection;
- visual process, permission, and trace manager;
- accessible desktop and terminal interfaces;
- security posture explanations in plain language;
- templates for common personal, developer, document, and business agents;
- migration and backup tools.

## How to Help

See [CONTRIBUTING.md](CONTRIBUTING.md). Current high-impact contributions include:

- native sandbox research and prototypes;
- Windows and Termux installation testing;
- adversarial privacy tests;
- keychain integrations;
- task cancellation and resource budgets;
- documentation and onboarding;
- reproducible bug reports across local model runtimes.

Open an issue before starting a large roadmap item so scope and security assumptions can be
reviewed together.
