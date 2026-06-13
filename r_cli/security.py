"""Privacy boundaries shared by local LLMs and tool execution."""

from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

NETWORK_SKILLS = {
    "android",
    "currency",
    "distributed_ai",
    "email",
    "hublab",
    "http",
    "ip",
    "network",
    "openapi",
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
    "network",
    "p2p",
    "rss",
    "sitemap",
    "ssh",
    "web",
}

HOST_ARGUMENTS = {
    "address",
    "host",
    "hostname",
    "server",
    "smtp_server",
}

UNCONFINED_SKILLS = {"code", "docker", "plugin", "power", "ssh", "system"}

PATH_ARGUMENTS = {
    "archive_path",
    "audio_path",
    "base_path",
    "compose_file",
    "cwd",
    "csv",
    "csv_path",
    "db_path",
    "destination",
    "directory",
    "env_file",
    "file",
    "file_path",
    "filename",
    "files",
    "folder",
    "icons_path",
    "identity_file",
    "image_path",
    "input",
    "input_file",
    "input_path",
    "input_paths",
    "local_path",
    "manifest_path",
    "output",
    "output_dir",
    "output_file",
    "output_path",
    "path",
    "pdf_path",
    "save_path",
    "schema_path",
    "script_path",
    "source",
    "source_paths",
    "template_file",
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


def normalize_host_rule(host: str) -> str:
    """Validate and normalize one exact host allowlist entry."""
    normalized = host.strip().rstrip(".").lower()
    if not normalized:
        raise ValueError("host must not be empty")
    if any(character.isspace() for character in normalized):
        raise ValueError("host must not contain whitespace")
    if "://" in normalized or any(character in normalized for character in "/?#@"):
        raise ValueError("use a host name or IP address without a URL, path, or credentials")

    candidate = normalized.strip("[]")
    try:
        ipaddress.ip_address(candidate)
        return candidate
    except ValueError:
        pass

    if ":" in candidate:
        raise ValueError("host allowlist entries must not include ports")
    labels = candidate.split(".")
    if any(
        not label
        or len(label) > 63
        or label.startswith("-")
        or label.endswith("-")
        or not all(character.isalnum() or character == "-" for character in label)
        for label in labels
    ):
        raise ValueError("invalid host name")
    return candidate


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
    hosts: list[str] = []
    for key, value in arguments.items():
        if key.lower() in HOST_ARGUMENTS and isinstance(value, str) and value:
            hosts.append(value.strip().strip("[]").rstrip(".").lower())
        elif isinstance(value, dict):
            hosts.extend(find_hosts(value))
        elif isinstance(value, list):
            hosts.extend(
                host for item in value if isinstance(item, dict) for host in find_hosts(item)
            )
    return hosts


def find_paths(arguments: dict[str, object]) -> list[Path]:
    """Extract path-like arguments without interpreting arbitrary content as paths."""
    paths: list[Path] = []
    for key, value in arguments.items():
        normalized = key.lower()
        if normalized in PATH_ARGUMENTS:
            values = value if isinstance(value, list) else [value]
            for item in values:
                if isinstance(item, str) and item and not urlparse(item).scheme:
                    paths.append(Path(item).expanduser().resolve(strict=False))
        if isinstance(value, dict):
            paths.extend(find_paths(value))
        elif isinstance(value, list):
            paths.extend(
                path for item in value if isinstance(item, dict) for path in find_paths(item)
            )
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
