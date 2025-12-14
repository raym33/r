"""
Skill de Multi-Agente para R CLI.

Expone la funcionalidad de orquestación multi-agente como un skill.
Permite al usuario interactuar con múltiples agentes especializados.
"""

from typing import Optional, Dict, Any
from r_cli.core.agent import Skill
from r_cli.core.llm import Tool
from r_cli.core.orchestrator import Orchestrator, AgentRole


class MultiAgentSkill(Skill):
    """Skill para orquestación multi-agente."""

    name = "multiagent"
    description = "Orquesta múltiples agentes especializados para tareas complejas"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orchestrator: Optional[Orchestrator] = None

    def _get_orchestrator(self) -> Orchestrator:
        """Obtiene o inicializa el orquestador."""
        if self._orchestrator is None:
            from r_cli.core.llm import LLMClient
            llm = LLMClient(self.config)
            self._orchestrator = Orchestrator(llm)
        return self._orchestrator

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="ask_agent",
                description="Envía una tarea a un agente especializado específico",
                parameters={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "La tarea o pregunta para el agente",
                        },
                        "agent": {
                            "type": "string",
                            "enum": ["coordinator", "coder", "writer", "analyst", "researcher", "designer", "planner"],
                            "description": "El agente a usar (opcional, se auto-detecta)",
                        },
                    },
                    "required": ["task"],
                },
                handler=self.ask_agent,
            ),
            Tool(
                name="complex_task",
                description="Procesa una tarea compleja usando múltiples agentes",
                parameters={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "La tarea compleja a procesar",
                        },
                        "max_steps": {
                            "type": "integer",
                            "description": "Máximo de pasos/agentes a usar (default: 5)",
                        },
                    },
                    "required": ["task"],
                },
                handler=self.complex_task,
            ),
            Tool(
                name="list_agents",
                description="Lista todos los agentes especializados disponibles",
                parameters={"type": "object", "properties": {}},
                handler=self.list_agents,
            ),
            Tool(
                name="agent_conversation",
                description="Inicia una conversación entre agentes sobre un tema",
                parameters={
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "El tema de la conversación",
                        },
                        "agents": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Lista de agentes a incluir",
                        },
                        "rounds": {
                            "type": "integer",
                            "description": "Número de rondas de conversación (default: 3)",
                        },
                    },
                    "required": ["topic"],
                },
                handler=self.agent_conversation,
            ),
            Tool(
                name="get_history",
                description="Obtiene el historial de conversación multi-agente",
                parameters={"type": "object", "properties": {}},
                handler=self.get_history,
            ),
            Tool(
                name="clear_agents",
                description="Limpia el historial de todos los agentes",
                parameters={"type": "object", "properties": {}},
                handler=self.clear_agents,
            ),
        ]

    def ask_agent(
        self,
        task: str,
        agent: Optional[str] = None,
    ) -> str:
        """Envía una tarea a un agente específico."""
        try:
            orchestrator = self._get_orchestrator()
            result = orchestrator.process_task_sync(task, agent_id=agent)

            response = [f"Agente: {result.agent_name}"]
            response.append(f"Tiempo: {result.execution_time:.2f}s")
            response.append("-" * 40)
            response.append(result.result)

            return "\n".join(response)

        except Exception as e:
            return f"Error procesando tarea: {e}"

    def complex_task(
        self,
        task: str,
        max_steps: int = 5,
    ) -> str:
        """Procesa una tarea compleja con múltiples agentes."""
        try:
            orchestrator = self._get_orchestrator()
            results = orchestrator.process_complex_task_sync(task, max_iterations=max_steps)

            if not results:
                return "No se obtuvieron resultados."

            response = [f"Tarea procesada con {len(results)} pasos:\n"]

            for i, result in enumerate(results, 1):
                response.append(f"Paso {i} - {result.agent_name}:")
                response.append(f"  Tiempo: {result.execution_time:.2f}s")
                # Truncar resultado largo
                result_text = result.result
                if len(result_text) > 500:
                    result_text = result_text[:500] + "..."
                response.append(f"  {result_text}")
                response.append("")

            # Total time
            total_time = sum(r.execution_time for r in results)
            response.append(f"Tiempo total: {total_time:.2f}s")

            return "\n".join(response)

        except Exception as e:
            return f"Error procesando tarea compleja: {e}"

    def list_agents(self) -> str:
        """Lista los agentes disponibles."""
        try:
            orchestrator = self._get_orchestrator()
            return orchestrator.list_agents()
        except Exception as e:
            return f"Error listando agentes: {e}"

    def agent_conversation(
        self,
        topic: str,
        agents: Optional[list] = None,
        rounds: int = 3,
    ) -> str:
        """Inicia una conversación entre agentes."""
        try:
            orchestrator = self._get_orchestrator()

            # Agentes por defecto
            if not agents:
                agents = ["researcher", "analyst", "writer"]

            # Validar agentes
            available = list(orchestrator.agents.keys())
            agents = [a for a in agents if a in available]

            if len(agents) < 2:
                return "Error: Se necesitan al menos 2 agentes válidos para una conversación."

            conversation = [f"Conversación multi-agente sobre: {topic}\n"]
            conversation.append(f"Participantes: {', '.join(agents)}")
            conversation.append("=" * 50 + "\n")

            context = {"topic": topic, "previous_responses": []}

            for round_num in range(1, rounds + 1):
                conversation.append(f"--- Ronda {round_num} ---\n")

                for agent_id in agents:
                    # Construir prompt con contexto
                    if round_num == 1 and agent_id == agents[0]:
                        prompt = f"Inicia una discusión sobre: {topic}"
                    else:
                        previous = context["previous_responses"][-3:] if context["previous_responses"] else []
                        prev_text = "\n".join([f"{p['agent']}: {p['response'][:200]}..." for p in previous])
                        prompt = f"""Continúa la conversación sobre "{topic}".

Respuestas anteriores:
{prev_text}

Añade tu perspectiva como {agent_id}. Sé conciso (máximo 150 palabras)."""

                    result = orchestrator.process_task_sync(prompt, agent_id=agent_id)

                    # Truncar respuesta
                    response_text = result.result
                    if len(response_text) > 400:
                        response_text = response_text[:400] + "..."

                    conversation.append(f"{result.agent_name}:")
                    conversation.append(f"  {response_text}")
                    conversation.append("")

                    # Agregar al contexto
                    context["previous_responses"].append({
                        "agent": result.agent_name,
                        "response": result.result,
                    })

            conversation.append("=" * 50)
            conversation.append("Fin de la conversación")

            return "\n".join(conversation)

        except Exception as e:
            return f"Error en conversación multi-agente: {e}"

    def get_history(self) -> str:
        """Obtiene el historial de conversación."""
        try:
            orchestrator = self._get_orchestrator()
            return orchestrator.get_conversation_summary()
        except Exception as e:
            return f"Error obteniendo historial: {e}"

    def clear_agents(self) -> str:
        """Limpia el historial de todos los agentes."""
        try:
            orchestrator = self._get_orchestrator()
            orchestrator.clear_all_history()
            return "Historial de todos los agentes limpiado."
        except Exception as e:
            return f"Error limpiando historial: {e}"

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        task = kwargs.get("task")
        agent = kwargs.get("agent")
        complex_mode = kwargs.get("complex", False)

        if not task:
            return self.list_agents()

        if complex_mode:
            return self.complex_task(task, kwargs.get("steps", 5))
        else:
            return self.ask_agent(task, agent)
