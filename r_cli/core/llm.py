"""
Cliente LLM para R CLI.

Abstracción sobre OpenAI SDK que funciona con:
- LM Studio
- Ollama
- Cualquier servidor OpenAI-compatible

Soporta:
- Chat completions
- Tool calling (function calling)
- Streaming
"""

import json
from typing import Any, AsyncIterator, Callable, Optional
from dataclasses import dataclass, field
from openai import OpenAI, AsyncOpenAI
from rich.console import Console

from r_cli.core.config import Config, LLMConfig

console = Console()


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
    tool_call_id: Optional[str] = None  # Para respuestas de tools
    name: Optional[str] = None  # Nombre de la tool (para role=tool)

    def to_dict(self) -> dict:
        """Convierte a formato OpenAI API."""
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
        """Convierte a formato OpenAI API."""
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

        # Cliente síncrono
        self.client = OpenAI(
            base_url=self.llm_config.base_url,
            api_key=self.llm_config.api_key,
        )

        # Cliente asíncrono
        self.async_client = AsyncOpenAI(
            base_url=self.llm_config.base_url,
            api_key=self.llm_config.api_key,
        )

        # Historial de mensajes
        self.messages: list[Message] = []

    def _check_connection(self) -> bool:
        """Verifica si el servidor LLM está disponible."""
        try:
            self.client.models.list()
            return True
        except Exception:
            return False

    def set_system_prompt(self, prompt: str) -> None:
        """Establece el prompt del sistema."""
        # Remover system prompt anterior si existe
        self.messages = [m for m in self.messages if m.role != "system"]
        # Agregar nuevo
        self.messages.insert(0, Message(role="system", content=prompt))

    def add_message(self, role: str, content: str) -> None:
        """Agrega un mensaje al historial."""
        self.messages.append(Message(role=role, content=content))

    def clear_history(self) -> None:
        """Limpia el historial manteniendo el system prompt."""
        system_msgs = [m for m in self.messages if m.role == "system"]
        self.messages = system_msgs

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

        # Llamar al LLM
        try:
            response = self.client.chat.completions.create(**request_params)
        except Exception as e:
            error_msg = f"Error conectando con LLM: {e}"
            console.print(f"[red]{error_msg}[/red]")
            return Message(role="assistant", content=error_msg)

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
                    args = {}

                assistant_message.tool_calls.append(
                    ToolCall(id=tc.id, name=tc.function.name, arguments=args)
                )

        # Agregar al historial
        self.messages.append(assistant_message)

        return assistant_message

    def execute_tools(
        self, tool_calls: list[ToolCall], tools: list[Tool]
    ) -> list[Message]:
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
                    return f"Error: {e}"

            # Si hay tool calls, ejecutarlas
            if response.tool_calls:
                self.execute_tools(response.tool_calls, tools)
            else:
                # No hay tool calls, respuesta final
                return response.content or ""

        return "Se alcanzó el límite de iteraciones"

    async def chat_stream(
        self, message: str, tools: Optional[list[Tool]] = None
    ) -> AsyncIterator[str]:
        """Chat con streaming de respuesta."""
        self.add_message("user", message)

        request_params = {
            "model": self.llm_config.model,
            "messages": [m.to_dict() for m in self.messages],
            "temperature": self.llm_config.temperature,
            "stream": True,
        }

        if tools:
            request_params["tools"] = [t.to_dict() for t in tools]

        full_content = ""

        async with self.async_client.chat.completions.create(**request_params) as stream:
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    yield content

        # Agregar al historial
        self.messages.append(Message(role="assistant", content=full_content))
