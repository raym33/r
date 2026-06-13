"""Tests for local-only privacy boundaries."""

import pytest

from r_cli.core.config import Config
from r_cli.security import (
    NETWORK_SKILLS,
    find_hosts,
    find_paths,
    is_loopback_host,
    is_loopback_url,
    normalize_host_rule,
    security_report,
    validate_local_llm_endpoint,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434/v1",
        "http://127.0.0.1:1234/v1",
        "http://[::1]:8080/v1",
    ],
)
def test_loopback_llm_urls_are_local(url):
    assert is_loopback_url(url)
    validate_local_llm_endpoint(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "http://192.168.1.10:11434",
        "http://ollama.local:11434",
        "file:///tmp/model",
    ],
)
def test_non_loopback_llm_urls_are_blocked(url):
    assert not is_loopback_url(url)
    with pytest.raises(ValueError, match="Remote LLM endpoint blocked"):
        validate_local_llm_endpoint(url)


def test_security_report_flags_remote_endpoint_and_broad_skills():
    config = Config()
    config.llm.base_url = "https://remote.example/v1"
    report = security_report(
        config,
        [
            {
                "name": "coder",
                "skills": ["code"],
                "filesystem_roots": [],
                "network_access": False,
            }
        ],
    )

    assert report["status"] == "error"
    assert any(check["name"] == "Agent coder confinement" for check in report["checks"])


def test_only_loopback_bind_hosts_are_private():
    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("::1")
    assert is_loopback_host("localhost")
    assert not is_loopback_host("0.0.0.0")
    assert not is_loopback_host("192.168.1.20")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("API.Example.COM.", "api.example.com"),
        ("127.0.0.1", "127.0.0.1"),
        ("[::1]", "::1"),
    ],
)
def test_host_allowlist_rules_are_normalized(value, expected):
    assert normalize_host_rule(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://api.example.com",
        "api.example.com:443",
        "*.example.com",
        "user@example.com",
        "api.example.com/path",
    ],
)
def test_host_allowlist_rules_reject_ambiguous_values(value):
    with pytest.raises(ValueError):
        normalize_host_rule(value)


def test_nested_host_and_path_arguments_are_discovered(tmp_path):
    document = tmp_path / "workspace" / "report.txt"
    arguments = {
        "connection": {"server": "SMTP.Example.com."},
        "jobs": [{"options": {"output_file": str(document)}}],
    }

    assert find_hosts(arguments) == ["smtp.example.com"]
    assert find_paths(arguments) == [document.resolve()]


def test_path_lists_and_common_filename_fields_are_discovered(tmp_path):
    arguments = {
        "filename": str(tmp_path / "script.py"),
        "input_paths": [
            str(tmp_path / "one.pdf"),
            str(tmp_path / "two.pdf"),
        ],
    }

    assert find_paths(arguments) == [
        (tmp_path / "script.py").resolve(),
        (tmp_path / "one.pdf").resolve(),
        (tmp_path / "two.pdf").resolve(),
    ]


def test_known_network_capabilities_are_governed():
    assert {
        "android",
        "currency",
        "hublab",
        "http",
        "ip",
        "network",
        "openapi",
        "social",
        "weather",
        "websearch",
    } <= NETWORK_SKILLS
