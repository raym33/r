"""
Backend OpenAI-compatible para LM Studio, vLLM, etc.
"""

import json
from typing import Iterator, Optional

from r_cli.backends.base import LLMBackend, Message, Tool, ToolCall


class OpenAICompatBackend(LLMBackend):
    """
    Backend para servidores OpenAI-compatible.

    Funciona con:
    - LM Studio
    - vLLM
    - LocalAI
    - text-generation-webui con extensión openai
    """

    name = "openai-compatible"
    supports_tools = True
    supports_streaming = True

    def __init__(
        self,
        model: str = "local-model",
        base_url: str = "http://localhost:1234/v1",
        api_key: str = "not-needed",
        **kwargs,
    ):
        super().__init__(model, **kwargs)
        self.base_url = base_url
        self.api_key = api_key
        self._client = None

    @property
    def client(self):
        """Lazy load del cliente OpenAI."""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        return self._client

    def is_available(self) -> bool:
        """Verifica si el servidor está disponible."""
        try:
            self.client.models.list()
            return True
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """Lista los modelos disponibles."""
        try:
            models = self.client.models.list()
            return [m.id for m in models.data]
        except Exception:
            return []

    def chat(
        self,
        message: str,
        tools: Optional[list[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Message:
        """Envía un mensaje y obtiene respuesta."""
        if message:
            self.add_message("user", message)

        request_params = {
            "model": self.model,
            "messages": [m.to_dict() for m in self.messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            request_params["tools"] = [t.to_dict() for t in tools]
            request_params["tool_choice"] = "auto"

        try:
            response = self.client.chat.completions.create(**request_params)
        except Exception as e:
            error_msg = f"Error conectando con LLM: {e}"
            return Message(role="assistant", content=error_msg)

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

        self.messages.append(assistant_message)
        return assistant_message

    def chat_stream(
        self,
        message: str,
        tools: Optional[list[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Iterator[str]:
        """Chat con streaming."""
        if message:
            self.add_message("user", message)

        request_params = {
            "model": self.model,
            "messages": [m.to_dict() for m in self.messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        full_content = ""

        try:
            stream = self.client.chat.completions.create(**request_params)
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    yield content

            self.messages.append(Message(role="assistant", content=full_content))
        except Exception as e:
            yield f"Error: {e}"
