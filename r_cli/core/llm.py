"""
LLM Client for R CLI.

Abstraction over OpenAI SDK that works with:
- LM Studio
- Ollama
- Any OpenAI-compatible server

Supports:
- Chat completions
- Tool calling (function calling)
- Streaming
- Retry with exponential backoff
"""

import json
import time
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Optional

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, OpenAI, RateLimitError
from rich.console import Console

# Optional tiktoken import for accurate token counting
try:
    import tiktoken

    _TIKTOKEN_AVAILABLE = True
except ImportError:
    tiktoken = None  # type: ignore
    _TIKTOKEN_AVAILABLE = False

from r_cli.core.config import Config
from r_cli.core.exceptions import (
    LLMConnectionError,
    RCLITimeoutError,
)
from r_cli.core.exceptions import (
    RateLimitError as RCLIRateLimitError,
)
from r_cli.core.logging import get_logger, timed, token_tracker

console = Console()
logger = get_logger("r_cli.llm")

# Retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0  # seconds
DEFAULT_RETRY_MULTIPLIER = 2.0
DEFAULT_RETRY_MAX_DELAY = 30.0  # seconds

# Token encoder cache (initialized lazily)
_TOKEN_ENCODER: Optional[Any] = None


def _get_token_encoder() -> Optional[Any]:
    """Get or create tiktoken encoder (cached). Returns None if unavailable."""
    global _TOKEN_ENCODER
    if not _TIKTOKEN_AVAILABLE:
        return None
    if _TOKEN_ENCODER is None:
        try:
            # Use cl100k_base which is used by GPT-4 and most modern models
            _TOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None
    return _TOKEN_ENCODER


def with_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_RETRY_DELAY,
    multiplier: float = DEFAULT_RETRY_MULTIPLIER,
    max_delay: float = DEFAULT_RETRY_MAX_DELAY,
) -> Callable:
    """
    Decorador para retry con backoff exponencial.

    Args:
        max_retries: Número máximo de reintentos
        initial_delay: Delay inicial en segundos
        multiplier: Multiplicador para backoff
        max_delay: Delay máximo entre reintentos
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = initial_delay
            last_exception: Optional[Exception] = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (APIConnectionError, APITimeoutError, RateLimitError) as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded: {e}")
                        break

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay = min(delay * multiplier, max_delay)
                except Exception as e:
                    # Errores no retriables
                    logger.error(f"Non-retriable error: {e}")
                    raise

            # Si llegamos aquí, agotamos los reintentos
            if isinstance(last_exception, APIConnectionError):
                # Extraer URL de forma segura
                request = getattr(last_exception, "request", None)
                url = str(getattr(request, "url", "unknown")) if request else "unknown"
                raise LLMConnectionError(
                    backend="LLM",
                    url=url,
                    cause=last_exception,
                )
            if isinstance(last_exception, APITimeoutError):
                raise RCLITimeoutError(
                    operation="LLM request",
                    timeout_seconds=30.0,
                    cause=last_exception,
                )
            if isinstance(last_exception, RateLimitError):
                raise RCLIRateLimitError(service="LLM")
            raise last_exception  # type: ignore

        return wrapper

    return decorator


@dataclass
class ToolCall:
    """Representa una llamada a herramienta del LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    """Mensaje en la conversación."""

    role: str  # system, user, assistant, tool
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: Optional[str] = None  # For tool responses
    name: Optional[str] = None  # Tool name (for role=tool)

    def to_dict(self) -> dict:
        """Convert to OpenAI API format."""
        msg = {"role": self.role}

        if self.content is not None:
            msg["content"] = self.content

        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in self.tool_calls
            ]

        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id

        if self.name:
            msg["name"] = self.name

        return msg


@dataclass
class Tool:
    """Definición de una herramienta para el LLM."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    handler: Callable[..., str]  # Función que ejecuta la tool

    def to_dict(self) -> dict:
        """Convert to OpenAI API format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class LLMClient:
    """
    Cliente para interactuar con LLMs locales.

    Ejemplo de uso:
    ```python
    client = LLMClient(config)

    # Chat simple
    response = client.chat("Hola, ¿cómo estás?")

    # Con tools
    tools = [Tool(name="get_weather", ...)]
    response = client.chat("¿Qué tiempo hace?", tools=tools)
    ```
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.llm_config = self.config.llm

        # Cliente síncrono con timeout configurable
        self.client = OpenAI(
            base_url=self.llm_config.base_url,
            api_key=self.llm_config.api_key,
            timeout=self.llm_config.request_timeout,
        )

        # Cliente asíncrono con timeout configurable
        self.async_client = AsyncOpenAI(
            base_url=self.llm_config.base_url,
            api_key=self.llm_config.api_key,
            timeout=self.llm_config.request_timeout,
        )

        # Message history
        self.messages: list[Message] = []

    def _estimate_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken for accuracy."""
        encoder = _get_token_encoder()
        if encoder is not None:
            try:
                return len(encoder.encode(text))
            except Exception:
                pass
        # Fallback to estimation if tiktoken unavailable
        return len(text) // 4 + 1

    def _get_context_tokens(self) -> int:
        """Calculate total tokens in current context."""
        total = 0
        for msg in self.messages:
            if msg.content:
                total += self._estimate_tokens(msg.content)
        return total

    def _check_token_limits(self, new_message: str) -> tuple[bool, str]:
        """
        Check if adding a message would exceed token limits.

        Returns:
            (is_ok, warning_message)
        """
        current_tokens = self._get_context_tokens()
        new_tokens = self._estimate_tokens(new_message)
        total_tokens = current_tokens + new_tokens
        max_tokens = self.llm_config.max_context_tokens
        threshold = max_tokens * self.llm_config.token_warning_threshold

        if total_tokens > max_tokens:
            return False, f"Context exceeds limit ({total_tokens}/{max_tokens} tokens)"
        elif total_tokens > threshold:
            return (
                True,
                f"Warning: Context at {int(total_tokens / max_tokens * 100)}% ({total_tokens}/{max_tokens} tokens)",
            )
        return True, ""

    def _truncate_context_if_needed(self) -> None:
        """Truncate context if it exceeds limits, keeping system prompt."""
        max_tokens = self.llm_config.max_context_tokens

        while self._get_context_tokens() > max_tokens and len(self.messages) > 2:
            # Keep system prompt (index 0), remove oldest messages
            for i, msg in enumerate(self.messages):
                if msg.role != "system":
                    self.messages.pop(i)
                    logger.info("Truncated message to stay within token limit")
                    break

    def _check_connection(self) -> bool:
        """Check if the LLM server is available."""
        try:
            self.client.models.list()
            return True
        except Exception:
            return False

    def set_system_prompt(self, prompt: str) -> None:
        """Set the system prompt."""
        # Remove previous system prompt if exists
        self.messages = [m for m in self.messages if m.role != "system"]
        # Add new one
        self.messages.insert(0, Message(role="system", content=prompt))

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the history."""
        self.messages.append(Message(role=role, content=content))

    def clear_history(self) -> None:
        """Clear history while keeping the system prompt."""
        system_msgs = [m for m in self.messages if m.role == "system"]
        self.messages = system_msgs

    @timed
    def chat(
        self,
        message: str,
        tools: Optional[list[Tool]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Message:
        """
        Envía un mensaje y obtiene respuesta.

        Si hay tools, puede retornar tool_calls que deben ser ejecutadas.
        """
        # Verificar límites de tokens antes de agregar
        is_ok, warning = self._check_token_limits(message)
        if warning:
            logger.warning(warning)
        if not is_ok:
            # Intentar truncar contexto
            self._truncate_context_if_needed()
            is_ok, warning = self._check_token_limits(message)
            if not is_ok:
                logger.error(f"Cannot add message: {warning}")
                return Message(
                    role="assistant",
                    content=f"Error: {warning}. Usa /clear para limpiar el historial.",
                )

        # Agregar mensaje del usuario
        self.add_message("user", message)

        # Preparar request
        request_params = {
            "model": self.llm_config.model,
            "messages": [m.to_dict() for m in self.messages],
            "temperature": temperature or self.llm_config.temperature,
            "max_tokens": max_tokens or self.llm_config.max_tokens,
        }

        if tools:
            request_params["tools"] = [t.to_dict() for t in tools]
            request_params["tool_choice"] = "auto"

        # Llamar al LLM con retry
        response = self._call_llm(request_params)
        if response is None:
            return Message(role="assistant", content="Error: No se pudo conectar con el LLM")

        # Registrar uso de tokens
        if hasattr(response, "usage") and response.usage:
            token_tracker.record(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                model=self.llm_config.model,
            )

        # Verificar que hay respuesta válida
        if not response.choices:
            logger.error("Empty response from LLM")
            return Message(role="assistant", content="Error: Respuesta vacía del LLM")

        # Procesar respuesta
        choice = response.choices[0]
        assistant_message = Message(role="assistant")

        if choice.message.content:
            assistant_message.content = choice.message.content

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    logger.warning(f"Error parsing tool call arguments: {tc.function.arguments}")
                    args = {}

                assistant_message.tool_calls.append(
                    ToolCall(id=tc.id, name=tc.function.name, arguments=args)
                )

        # Agregar al historial
        self.messages.append(assistant_message)
        logger.debug(
            f"Chat response: {len(assistant_message.content or '')} chars, "
            f"{len(assistant_message.tool_calls)} tool calls"
        )

        return assistant_message

    @with_retry()
    def _call_llm(self, request_params: dict[str, Any]) -> Any:
        """Llamada al LLM con retry automático."""
        return self.client.chat.completions.create(**request_params)

    def execute_tools(self, tool_calls: list[ToolCall], tools: list[Tool]) -> list[Message]:
        """Ejecuta las tools llamadas y retorna los resultados."""
        results = []
        tool_map = {t.name: t for t in tools}

        for tc in tool_calls:
            if tc.name in tool_map:
                tool = tool_map[tc.name]
                try:
                    result = tool.handler(**tc.arguments)
                except Exception as e:
                    result = f"Error ejecutando {tc.name}: {e}"
            else:
                result = f"Tool no encontrada: {tc.name}"

            msg = Message(
                role="tool",
                content=result,
                tool_call_id=tc.id,
                name=tc.name,
            )
            results.append(msg)
            self.messages.append(msg)

        return results

    def chat_with_tools(
        self,
        message: str,
        tools: list[Tool],
        max_iterations: int = 10,
    ) -> str:
        """
        Chat completo con ejecución automática de tools.

        Loop agentic: LLM → tool calls → execute → LLM → ... hasta respuesta final.
        """
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            if iteration == 1:
                response = self.chat(message, tools=tools)
            else:
                # Continuar conversación sin nuevo mensaje de usuario
                request_params = {
                    "model": self.llm_config.model,
                    "messages": [m.to_dict() for m in self.messages],
                    "tools": [t.to_dict() for t in tools],
                    "tool_choice": "auto",
                }

                try:
                    api_response = self.client.chat.completions.create(**request_params)

                    # Verificar respuesta válida
                    if not api_response.choices:
                        return "Error: Respuesta vacía del LLM"

                    choice = api_response.choices[0]

                    response = Message(role="assistant")
                    if choice.message.content:
                        response.content = choice.message.content

                    if choice.message.tool_calls:
                        for tc in choice.message.tool_calls:
                            try:
                                args = json.loads(tc.function.arguments)
                            except json.JSONDecodeError:
                                args = {}
                            response.tool_calls.append(
                                ToolCall(id=tc.id, name=tc.function.name, arguments=args)
                            )

                    self.messages.append(response)

                except Exception as e:
                    logger.error(f"Error in chat_with_tools: {e}")
                    return f"Error: {e}"

            # Si hay tool calls, ejecutarlas
            if response.tool_calls:
                self.execute_tools(response.tool_calls, tools)
            else:
                # No hay tool calls, respuesta final
                return response.content or ""

        return "Se alcanzó el límite de iteraciones"

    def chat_stream_sync(
        self,
        message: str,
        tools: Optional[list[Tool]] = None,
        max_tool_iterations: int = 10,
    ) -> Iterator[str]:
        """
        Chat with synchronous streaming, including tool call support.

        Yields tokens as they arrive from the LLM.
        If tools are provided and the LLM requests tool calls, executes them
        and continues streaming the follow-up response.

        Args:
            message: User message
            tools: Optional list of tools available to the LLM
            max_tool_iterations: Max tool execution loops (default: 10)
        """
        self.add_message("user", message)
        logger.debug(f"Starting sync stream for message: {message[:50]}...")

        iteration = 0
        while iteration < max_tool_iterations:
            iteration += 1

            request_params = {
                "model": self.llm_config.model,
                "messages": [m.to_dict() for m in self.messages],
                "temperature": self.llm_config.temperature,
                "stream": True,
            }

            if tools:
                request_params["tools"] = [t.to_dict() for t in tools]

            full_content = ""
            tool_calls_data: dict[int, dict] = {}  # index -> {id, name, arguments}

            try:
                stream = self.client.chat.completions.create(**request_params)
                for chunk in stream:
                    if not chunk.choices:
                        continue

                    delta = chunk.choices[0].delta

                    # Handle content
                    if delta.content:
                        full_content += delta.content
                        yield delta.content

                    # Handle tool calls (accumulated from deltas)
                    if delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tool_calls_data:
                                tool_calls_data[idx] = {
                                    "id": "",
                                    "name": "",
                                    "arguments": "",
                                }
                            if tc_delta.id:
                                tool_calls_data[idx]["id"] = tc_delta.id
                            if tc_delta.function:
                                if tc_delta.function.name:
                                    tool_calls_data[idx]["name"] = tc_delta.function.name
                                if tc_delta.function.arguments:
                                    tool_calls_data[idx]["arguments"] += tc_delta.function.arguments

            except (APIConnectionError, APITimeoutError) as e:
                logger.error(f"Stream error: {e}")
                yield f"\n[Streaming error: {e}]"
                return

            # Build assistant message
            assistant_message = Message(
                role="assistant", content=full_content if full_content else None
            )

            # Convert accumulated tool calls to ToolCall objects
            if tool_calls_data:
                for idx in sorted(tool_calls_data.keys()):
                    tc_data = tool_calls_data[idx]
                    try:
                        args = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    assistant_message.tool_calls.append(
                        ToolCall(id=tc_data["id"], name=tc_data["name"], arguments=args)
                    )

            self.messages.append(assistant_message)
            logger.debug(
                f"Stream iteration {iteration}: {len(full_content)} chars, "
                f"{len(assistant_message.tool_calls)} tool calls"
            )

            # If no tool calls, we're done
            if not assistant_message.tool_calls or not tools:
                return

            # Execute tool calls
            yield "\n"  # Separator before tool execution
            tool_map = {t.name: t for t in tools}
            for tc in assistant_message.tool_calls:
                if tc.name in tool_map:
                    tool = tool_map[tc.name]
                    yield f"[Executing: {tc.name}...]\n"
                    try:
                        result = tool.handler(**tc.arguments)
                    except Exception as e:
                        result = f"Error executing {tc.name}: {e}"
                else:
                    result = f"Tool not found: {tc.name}"

                # Add tool result to messages
                tool_msg = Message(
                    role="tool",
                    content=result,
                    tool_call_id=tc.id,
                    name=tc.name,
                )
                self.messages.append(tool_msg)

            # Continue loop to get LLM's response after tool execution

        yield "\n[Max tool iterations reached]"

    async def chat_stream(
        self,
        message: str,
        tools: Optional[list[Tool]] = None,
        max_tool_iterations: int = 10,
    ) -> AsyncIterator[str]:
        """
        Chat with asynchronous streaming, including tool call support.

        Yields tokens as they arrive from the LLM.
        If tools are provided and the LLM requests tool calls, executes them
        and continues streaming the follow-up response.

        Args:
            message: User message
            tools: Optional list of tools available to the LLM
            max_tool_iterations: Max tool execution loops (default: 10)
        """
        self.add_message("user", message)
        logger.debug(f"Starting async stream for message: {message[:50]}...")

        iteration = 0
        while iteration < max_tool_iterations:
            iteration += 1

            request_params = {
                "model": self.llm_config.model,
                "messages": [m.to_dict() for m in self.messages],
                "temperature": self.llm_config.temperature,
                "stream": True,
            }

            if tools:
                request_params["tools"] = [t.to_dict() for t in tools]

            full_content = ""
            tool_calls_data: dict[int, dict] = {}

            try:
                stream = await self.async_client.chat.completions.create(**request_params)
                async for chunk in stream:
                    if not chunk.choices:
                        continue

                    delta = chunk.choices[0].delta

                    # Handle content
                    if delta.content:
                        full_content += delta.content
                        yield delta.content

                    # Handle tool calls (accumulated from deltas)
                    if delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tool_calls_data:
                                tool_calls_data[idx] = {
                                    "id": "",
                                    "name": "",
                                    "arguments": "",
                                }
                            if tc_delta.id:
                                tool_calls_data[idx]["id"] = tc_delta.id
                            if tc_delta.function:
                                if tc_delta.function.name:
                                    tool_calls_data[idx]["name"] = tc_delta.function.name
                                if tc_delta.function.arguments:
                                    tool_calls_data[idx]["arguments"] += tc_delta.function.arguments

            except (APIConnectionError, APITimeoutError) as e:
                logger.error(f"Async stream error: {e}")
                yield f"\n[Streaming error: {e}]"
                return

            # Build assistant message
            assistant_message = Message(
                role="assistant", content=full_content if full_content else None
            )

            # Convert accumulated tool calls to ToolCall objects
            if tool_calls_data:
                for idx in sorted(tool_calls_data.keys()):
                    tc_data = tool_calls_data[idx]
                    try:
                        args = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    assistant_message.tool_calls.append(
                        ToolCall(id=tc_data["id"], name=tc_data["name"], arguments=args)
                    )

            self.messages.append(assistant_message)
            logger.debug(
                f"Async stream iteration {iteration}: {len(full_content)} chars, "
                f"{len(assistant_message.tool_calls)} tool calls"
            )

            # If no tool calls, we're done
            if not assistant_message.tool_calls or not tools:
                return

            # Execute tool calls
            yield "\n"
            tool_map = {t.name: t for t in tools}
            for tc in assistant_message.tool_calls:
                if tc.name in tool_map:
                    tool = tool_map[tc.name]
                    yield f"[Executing: {tc.name}...]\n"
                    try:
                        result = tool.handler(**tc.arguments)
                    except Exception as e:
                        result = f"Error executing {tc.name}: {e}"
                else:
                    result = f"Tool not found: {tc.name}"

                tool_msg = Message(
                    role="tool",
                    content=result,
                    tool_call_id=tc.id,
                    name=tc.name,
                )
                self.messages.append(tool_msg)

        yield "\n[Max tool iterations reached]"

    def get_token_usage(self) -> dict[str, Any]:
        """Retorna estadísticas de uso de tokens."""
        return token_tracker.summary()
