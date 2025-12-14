"""
Clase base abstracta para backends de LLM.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional


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
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

    def to_dict(self) -> dict:
        """Convierte a formato compatible."""
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
    parameters: dict[str, Any]
    handler: Callable[..., str]

    def to_dict(self) -> dict:
        """Convierte a formato OpenAI-compatible."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class LLMBackend(ABC):
    """
    Clase base abstracta para backends de LLM.

    Todos los backends deben implementar estos métodos.
    """

    name: str = "base"
    supports_tools: bool = False
    supports_streaming: bool = False

    def __init__(self, model: str, **kwargs):
        self.model = model
        self.messages: list[Message] = []
        self.config = kwargs

    @abstractmethod
    def is_available(self) -> bool:
        """Verifica si el backend está disponible."""

    @abstractmethod
    def list_models(self) -> list[str]:
        """Lista los modelos disponibles."""

    @abstractmethod
    def chat(
        self,
        message: str,
        tools: Optional[list[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Message:
        """Envía un mensaje y obtiene respuesta."""

    def chat_stream(
        self,
        message: str,
        tools: Optional[list[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Iterator[str]:
        """Chat con streaming. Por defecto, no implementado."""
        response = self.chat(message, tools, temperature, max_tokens)
        if response.content:
            yield response.content

    def set_system_prompt(self, prompt: str) -> None:
        """Establece el prompt del sistema."""
        self.messages = [m for m in self.messages if m.role != "system"]
        self.messages.insert(0, Message(role="system", content=prompt))

    def add_message(self, role: str, content: str) -> None:
        """Agrega un mensaje al historial."""
        self.messages.append(Message(role=role, content=content))

    def clear_history(self) -> None:
        """Limpia el historial manteniendo el system prompt."""
        self.messages = [m for m in self.messages if m.role == "system"]

    def execute_tools(self, tool_calls: list[ToolCall], tools: list[Tool]) -> list[Message]:
        """Ejecuta las tools llamadas."""
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
        """Chat completo con ejecución automática de tools."""
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            response = self.chat(message if iteration == 1 else "", tools=tools)

            if response.tool_calls:
                self.execute_tools(response.tool_calls, tools)
                message = ""  # Continuar sin nuevo mensaje
            else:
                return response.content or ""

        return "Se alcanzó el límite de iteraciones"
