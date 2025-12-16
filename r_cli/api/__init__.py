"""R CLI API - REST API daemon for R Agent Runtime."""

from r_cli.api.server import create_app, run_server

__all__ = ["create_app", "run_server"]
