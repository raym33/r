"""Health checks used by the R CLI doctor command."""

import os
import platform
import sys
from dataclasses import asdict, dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from r_cli import __version__
from r_cli.backends.auto import auto_detect_backend
from r_cli.core.config import Config
from r_cli.security import is_loopback_url


@dataclass
class Diagnostic:
    """A single actionable health check."""

    name: str
    status: str
    message: str
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)


def _check_directory(name: str, path_value: str) -> Diagnostic:
    path = Path(os.path.expanduser(path_value))

    if not path.exists():
        parent = next((candidate for candidate in path.parents if candidate.exists()), None)
        if parent is None or not os.access(parent, os.W_OK):
            return Diagnostic(
                name,
                "error",
                f"{path} cannot be created",
                "Check parent directory permissions",
            )
        return Diagnostic(name, "ok", f"{path} (will be created when needed)")

    if not os.access(path, os.W_OK):
        return Diagnostic(name, "error", f"{path} is not writable", "Check directory permissions")

    return Diagnostic(name, "ok", str(path))


def collect_diagnostics(config_path: str | None = None) -> list[Diagnostic]:
    """Run local configuration, storage, and backend health checks."""
    config_file = Path(
        os.path.expanduser(config_path or os.environ.get("R_CLI_CONFIG", "~/.r-cli/config.yaml"))
    )
    checks = [
        Diagnostic("R CLI", "ok", f"v{__version__}"),
        Diagnostic(
            "Python",
            "ok",
            f"{platform.python_version()} ({platform.system()} {platform.machine()})",
        ),
    ]

    try:
        config = Config.load(str(config_file))
        if config_file.exists():
            checks.append(Diagnostic("Configuration", "ok", str(config_file)))
        else:
            checks.append(
                Diagnostic(
                    "Configuration",
                    "warning",
                    f"Using defaults; {config_file} does not exist",
                    "Run `r config --path` to see where configuration is loaded from",
                )
            )
    except Exception as exc:
        checks.append(
            Diagnostic(
                "Configuration",
                "error",
                f"Could not load {config_file}: {exc}",
                "Fix the YAML file or move it aside to use defaults",
            )
        )
        return checks

    checks.extend(
        [
            _check_directory("Home directory", config.home_dir),
            _check_directory("Output directory", config.output_dir),
            _check_directory("Skills directory", config.skills_dir),
        ]
    )

    if config.security.local_only and not is_loopback_url(config.llm.base_url):
        checks.append(
            Diagnostic(
                "LLM privacy",
                "error",
                f"Remote endpoint blocked: {config.llm.base_url}",
                "Use a loopback endpoint such as http://127.0.0.1:11434/v1",
            )
        )
    else:
        checks.append(Diagnostic("LLM privacy", "ok", f"Local endpoint: {config.llm.base_url}"))

    if config.security.mode not in {"ask", "strict", "permissive"}:
        checks.append(
            Diagnostic(
                "Permission policy",
                "error",
                f"Unknown security mode: {config.security.mode}",
                "Use ask, strict, or permissive",
            )
        )
    else:
        checks.append(
            Diagnostic(
                "Permission policy",
                "ok",
                f"{config.security.mode} mode; confirms {', '.join(config.security.confirm_risk)}",
            )
        )

    enabled_mcp_servers = [name for name, server in config.mcp.servers.items() if server.enabled]
    if enabled_mcp_servers and find_spec("mcp") is None:
        checks.append(
            Diagnostic(
                "MCP",
                "warning",
                f"{len(enabled_mcp_servers)} server(s) configured but SDK is not installed",
                "Run: pip install 'r-cli-ai[mcp]'",
            )
        )
    elif enabled_mcp_servers:
        mcp_status = "warning" if config.mcp.auto_load else "ok"
        checks.append(
            Diagnostic(
                "MCP",
                mcp_status,
                f"{len(enabled_mcp_servers)} enabled server(s); auto-load={config.mcp.auto_load}",
                "Disable mcp.auto_load for strongest process isolation"
                if config.mcp.auto_load
                else None,
            )
        )

    detected, details = auto_detect_backend(config.llm.backend)
    if detected == "none":
        checks.append(
            Diagnostic(
                "LLM backend",
                "warning",
                "No running local backend detected",
                "Start Ollama with `ollama serve` or start the LM Studio local server",
            )
        )
    else:
        model = details.get("model") or config.llm.model
        checks.append(Diagnostic("LLM backend", "ok", f"{detected} ({model})"))

    checks.append(
        Diagnostic(
            "Terminal",
            "ok",
            "Interactive TTY"
            if sys.stdout.isatty()
            else "Non-interactive output (animations disabled)",
        )
    )
    return checks


def diagnostics_status(checks: list[Diagnostic]) -> str:
    """Return the overall status for a collection of checks."""
    statuses = {check.status for check in checks}
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    return "ok"
