"""
Agente principal de R CLI.

Orquesta:
- LLM Client para razonamiento
- Skills para ejecución de tareas
- Memory para contexto
- UI para feedback al usuario
"""

import os
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from r_cli.core.config import Config
from r_cli.core.llm import LLMClient, Tool
from r_cli.core.memory import Memory

console = Console()


# System prompt base del agente
SYSTEM_PROMPT = """Eres R, un asistente AI local que funciona 100% offline en la terminal del usuario.

Tu personalidad:
- Directo y eficiente (sin florituras innecesarias)
- Técnicamente competente
- Resolutivo (prefieres actuar a preguntar demasiado)

Capacidades:
- Generar documentos (PDF, LaTeX, Markdown)
- Resumir textos largos
- Escribir y analizar código
- Consultas SQL en lenguaje natural
- Gestionar archivos locales
- Recordar contexto de conversaciones anteriores

Restricciones:
- Solo puedes acceder a archivos locales del usuario
- No tienes acceso a internet
- Responde en el mismo idioma que el usuario

Cuando uses herramientas:
1. Explica brevemente qué vas a hacer
2. Ejecuta la herramienta
3. Reporta el resultado de forma concisa

Si no puedes hacer algo, explica por qué y sugiere alternativas.
"""


class Agent:
    """
    Agente principal que procesa requests del usuario.

    Uso:
    ```python
    agent = Agent()
    response = agent.run("Genera un PDF con el resumen del proyecto")
    ```
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.config.ensure_directories()

        # Componentes core
        self.llm = LLMClient(self.config)
        self.memory = Memory(self.config)

        # Skills registrados (se cargan dinámicamente)
        self.skills: dict[str, Skill] = {}
        self.tools: list[Tool] = []

        # Estado
        self.is_running = False

        # Configurar LLM
        self._setup_llm()

    def _setup_llm(self) -> None:
        """Configura el LLM con el system prompt y contexto."""
        # Cargar sesión anterior si existe
        if self.memory.load_session():
            session_summary = self.memory.get_session_summary()
            full_prompt = f"{SYSTEM_PROMPT}\n\n{session_summary}"
        else:
            full_prompt = SYSTEM_PROMPT

        self.llm.set_system_prompt(full_prompt)

    def register_skill(self, skill: "Skill") -> None:
        """Registra un skill y sus tools."""
        self.skills[skill.name] = skill

        # Agregar tools del skill
        for tool in skill.get_tools():
            self.tools.append(tool)

        console.print(f"[dim]Skill registrado: {skill.name}[/dim]")

    def load_skills(self) -> None:
        """Carga todos los skills disponibles, respetando la configuración."""
        from r_cli.skills import get_all_skills

        for skill_class in get_all_skills():
            try:
                skill = skill_class(self.config)

                # Check if skill is enabled in config
                if not self.config.skills.is_skill_enabled(skill.name):
                    console.print(
                        f"[dim]Skill deshabilitado en config: {skill.name}[/dim]"
                    )
                    continue

                self.register_skill(skill)
            except ImportError as e:
                console.print(
                    f"[yellow]Dependencia faltante para {skill_class.__name__}: {e}[/yellow]"
                )
            except TypeError as e:
                console.print(
                    f"[yellow]Error de configuración en {skill_class.__name__}: {e}[/yellow]"
                )
            except OSError as e:
                console.print(
                    f"[yellow]Error de archivo/IO en {skill_class.__name__}: {e}[/yellow]"
                )
            except Exception as e:
                console.print(
                    f"[yellow]Error inesperado cargando {skill_class.__name__}: {e}[/yellow]"
                )

    def run(self, user_input: str, show_thinking: bool = True) -> str:
        """
        Procesa input del usuario y retorna respuesta.

        Args:
            user_input: Mensaje del usuario
            show_thinking: Si mostrar el proceso de razonamiento

        Returns:
            Respuesta del agente
        """
        # Agregar a memoria
        self.memory.add_short_term(user_input, entry_type="user_input")

        # Obtener contexto relevante
        context = self.memory.get_relevant_context(user_input)

        # Preparar mensaje con contexto
        if context:
            augmented_input = f"{user_input}\n\n[Contexto disponible]\n{context}"
        else:
            augmented_input = user_input

        # Ejecutar con tools si hay skills registrados
        if self.tools:
            response = self.llm.chat_with_tools(augmented_input, self.tools)
        else:
            response_msg = self.llm.chat(augmented_input)
            response = response_msg.content or ""

        # Agregar respuesta a memoria
        self.memory.add_short_term(response, entry_type="agent_response")

        # Guardar sesión
        self.memory.save_session()

        return response

    def run_stream(self, user_input: str):
        """
        Procesa input del usuario con streaming.

        Yields chunks de la respuesta a medida que llegan.

        Args:
            user_input: Mensaje del usuario

        Yields:
            Chunks de texto de la respuesta
        """
        # Agregar a memoria
        self.memory.add_short_term(user_input, entry_type="user_input")

        # Obtener contexto relevante
        context = self.memory.get_relevant_context(user_input)

        # Preparar mensaje con contexto
        if context:
            augmented_input = f"{user_input}\n\n[Contexto disponible]\n{context}"
        else:
            augmented_input = user_input

        # Usar streaming (sin tools para streaming simple)
        full_response = ""
        for chunk in self.llm.chat_stream_sync(augmented_input):
            full_response += chunk
            yield chunk

        # Agregar respuesta completa a memoria
        self.memory.add_short_term(full_response, entry_type="agent_response")

        # Guardar sesión
        self.memory.save_session()

    def run_skill_directly(self, skill_name: str, **kwargs) -> str:
        """
        Ejecuta un skill directamente sin pasar por el LLM.

        Útil para comandos directos como: r pdf "contenido"
        """
        if skill_name not in self.skills:
            return f"Skill no encontrado: {skill_name}"

        skill = self.skills[skill_name]
        return skill.execute(**kwargs)

    def check_connection(self) -> bool:
        """Verifica conexión con el servidor LLM."""
        return self.llm._check_connection()

    def get_available_skills(self) -> list[str]:
        """Retorna lista de skills disponibles."""
        return list(self.skills.keys())

    def show_help(self) -> None:
        """Muestra ayuda sobre skills disponibles."""
        help_text = "# Skills Disponibles\n\n"

        for name, skill in self.skills.items():
            help_text += f"## {name}\n"
            help_text += f"{skill.description}\n\n"
            help_text += f"**Uso:** `r {name} <args>`\n\n"

        console.print(Panel(Markdown(help_text), title="R CLI Help", border_style="blue"))


class Skill:
    """
    Clase base para skills.

    Los skills son mini-programas especializados que el agente puede usar.

    Ejemplo de implementación:
    ```python
    class PDFSkill(Skill):
        name = "pdf"
        description = "Genera documentos PDF"

        def get_tools(self) -> list[Tool]:
            return [
                Tool(
                    name="generate_pdf",
                    description="Genera un PDF",
                    parameters={...},
                    handler=self.generate_pdf,
                )
            ]

        def generate_pdf(self, content: str, output: str) -> str:
            # Implementación
            return f"PDF generado: {output}"
    ```
    """

    name: str = "base_skill"
    description: str = "Skill base"

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.output_dir = os.path.expanduser(self.config.output_dir)

    def get_tools(self) -> list[Tool]:
        """Retorna las tools que este skill provee."""
        return []

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill (sin LLM)."""
        return "Not implemented"
