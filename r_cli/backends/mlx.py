"""
Backend MLX-LM para Apple Silicon.

MLX es el framework de Apple para ML en Apple Silicon (M1/M2/M3/M4).
Ofrece inferencia muy rápida sin necesidad de servidor externo.

Requiere: pip install mlx-lm
"""

import platform
from typing import Iterator, Optional

from r_cli.backends.base import LLMBackend, Message, Tool


class MLXBackend(LLMBackend):
    """
    Backend para MLX-LM en Apple Silicon.

    Ejecuta modelos directamente en el chip, sin servidor.
    Muy rápido en M1/M2/M3/M4.
    """

    name = "mlx"
    supports_tools = False  # MLX-LM no soporta tool calling nativo
    supports_streaming = True

    # Modelos populares compatibles con MLX
    RECOMMENDED_MODELS = {
        "qwen2.5-7b": "mlx-community/Qwen2.5-7B-Instruct-4bit",
        "qwen2.5-14b": "mlx-community/Qwen2.5-14B-Instruct-4bit",
        "qwen2.5-32b": "mlx-community/Qwen2.5-32B-Instruct-4bit",
        "llama3.2-3b": "mlx-community/Llama-3.2-3B-Instruct-4bit",
        "llama3.1-8b": "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
        "mistral-7b": "mlx-community/Mistral-7B-Instruct-v0.3-4bit",
        "codellama-7b": "mlx-community/CodeLlama-7b-Instruct-hf-4bit",
        "phi-3-mini": "mlx-community/Phi-3-mini-4k-instruct-4bit",
        "gemma2-9b": "mlx-community/gemma-2-9b-it-4bit",
    }

    def __init__(
        self,
        model: str = "mlx-community/Qwen2.5-7B-Instruct-4bit",
        **kwargs,
    ):
        # Resolver alias de modelo
        if model in self.RECOMMENDED_MODELS:
            model = self.RECOMMENDED_MODELS[model]

        super().__init__(model, **kwargs)
        self._model = None
        self._tokenizer = None

    @staticmethod
    def is_apple_silicon() -> bool:
        """Verifica si estamos en Apple Silicon."""
        return platform.system() == "Darwin" and platform.machine() == "arm64"

    @staticmethod
    def is_mlx_installed() -> bool:
        """Verifica si mlx-lm está instalado."""
        try:
            import mlx_lm  # noqa: F401

            return True
        except ImportError:
            return False

    def is_available(self) -> bool:
        """Verifica si MLX está disponible."""
        return self.is_apple_silicon() and self.is_mlx_installed()

    def _load_model(self):
        """Carga el modelo en memoria (lazy loading)."""
        if self._model is None:
            try:
                from mlx_lm import load

                self._model, self._tokenizer = load(self.model)
            except Exception as e:
                raise RuntimeError(f"Error cargando modelo MLX: {e}")

    def list_models(self) -> list[str]:
        """Lista modelos recomendados para MLX."""
        return list(self.RECOMMENDED_MODELS.keys())

    def download_model(self, model_name: str) -> bool:
        """Descarga un modelo de Hugging Face para MLX."""
        try:
            from huggingface_hub import snapshot_download

            # Resolver alias
            if model_name in self.RECOMMENDED_MODELS:
                model_name = self.RECOMMENDED_MODELS[model_name]

            print(f"Descargando {model_name}...")
            snapshot_download(model_name)
            print(f"Modelo {model_name} descargado")
            return True
        except Exception as e:
            print(f"Error descargando modelo: {e}")
            return False

    def _build_prompt(self) -> str:
        """Construye el prompt completo desde el historial."""
        # Formato ChatML (compatible con Qwen, Mistral, etc.)
        prompt = ""

        for msg in self.messages:
            if msg.role == "system":
                prompt += f"<|im_start|>system\n{msg.content}<|im_end|>\n"
            elif msg.role == "user":
                prompt += f"<|im_start|>user\n{msg.content}<|im_end|>\n"
            elif msg.role == "assistant":
                prompt += f"<|im_start|>assistant\n{msg.content}<|im_end|>\n"

        # Añadir inicio de respuesta del asistente
        prompt += "<|im_start|>assistant\n"

        return prompt

    def chat(
        self,
        message: str,
        tools: Optional[list[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Message:
        """Envía un mensaje y obtiene respuesta."""
        if not self.is_available():
            return Message(
                role="assistant",
                content="Error: MLX solo está disponible en Apple Silicon (M1/M2/M3/M4)",
            )

        if message:
            self.add_message("user", message)

        try:
            self._load_model()
            from mlx_lm import generate

            prompt = self._build_prompt()

            response = generate(
                self._model,
                self._tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
                temp=temperature,
                verbose=False,
            )

            # Limpiar respuesta (remover tokens especiales)
            response = response.replace("<|im_end|>", "").strip()

            assistant_message = Message(role="assistant", content=response)
            self.messages.append(assistant_message)
            return assistant_message

        except Exception as e:
            return Message(role="assistant", content=f"Error MLX: {e}")

    def chat_stream(
        self,
        message: str,
        tools: Optional[list[Tool]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Iterator[str]:
        """Chat con streaming."""
        if not self.is_available():
            yield "Error: MLX solo está disponible en Apple Silicon"
            return

        if message:
            self.add_message("user", message)

        try:
            self._load_model()
            from mlx_lm import stream_generate

            prompt = self._build_prompt()
            full_content = ""

            for token in stream_generate(
                self._model,
                self._tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
                temp=temperature,
            ):
                # Filtrar tokens especiales
                if "<|im_end|>" in token:
                    break
                if token and not token.startswith("<|"):
                    full_content += token
                    yield token

            self.messages.append(Message(role="assistant", content=full_content))

        except Exception as e:
            yield f"Error: {e}"

    def unload_model(self):
        """Libera el modelo de memoria."""
        self._model = None
        self._tokenizer = None

    @staticmethod
    def get_install_instructions() -> str:
        """Instrucciones de instalación."""
        return """
Para usar MLX-LM en tu Mac con Apple Silicon:

1. Instala mlx-lm:
   pip install mlx-lm

2. Configura R CLI:
   r config --backend mlx --model qwen2.5-7b

Modelos recomendados (4-bit quantized):
- qwen2.5-7b   : Excelente para tareas generales (4GB RAM)
- qwen2.5-14b  : Mejor calidad (8GB RAM)
- llama3.2-3b  : Muy rápido, ligero (2GB RAM)
- codellama-7b : Especializado en código (4GB RAM)
- phi-3-mini   : Compacto y capaz (2GB RAM)
"""
