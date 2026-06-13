"""Privacy boundaries shared by local LLMs and tool execution."""

from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

NETWORK_SKILLS = {
    "distributed_ai",
    "email",
    "http",
    "p2p",
    "rss",
    "sitemap",
    "social",
    "ssh",
    "translate",
    "weather",
    "web",
    "websearch",
}

PARAMETERIZED_NETWORK_SKILLS = {
    "distributed_ai",
    "email",
    "http",
    "p2p",
    "rss",
    "sitemap",
    "ssh",
    "web",
}

HOST_ARGUMENTS = {
    "host",
    "hostname",
    "server",
    "smtp_server",
}

UNCONFINED_SKILLS = {"code", "docker", "plugin", "power", "ssh", "system"}

PATH_ARGUMENTS = {
    "cwd",
    "destination",
    "directory",
    "file",
    "file_path",
    "folder",
    "input",
    "input_file",
    "local_path",
    "output",
    "output_dir",
    "output_file",
    "path",
    "source",
}


def is_loopback_url(url: str) -> bool:
    """Return whether an HTTP endpoint is guaranteed to stay on this device."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def is_loopback_host(host: str) -> bool:
    """Return whether a bind host is restricted to this device."""
    normalized = host.strip().strip("[]").rstrip(".").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def validate_local_llm_endpoint(url: str, local_only: bool = True) -> None:
    """Reject an LLM endpoint that could transmit prompts off-device."""
    if local_only and not is_loopback_url(url):
        raise ValueError(
            f"Remote LLM endpoint blocked by local-only policy: {url}. "
            "Use localhost, 127.0.0.1, or ::1."
        )


def host_is_allowed(url: str, allowed_hosts: list[str]) -> bool:
    """Check an outbound URL against explicit host allow rules."""
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").rstrip(".").lower()
    return bool(hostname) and hostname in {host.rstrip(".").lower() for host in allowed_hosts}


def find_urls(value: object) -> list[str]:
    """Find URL-shaped strings recursively in tool arguments."""
    if isinstance(value, str):
        return [value] if urlparse(value).scheme in {"http", "https"} else []
    if isinstance(value, dict):
        return [url for item in value.values() for url in find_urls(item)]
    if isinstance(value, list):
        return [url for item in value for url in find_urls(item)]
    return []


def find_hosts(arguments: dict[str, object]) -> list[str]:
    """Extract explicit host arguments from network tools."""
    return [
        value.rstrip(".").lower()
        for key, value in arguments.items()
        if key.lower() in HOST_ARGUMENTS and isinstance(value, str) and value
    ]


def find_paths(arguments: dict[str, object]) -> list[Path]:
    """Extract path-like arguments without interpreting arbitrary content as paths."""
    paths: list[Path] = []
    for key, value in arguments.items():
        normalized = key.lower()
        if normalized not in PATH_ARGUMENTS or not isinstance(value, str) or not value:
            continue
        if urlparse(value).scheme:
            continue
        paths.append(Path(value).expanduser().resolve(strict=False))
    return paths


def path_is_within_roots(path: Path, roots: list[str]) -> bool:
    """Return whether a path is contained by one of the configured roots."""
    resolved_roots = [Path(root).expanduser().resolve(strict=False) for root in roots]
    return any(path == root or root in path.parents for root in resolved_roots)


def local_host_addresses() -> set[str]:
    """Return loopback addresses for security diagnostics."""
    addresses = {"127.0.0.1", "::1"}
    try:
        addresses.update(socket.gethostbyname_ex("localhost")[2])
    except OSError:
        pass
    return addresses


def security_report(
    config: object, agents: list[dict[str, object]] | None = None
) -> dict[str, object]:
    """Build an actionable privacy report without making network requests."""
    security = config.security
    llm = config.llm
    checks: list[dict[str, str]] = []

    checks.append(
        {
            "name": "Local LLM endpoint",
            "status": "ok" if is_loopback_url(llm.base_url) else "error",
            "message": llm.base_url,
        }
    )
    checks.append(
        {
            "name": "Local-only enforcement",
            "status": "ok" if security.local_only else "error",
            "message": "enabled" if security.local_only else "disabled",
        }
    )
    checks.append(
        {
            "name": "Default outbound network",
            "status": "warning" if security.network_access else "ok",
            "message": "enabled" if security.network_access else "denied",
        }
    )
    checks.append(
        {
            "name": "Permission mode",
            "status": "warning" if security.mode == "permissive" else "ok",
            "message": security.mode,
        }
    )
    checks.append(
        {
            "name": "Audit trail",
            "status": "ok" if security.audit_enabled else "warning",
            "message": "enabled" if security.audit_enabled else "disabled",
        }
    )

    for agent in agents or []:
        name = str(agent.get("name", "unknown"))
        skills = set(agent.get("skills") or [])
        dangerous = sorted(skills & UNCONFINED_SKILLS)
        if dangerous:
            checks.append(
                {
                    "name": f"Agent {name} confinement",
                    "status": "warning" if agent.get("unsafe_capabilities") else "error",
                    "message": f"broad host capabilities: {', '.join(dangerous)}",
                }
            )
        if agent.get("network_access"):
            hosts = agent.get("allowed_hosts") or []
            checks.append(
                {
                    "name": f"Agent {name} network",
                    "status": "warning",
                    "message": f"allowed hosts: {', '.join(str(host) for host in hosts)}",
                }
            )
        roots = agent.get("filesystem_roots") or []
        checks.append(
            {
                "name": f"Agent {name} filesystem",
                "status": "ok" if roots else "warning",
                "message": ", ".join(str(root) for root in roots) if roots else "no path roots",
            }
        )

    statuses = {check["status"] for check in checks}
    overall = "error" if "error" in statuses else ("warning" if "warning" in statuses else "ok")
    return {"status": overall, "checks": checks}
