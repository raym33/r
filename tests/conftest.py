"""
Pytest fixtures para R CLI.

Proporciona fixtures compartidos para tests unitarios e integración.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock, Mock, patch

import pytest

from r_cli.core.config import Config, LLMConfig, RAGConfig, UIConfig
from r_cli.core.llm import LLMClient, Message, Tool, ToolCall

# === Config Fixtures ===


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Directorio temporal que se limpia automáticamente."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config(temp_dir: Path) -> Config:
    """Configuración mock para tests."""
    return Config(
        llm=LLMConfig(
            backend="lm-studio",
            model="test-model",
            base_url="http://localhost:1234/v1",
            api_key="test-key",
            temperature=0.7,
            max_tokens=1000,
        ),
        rag=RAGConfig(
            enabled=False,
            persist_directory=str(temp_dir / "vectordb"),
        ),
        ui=UIConfig(
            theme="minimal",
            show_thinking=False,
            show_tool_calls=False,
        ),
        home_dir=str(temp_dir / "r-cli"),
        skills_dir=str(temp_dir / "skills"),
        output_dir=str(temp_dir / "output"),
    )


@pytest.fixture
def config_file(temp_dir: Path) -> Path:
    """Archivo de configuración temporal."""
    config_path = temp_dir / "config.yaml"
    config_path.write_text(
        """
llm:
  backend: ollama
  model: qwen2.5:7b
  temperature: 0.5
rag:
  enabled: true
ui:
  theme: ps2
"""
    )
    return config_path


# === LLM Client Fixtures ===


@pytest.fixture
def mock_openai_response() -> Mock:
    """Mock de respuesta OpenAI estándar."""
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = "Mock response from LLM"
    response.choices[0].message.tool_calls = None
    response.usage = Mock()
    response.usage.prompt_tokens = 50
    response.usage.completion_tokens = 100
    return response


@pytest.fixture
def mock_openai_tool_response() -> Mock:
    """Mock de respuesta OpenAI con tool calls."""
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = None
    response.choices[0].message.tool_calls = [
        Mock(
            id="call_123",
            function=Mock(
                name="read_file",
                arguments=json.dumps({"path": "/tmp/test.txt"}),
            ),
        )
    ]
    response.usage = Mock()
    response.usage.prompt_tokens = 60
    response.usage.completion_tokens = 20
    return response


@pytest.fixture
def mock_llm_client(mock_config: Config, mock_openai_response: Mock) -> LLMClient:
    """LLMClient con OpenAI mockeado."""
    with patch("r_cli.core.llm.OpenAI") as mock_openai_cls:
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_client.models.list.return_value = Mock(data=[Mock(id="test-model")])
        mock_openai_cls.return_value = mock_client

        with patch("r_cli.core.llm.AsyncOpenAI"):
            client = LLMClient(mock_config)
            client.client = mock_client
            return client


@pytest.fixture
def sample_tools() -> list[Tool]:
    """Lista de tools de ejemplo para tests."""
    return [
        Tool(
            name="read_file",
            description="Lee un archivo del sistema",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta del archivo"},
                },
                "required": ["path"],
            },
            handler=lambda path: f"Contenido de {path}",
        ),
        Tool(
            name="write_file",
            description="Escribe un archivo",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            handler=lambda path, content: f"Escrito {len(content)} bytes en {path}",
        ),
    ]


# === Message Fixtures ===


@pytest.fixture
def sample_messages() -> list[Message]:
    """Mensajes de ejemplo para tests."""
    return [
        Message(role="system", content="Eres un asistente útil."),
        Message(role="user", content="Hola, ¿cómo estás?"),
        Message(role="assistant", content="¡Hola! Estoy bien, gracias."),
    ]


@pytest.fixture
def tool_call_message() -> Message:
    """Mensaje con tool calls."""
    return Message(
        role="assistant",
        tool_calls=[
            ToolCall(id="call_1", name="read_file", arguments={"path": "/tmp/test.txt"}),
            ToolCall(id="call_2", name="list_dir", arguments={"path": "/tmp"}),
        ],
    )


# === File Fixtures ===


@pytest.fixture
def sample_files(temp_dir: Path) -> dict[str, Path]:
    """Crea archivos de ejemplo para tests."""
    files = {}

    # Archivo de texto
    txt_file = temp_dir / "test.txt"
    txt_file.write_text("Contenido de prueba\nLínea 2\nLínea 3")
    files["txt"] = txt_file

    # Archivo Python
    py_file = temp_dir / "test.py"
    py_file.write_text('def hello():\n    print("Hello")\n')
    files["py"] = py_file

    # Archivo JSON
    json_file = temp_dir / "test.json"
    json_file.write_text('{"key": "value", "number": 42}')
    files["json"] = json_file

    # Archivo Markdown
    md_file = temp_dir / "test.md"
    md_file.write_text("# Title\n\n## Section\n\nContent here.")
    files["md"] = md_file

    return files


@pytest.fixture
def sample_csv(temp_dir: Path) -> Path:
    """CSV de ejemplo para tests."""
    csv_file = temp_dir / "data.csv"
    csv_file.write_text("name,age,city\nAlice,30,Madrid\nBob,25,Barcelona\n")
    return csv_file


# === Environment Fixtures ===


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Limpia variables de entorno relevantes."""
    env_vars = ["R_CLI_CONFIG", "R_CLI_HOME", "OPENAI_API_KEY"]
    saved = {k: os.environ.get(k) for k in env_vars}

    for var in env_vars:
        if var in os.environ:
            del os.environ[var]

    yield

    for var, value in saved.items():
        if value is not None:
            os.environ[var] = value
        elif var in os.environ:
            del os.environ[var]


# === Marker Fixtures ===


def pytest_configure(config: Any) -> None:
    """Configura markers custom."""
    config.addinivalue_line("markers", "integration: tests que requieren servicios externos")
    config.addinivalue_line("markers", "slow: tests lentos")
    config.addinivalue_line("markers", "requires_llm: tests que requieren un LLM corriendo")


# === Skip Conditions ===


@pytest.fixture
def skip_without_ollama() -> None:
    """Salta si Ollama no está disponible."""
    import subprocess

    try:
        result = subprocess.run(
            ["ollama", "--version"], check=False, capture_output=True, timeout=5
        )
        if result.returncode != 0:
            pytest.skip("Ollama not installed")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("Ollama not available")


@pytest.fixture
def skip_without_lm_studio() -> None:
    """Salta si LM Studio no está corriendo."""
    import requests

    try:
        response = requests.get("http://localhost:1234/v1/models", timeout=2)
        if response.status_code != 200:
            pytest.skip("LM Studio not running")
    except requests.exceptions.RequestException:
        pytest.skip("LM Studio not available")
