"""
Backend nativo para Ollama.

Soporta:
- Chat con modelos locales
- Gestión de modelos (list, pull, delete)
- Streaming
- Tool calling (modelos compatibles)
"""

import json
import subprocess
from typing import Iterator, Optional

import requests

from r_cli.backends.base import LLMBackend, Message, Tool, ToolCall


class OllamaBackend(LLMBackend):
    """
    Backend nativo para Ollama.

    Usa la API REST de Ollama directamente para mejor integración.
    """

    name = "ollama"
    supports_tools = True
    supports_streaming = True

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
        **kwargs,
    ):
        super().__init__(model, **kwargs)
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        """Verifica si Ollama está corriendo."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """Lista los modelos instalados en Ollama."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def pull_model(self, model_name: str, stream_progress: bool = True) -> bool:
        """Descarga un modelo de Ollama."""
        try:
            response = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name, "stream": stream_progress},
                stream=stream_progress,
                timeout=None,
            )

            if stream_progress:
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        status = data.get("status", "")
                        if "pulling" in status:
                            completed = data.get("completed", 0)
                            total = data.get("total", 1)
                            pct = (completed / total * 100) if total else 0
                            print(f"\r{status}: {pct:.1f}%", end="", flush=True)
                        elif status == "success":
                            print(f"\n{model_name} descargado correctamente")
                            return True
            else:
                return response.status_code == 200

        except Exception as e:
            print(f"Error descargando modelo: {e}")

        return False

    def delete_model(self, model_name: str) -> bool:
        """Elimina un modelo de Ollama."""
        try:
            response = requests.delete(
                f"{self.base_url}/api/delete",
                json={"name": model_name},
                timeout=30,
            )
            return response.status_code == 200
        except Exception:
            return False

    def model_info(self, model_name: Optional[str] = None) -> dict:
        """Obtiene información de un modelo."""
        try:
            response = requests.post(
                f"{self.base_url}/api/show",
                json={"name": model_name or self.model},
                timeout=10,
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return {}

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

        # Preparar mensajes para Ollama
        ollama_messages = []
        for m in self.messages:
            msg = {"role": m.role, "content": m.content or ""}
            ollama_messages.append(msg)

        request_data = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        # Añadir tools si el modelo las soporta
        if tools:
            request_data["tools"] = [t.to_dict() for t in tools]

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=request_data,
                timeout=120,
            )

            if response.status_code != 200:
                return Message(
                    role="assistant",
                    content=f"Error de Ollama: {response.status_code}",
                )

            data = response.json()
            assistant_message = Message(role="assistant")

            # Extraer contenido
            msg_data = data.get("message", {})
            assistant_message.content = msg_data.get("content", "")

            # Extraer tool calls si existen
            if "tool_calls" in msg_data:
                for i, tc in enumerate(msg_data["tool_calls"]):
                    func = tc.get("function", {})
                    assistant_message.tool_calls.append(
                        ToolCall(
                            id=f"call_{i}",
                            name=func.get("name", ""),
                            arguments=func.get("arguments", {}),
                        )
                    )

            self.messages.append(assistant_message)
            return assistant_message

        except requests.exceptions.Timeout:
            return Message(role="assistant", content="Error: Timeout esperando respuesta de Ollama")
        except Exception as e:
            return Message(role="assistant", content=f"Error conectando con Ollama: {e}")

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

        ollama_messages = []
        for m in self.messages:
            msg = {"role": m.role, "content": m.content or ""}
            ollama_messages.append(msg)

        request_data = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        full_content = ""

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=request_data,
                stream=True,
                timeout=None,
            )

            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    if "message" in data:
                        content = data["message"].get("content", "")
                        if content:
                            full_content += content
                            yield content

                    if data.get("done", False):
                        break

            self.messages.append(Message(role="assistant", content=full_content))

        except Exception as e:
            yield f"Error: {e}"

    @staticmethod
    def start_server() -> bool:
        """Intenta iniciar el servidor Ollama."""
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False

    @staticmethod
    def is_installed() -> bool:
        """Verifica si Ollama está instalado."""
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False
