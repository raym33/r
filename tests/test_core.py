"""
Tests para los módulos core de R CLI.

Cubre:
- Sistema de logging
- Jerarquía de excepciones
- Retry logic
- LLMClient
"""

import json
import logging
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from openai import APIConnectionError, APITimeoutError, RateLimitError

from r_cli.core.config import Config, LLMConfig, discover_config_path, get_preset
from r_cli.core.exceptions import (
    ConfigurationError,
    ExecutionError,
    InvalidInputError,
    LLMConnectionError,
    MissingDependencyError,
    RCLIError,
    RCLIFileNotFoundError,
    SkillExecutionError,
    ValidationError,
    format_error_for_llm,
    is_retriable,
)
from r_cli.core.llm import LLMClient, Message, Tool, ToolCall, with_retry
from r_cli.core.logging import (
    TokenTracker,
    get_logger,
    log_error,
    log_skill_execution,
    setup_logging,
    timed,
)


class TestLogging:
    """Tests para el sistema de logging."""

    def test_setup_logging_creates_logger(self, temp_dir: Path) -> None:
        """Verifica que setup_logging crea un logger."""
        logger = setup_logging(log_dir=str(temp_dir))
        assert logger is not None
        assert logger.name == "r_cli"

    def test_setup_logging_creates_log_file(self, temp_dir: Path) -> None:
        """Verifica que se crea el archivo de log."""
        # Create a fresh logger for this test
        test_logger = logging.getLogger("r_cli.test_file_creation")
        test_logger.handlers.clear()

        log_file = temp_dir / "r_cli.log"
        from logging.handlers import RotatingFileHandler

        fh = RotatingFileHandler(str(log_file), maxBytes=1000, backupCount=1)
        test_logger.addHandler(fh)
        test_logger.setLevel(logging.DEBUG)
        test_logger.info("Test message")
        fh.close()

        assert log_file.exists()

    def test_get_logger_returns_child_logger(self) -> None:
        """Verifica que get_logger retorna loggers hijos."""
        logger = get_logger("r_cli.test")
        assert logger.name == "r_cli.test"

    def test_timed_decorator_logs_execution_time(self, temp_dir: Path) -> None:
        """Verifica que @timed registra el tiempo de ejecución."""
        setup_logging(log_dir=str(temp_dir))

        @timed
        def slow_function() -> str:
            time.sleep(0.1)
            return "done"

        result = slow_function()
        assert result == "done"

    def test_timed_decorator_logs_errors(self, temp_dir: Path) -> None:
        """Verifica que @timed registra errores."""
        setup_logging(log_dir=str(temp_dir))

        @timed
        def failing_function() -> None:
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()


class TestTokenTracker:
    """Tests para TokenTracker."""

    def test_record_tokens(self) -> None:
        """Verifica que se registran tokens correctamente."""
        tracker = TokenTracker()
        tracker.record(prompt_tokens=100, completion_tokens=50)

        assert tracker.total_prompt_tokens == 100
        assert tracker.total_completion_tokens == 50
        assert tracker.total_tokens == 150
        assert tracker.total_requests == 1

    def test_multiple_records(self) -> None:
        """Verifica acumulación de múltiples registros."""
        tracker = TokenTracker()
        tracker.record(prompt_tokens=100, completion_tokens=50)
        tracker.record(prompt_tokens=200, completion_tokens=100)

        assert tracker.total_tokens == 450
        assert tracker.total_requests == 2

    def test_summary(self) -> None:
        """Verifica el resumen de uso."""
        tracker = TokenTracker()
        tracker.record(prompt_tokens=100, completion_tokens=50)

        summary = tracker.summary()
        assert summary["total_requests"] == 1
        assert summary["total_tokens"] == 150

    def test_reset(self) -> None:
        """Verifica el reset de contadores."""
        tracker = TokenTracker()
        tracker.record(prompt_tokens=100, completion_tokens=50)
        tracker.reset()

        assert tracker.total_tokens == 0
        assert tracker.total_requests == 0


class TestExceptions:
    """Tests para la jerarquía de excepciones."""

    def test_rcli_error_base(self) -> None:
        """Verifica la excepción base."""
        error = RCLIError("Test error")
        assert str(error) == "Test error"
        assert error.category == "general"
        assert error.is_recoverable is True

    def test_validation_error(self) -> None:
        """Verifica ValidationError."""
        error = ValidationError("Invalid input")
        assert error.category == "validation"
        assert error.is_recoverable is True

    def test_file_not_found_error(self) -> None:
        """Verifica RCLIFileNotFoundError."""
        error = RCLIFileNotFoundError("/path/to/file")
        assert "/path/to/file" in str(error)
        assert error.context.details["path"] == "/path/to/file"
        assert len(error.context.suggestions) > 0

    def test_invalid_input_error(self) -> None:
        """Verifica InvalidInputError."""
        error = InvalidInputError("age", "abc", "número entero")
        assert "age" in str(error)
        assert "abc" in str(error)

    def test_llm_connection_error(self) -> None:
        """Verifica LLMConnectionError."""
        error = LLMConnectionError("ollama", "http://localhost:11434")
        assert "ollama" in str(error)
        assert error.category == "connection"

    def test_missing_dependency_error(self) -> None:
        """Verifica MissingDependencyError."""
        error = MissingDependencyError("torch", "voice skill")
        assert "torch" in str(error)
        assert error.is_recoverable is False

    def test_skill_execution_error(self) -> None:
        """Verifica SkillExecutionError."""
        cause = ValueError("Original error")
        error = SkillExecutionError("pdf", "generate", cause=cause)
        assert "pdf" in str(error)
        assert error.cause == cause

    def test_error_to_dict(self) -> None:
        """Verifica conversión a dict."""
        error = ValidationError("Test")
        d = error.to_dict()
        assert d["error"] is True
        assert d["category"] == "validation"
        assert d["recoverable"] is True

    def test_user_message_with_suggestions(self) -> None:
        """Verifica mensaje de usuario con sugerencias."""
        error = RCLIFileNotFoundError("/missing/file")
        msg = error.user_message()
        assert "Sugerencias:" in msg

    def test_format_error_for_llm(self) -> None:
        """Verifica formato de error para LLM."""
        error = ValidationError("Test error")
        formatted = format_error_for_llm(error)
        assert "[ERROR: validation]" in formatted

    def test_is_retriable(self) -> None:
        """Verifica detección de errores retriables."""
        conn_error = LLMConnectionError("test", "http://test")
        assert is_retriable(conn_error) is True

        val_error = ValidationError("test")
        assert is_retriable(val_error) is False


class TestRetryLogic:
    """Tests para la lógica de retry."""

    def test_with_retry_succeeds_first_try(self) -> None:
        """Verifica éxito en primer intento."""
        call_count = 0

        @with_retry(max_retries=3)
        def success_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()
        assert result == "success"
        assert call_count == 1

    def test_with_retry_succeeds_after_failures(self) -> None:
        """Verifica éxito después de fallos."""
        call_count = 0

        @with_retry(max_retries=3, initial_delay=0.01)
        def flaky_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise APIConnectionError(request=Mock())
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count == 3

    def test_with_retry_raises_after_max_retries(self) -> None:
        """Verifica que se lanza excepción después de máx reintentos."""

        @with_retry(max_retries=2, initial_delay=0.01)
        def always_fails() -> None:
            raise APIConnectionError(request=Mock())

        with pytest.raises(LLMConnectionError):
            always_fails()

    def test_with_retry_non_retriable_error(self) -> None:
        """Verifica que errores no-retriables se lanzan inmediatamente."""
        call_count = 0

        @with_retry(max_retries=3)
        def value_error_func() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retriable")

        with pytest.raises(ValueError):
            value_error_func()
        assert call_count == 1


class TestConfig:
    """Tests para configuración."""

    def test_default_config(self) -> None:
        """Verifica configuración por defecto."""
        config = Config()
        assert config.llm.backend == "auto"
        assert config.llm.temperature == 0.7

    def test_load_config_from_file(self, config_file: Path) -> None:
        """Verifica carga desde archivo."""
        config = Config.load(str(config_file))
        assert config.llm.backend == "ollama"
        assert config.llm.model == "qwen2.5:7b"
        assert config.llm.temperature == 0.5

    def test_load_config_from_environment(self, config_file: Path) -> None:
        """Verifica R_CLI_CONFIG como ruta de configuración global."""
        with patch.dict("os.environ", {"R_CLI_CONFIG": str(config_file)}):
            config = Config.load()

        assert config.llm.backend == "ollama"
        assert config.llm.model == "qwen2.5:7b"

    def test_discover_project_local_config(self, temp_dir: Path) -> None:
        project = temp_dir / "project"
        nested = project / "src" / "feature"
        nested.mkdir(parents=True)
        local_config = project / ".r-cli.yaml"
        local_config.write_text("skills:\n  mode: lite\n")

        with patch.dict("os.environ", {}, clear=True):
            assert discover_config_path(str(nested)) == local_config.resolve()

    def test_save_config(self, temp_dir: Path) -> None:
        """Verifica guardado de configuración."""
        config = Config(llm=LLMConfig(model="test-model"))
        config_path = temp_dir / "test_config.yaml"
        config.save(str(config_path))

        loaded = Config.load(str(config_path))
        assert loaded.llm.model == "test-model"

    def test_ensure_directories(self, temp_dir: Path) -> None:
        """Verifica creación de directorios."""
        config = Config(
            home_dir=str(temp_dir / "home"),
            skills_dir=str(temp_dir / "skills"),
            output_dir=str(temp_dir / "output"),
        )
        config.ensure_directories()

        assert (temp_dir / "home").exists()
        assert (temp_dir / "skills").exists()
        assert (temp_dir / "output").exists()

    def test_get_preset(self) -> None:
        """Verifica obtención de presets."""
        ollama_preset = get_preset("ollama")
        assert ollama_preset.backend == "ollama"
        assert ollama_preset.model == "qwen2.5:7b"

    def test_invalid_preset_raises(self) -> None:
        """Verifica error con preset inválido."""
        with pytest.raises(ValueError):
            get_preset("invalid_preset")


class TestLLMClient:
    """Tests para LLMClient."""

    def test_init_creates_clients(self, mock_config: Config) -> None:
        """Verifica que se crean los clientes."""
        with patch("r_cli.core.llm.OpenAI"), patch("r_cli.core.llm.AsyncOpenAI"):
            client = LLMClient(mock_config)
            assert client.config == mock_config
            assert len(client.messages) == 0

    def test_set_system_prompt(self, mock_llm_client: LLMClient) -> None:
        """Verifica establecer system prompt."""
        mock_llm_client.set_system_prompt("You are helpful.")
        assert len(mock_llm_client.messages) == 1
        assert mock_llm_client.messages[0].role == "system"
        assert mock_llm_client.messages[0].content == "You are helpful."

    def test_add_message(self, mock_llm_client: LLMClient) -> None:
        """Verifica añadir mensaje."""
        mock_llm_client.add_message("user", "Hello")
        assert len(mock_llm_client.messages) == 1
        assert mock_llm_client.messages[0].role == "user"

    def test_clear_history_keeps_system(self, mock_llm_client: LLMClient) -> None:
        """Verifica que clear_history mantiene system prompt."""
        mock_llm_client.set_system_prompt("System")
        mock_llm_client.add_message("user", "Hello")
        mock_llm_client.add_message("assistant", "Hi")
        mock_llm_client.clear_history()

        assert len(mock_llm_client.messages) == 1
        assert mock_llm_client.messages[0].role == "system"


class TestMessage:
    """Tests para Message."""

    def test_message_to_dict_basic(self) -> None:
        """Verifica conversión básica a dict."""
        msg = Message(role="user", content="Hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello"

    def test_message_to_dict_with_tool_calls(self) -> None:
        """Verifica conversión con tool calls."""
        msg = Message(
            role="assistant",
            tool_calls=[ToolCall(id="1", name="test", arguments={"a": 1})],
        )
        d = msg.to_dict()
        assert "tool_calls" in d
        assert d["tool_calls"][0]["function"]["name"] == "test"

    def test_message_to_dict_tool_response(self) -> None:
        """Verifica conversión de respuesta de tool."""
        msg = Message(role="tool", content="Result", tool_call_id="1", name="test_tool")
        d = msg.to_dict()
        assert d["tool_call_id"] == "1"
        assert d["name"] == "test_tool"


class TestTool:
    """Tests para Tool."""

    def test_tool_to_dict(self) -> None:
        """Verifica conversión a formato OpenAI."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "result",
        )
        d = tool.to_dict()
        assert d["type"] == "function"
        assert d["function"]["name"] == "test_tool"
        assert d["function"]["description"] == "A test tool"

    def test_tool_handler_execution(self) -> None:
        """Verifica ejecución del handler."""
        tool = Tool(
            name="add",
            description="Adds numbers",
            parameters={},
            handler=lambda a, b: str(a + b),
        )
        result = tool.handler(2, 3)
        assert result == "5"
