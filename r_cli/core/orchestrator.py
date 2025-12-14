"""
Sistema de Orquestación Multi-Agente para R CLI.

Permite coordinar múltiples agentes especializados que trabajan juntos
para resolver tareas complejas.

Arquitectura:
- Orchestrator: Coordina agentes y decide qué agente usar
- SpecializedAgent: Agentes con habilidades específicas
- TaskRouter: Enruta tareas al agente adecuado
- AgentPool: Pool de agentes disponibles

Todo 100% local, sin dependencias de cloud.
"""

import json
import asyncio
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from r_cli.core.llm import LLMClient, Message


class AgentRole(Enum):
    """Roles de agentes especializados."""
    COORDINATOR = "coordinator"      # Coordina otros agentes
    RESEARCHER = "researcher"        # Busca información
    CODER = "coder"                  # Escribe código
    WRITER = "writer"                # Escribe documentos
    ANALYST = "analyst"              # Analiza datos
    DESIGNER = "designer"            # Diseña/genera imágenes
    PLANNER = "planner"              # Planifica tareas
    REVIEWER = "reviewer"            # Revisa trabajo de otros agentes
    EXECUTOR = "executor"            # Ejecuta acciones


@dataclass
class AgentConfig:
    """Configuración de un agente."""
    name: str
    role: AgentRole
    description: str
    system_prompt: str
    skills: List[str] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 2000


@dataclass
class TaskResult:
    """Resultado de una tarea ejecutada por un agente."""
    agent_name: str
    task: str
    result: str
    success: bool
    execution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMessage:
    """Mensaje entre agentes."""
    from_agent: str
    to_agent: str
    content: str
    message_type: str = "task"  # task, result, question, info
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class SpecializedAgent:
    """Agente especializado con rol específico."""

    def __init__(
        self,
        config: AgentConfig,
        llm_client: LLMClient,
        skills: Optional[Dict[str, Any]] = None,
    ):
        self.config = config
        self.llm = llm_client
        self.skills = skills or {}
        self.conversation_history: List[Message] = []
        self.task_history: List[TaskResult] = []

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def role(self) -> AgentRole:
        return self.config.role

    def get_system_prompt(self) -> str:
        """Genera el system prompt del agente."""
        base = self.config.system_prompt
        skills_info = ""
        if self.config.skills:
            skills_info = f"\n\nSkills disponibles: {', '.join(self.config.skills)}"
        return base + skills_info

    async def process(self, task: str, context: Optional[Dict] = None) -> TaskResult:
        """Procesa una tarea."""
        start_time = datetime.now()

        try:
            # Construir mensajes
            messages = [
                Message(role="system", content=self.get_system_prompt()),
            ]

            # Agregar contexto si existe
            if context:
                context_str = f"Contexto adicional:\n{json.dumps(context, indent=2, ensure_ascii=False)}"
                messages.append(Message(role="system", content=context_str))

            # Agregar historial relevante
            messages.extend(self.conversation_history[-10:])  # Últimos 10 mensajes

            # Agregar tarea actual
            messages.append(Message(role="user", content=task))

            # Obtener respuesta del LLM
            response = await self._get_response(messages)

            # Calcular tiempo
            execution_time = (datetime.now() - start_time).total_seconds()

            # Crear resultado
            result = TaskResult(
                agent_name=self.name,
                task=task,
                result=response,
                success=True,
                execution_time=execution_time,
                metadata={"role": self.role.value},
            )

            # Actualizar historial
            self.conversation_history.append(Message(role="user", content=task))
            self.conversation_history.append(Message(role="assistant", content=response))
            self.task_history.append(result)

            return result

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return TaskResult(
                agent_name=self.name,
                task=task,
                result=f"Error: {str(e)}",
                success=False,
                execution_time=execution_time,
            )

    async def _get_response(self, messages: List[Message]) -> str:
        """Obtiene respuesta del LLM."""
        # Convertir a formato OpenAI
        msgs = [{"role": m.role, "content": m.content} for m in messages]

        response = self.llm.client.chat.completions.create(
            model=self.llm.model,
            messages=msgs,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        return response.choices[0].message.content

    def clear_history(self):
        """Limpia el historial de conversación."""
        self.conversation_history = []


class TaskRouter:
    """Enruta tareas al agente más adecuado."""

    # Palabras clave para cada rol
    ROLE_KEYWORDS = {
        AgentRole.CODER: [
            "código", "code", "programa", "function", "clase", "class",
            "python", "javascript", "bug", "error", "debug", "implementar",
        ],
        AgentRole.WRITER: [
            "escribe", "write", "documento", "artículo", "blog", "email",
            "carta", "resumen", "summary", "redacta", "content",
        ],
        AgentRole.ANALYST: [
            "analiza", "analyze", "datos", "data", "estadística", "statistics",
            "gráfico", "chart", "csv", "excel", "tendencia", "pattern",
        ],
        AgentRole.DESIGNER: [
            "diseña", "design", "imagen", "image", "logo", "ilustración",
            "ui", "ux", "visual", "gráfico", "creative",
        ],
        AgentRole.RESEARCHER: [
            "busca", "search", "investiga", "research", "información",
            "encuentra", "find", "qué es", "what is", "explica",
        ],
        AgentRole.PLANNER: [
            "planifica", "plan", "organiza", "schedule", "proyecto",
            "roadmap", "timeline", "estrategia", "strategy",
        ],
    }

    def route(self, task: str, available_agents: List[SpecializedAgent]) -> SpecializedAgent:
        """Determina el mejor agente para una tarea."""
        task_lower = task.lower()

        # Calcular puntuación para cada rol
        scores = {role: 0 for role in AgentRole}

        for role, keywords in self.ROLE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in task_lower:
                    scores[role] += 1

        # Encontrar rol con mayor puntuación
        best_role = max(scores, key=scores.get)

        # Si no hay coincidencias claras, usar coordinator
        if scores[best_role] == 0:
            best_role = AgentRole.COORDINATOR

        # Buscar agente con ese rol
        for agent in available_agents:
            if agent.role == best_role:
                return agent

        # Fallback: primer agente disponible
        return available_agents[0] if available_agents else None


class Orchestrator:
    """Orquestador principal de agentes."""

    # Configuraciones predefinidas de agentes
    DEFAULT_AGENTS = {
        "coordinator": AgentConfig(
            name="Coordinator",
            role=AgentRole.COORDINATOR,
            description="Coordina tareas complejas y delega a otros agentes",
            system_prompt="""Eres el agente coordinador. Tu trabajo es:
1. Analizar tareas complejas y dividirlas en subtareas
2. Decidir qué agente especializado debe manejar cada subtarea
3. Sintetizar los resultados de múltiples agentes
4. Asegurar que la respuesta final sea coherente y completa

Cuando recibas una tarea:
- Si es simple, resuélvela directamente
- Si es compleja, indica qué subtareas crear y qué agente debería manejarlas
- Siempre proporciona una respuesta clara y útil""",
        ),
        "coder": AgentConfig(
            name="Coder",
            role=AgentRole.CODER,
            description="Especialista en programación y código",
            system_prompt="""Eres un experto programador. Tu trabajo es:
1. Escribir código limpio, eficiente y bien documentado
2. Explicar conceptos de programación claramente
3. Depurar y corregir errores
4. Sugerir mejoras y buenas prácticas

Lenguajes principales: Python, JavaScript, TypeScript, SQL
Siempre incluye comentarios explicativos en tu código.""",
            skills=["code"],
            temperature=0.3,
        ),
        "writer": AgentConfig(
            name="Writer",
            role=AgentRole.WRITER,
            description="Especialista en redacción y contenido",
            system_prompt="""Eres un escritor profesional. Tu trabajo es:
1. Escribir contenido claro, conciso y atractivo
2. Adaptar el tono según el contexto (formal, casual, técnico)
3. Estructurar documentos de manera lógica
4. Corregir y mejorar textos existentes

Siempre verifica ortografía y gramática.""",
            skills=["pdf", "latex", "resume"],
            temperature=0.8,
        ),
        "analyst": AgentConfig(
            name="Analyst",
            role=AgentRole.ANALYST,
            description="Especialista en análisis de datos",
            system_prompt="""Eres un analista de datos experto. Tu trabajo es:
1. Analizar conjuntos de datos y encontrar patrones
2. Crear consultas SQL eficientes
3. Generar insights accionables
4. Explicar hallazgos de manera clara

Siempre respalda tus conclusiones con datos.""",
            skills=["sql"],
            temperature=0.4,
        ),
        "researcher": AgentConfig(
            name="Researcher",
            role=AgentRole.RESEARCHER,
            description="Especialista en investigación",
            system_prompt="""Eres un investigador meticuloso. Tu trabajo es:
1. Buscar y sintetizar información
2. Verificar datos y fuentes
3. Explicar conceptos complejos de forma accesible
4. Proporcionar contexto histórico y actual

Siempre cita tus fuentes cuando sea posible.""",
            skills=["fs", "resume"],
            temperature=0.5,
        ),
        "designer": AgentConfig(
            name="Designer",
            role=AgentRole.DESIGNER,
            description="Especialista en diseño visual",
            system_prompt="""Eres un diseñador creativo. Tu trabajo es:
1. Crear prompts efectivos para generación de imágenes
2. Sugerir paletas de colores y composiciones
3. Asesorar sobre diseño UI/UX
4. Describir conceptos visuales claramente

Siempre considera la audiencia y el propósito del diseño.""",
            skills=["design"],
            temperature=0.9,
        ),
        "planner": AgentConfig(
            name="Planner",
            role=AgentRole.PLANNER,
            description="Especialista en planificación",
            system_prompt="""Eres un planificador estratégico. Tu trabajo es:
1. Crear planes de acción detallados
2. Establecer prioridades y dependencias
3. Estimar tiempos y recursos
4. Identificar riesgos y mitigaciones

Siempre incluye pasos concretos y medibles.""",
            skills=["calendar"],
            temperature=0.5,
        ),
    }

    def __init__(self, llm_client: LLMClient, skills: Optional[Dict] = None):
        self.llm = llm_client
        self.skills = skills or {}
        self.agents: Dict[str, SpecializedAgent] = {}
        self.router = TaskRouter()
        self.message_log: List[AgentMessage] = []
        self._init_agents()

    def _init_agents(self):
        """Inicializa los agentes predefinidos."""
        for agent_id, config in self.DEFAULT_AGENTS.items():
            self.agents[agent_id] = SpecializedAgent(
                config=config,
                llm_client=self.llm,
                skills={s: self.skills.get(s) for s in config.skills if s in self.skills},
            )

    def get_agent(self, agent_id: str) -> Optional[SpecializedAgent]:
        """Obtiene un agente por ID."""
        return self.agents.get(agent_id)

    def list_agents(self) -> str:
        """Lista los agentes disponibles."""
        result = ["Agentes disponibles:\n"]
        for agent_id, agent in self.agents.items():
            result.append(f"  - {agent.name} ({agent.role.value})")
            result.append(f"    {agent.config.description}")
            if agent.config.skills:
                result.append(f"    Skills: {', '.join(agent.config.skills)}")
            result.append("")
        return "\n".join(result)

    async def process_task(
        self,
        task: str,
        agent_id: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> TaskResult:
        """Procesa una tarea, opcionalmente con un agente específico."""
        # Seleccionar agente
        if agent_id and agent_id in self.agents:
            agent = self.agents[agent_id]
        else:
            # Auto-routing
            agent = self.router.route(task, list(self.agents.values()))

        if not agent:
            return TaskResult(
                agent_name="orchestrator",
                task=task,
                result="Error: No hay agentes disponibles",
                success=False,
                execution_time=0,
            )

        # Procesar tarea
        result = await agent.process(task, context)

        # Log del mensaje
        self.message_log.append(AgentMessage(
            from_agent="user",
            to_agent=agent.name,
            content=task,
            message_type="task",
        ))
        self.message_log.append(AgentMessage(
            from_agent=agent.name,
            to_agent="user",
            content=result.result,
            message_type="result",
        ))

        return result

    async def process_complex_task(
        self,
        task: str,
        max_iterations: int = 5,
    ) -> List[TaskResult]:
        """Procesa una tarea compleja usando múltiples agentes."""
        results = []

        # Primero, el coordinador analiza la tarea
        coordinator = self.agents.get("coordinator")
        if not coordinator:
            return [await self.process_task(task)]

        # Análisis inicial
        analysis_prompt = f"""Analiza esta tarea y decide cómo proceder:

Tarea: {task}

Agentes disponibles:
{self.list_agents()}

Responde en formato JSON:
{{
    "is_complex": true/false,
    "subtasks": [
        {{"agent": "agent_id", "task": "descripción de subtarea"}},
        ...
    ],
    "direct_response": "respuesta directa si no es compleja"
}}"""

        analysis_result = await coordinator.process(analysis_prompt)
        results.append(analysis_result)

        # Intentar parsear la respuesta
        try:
            # Buscar JSON en la respuesta
            response_text = analysis_result.result
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                analysis = json.loads(response_text[json_start:json_end])

                if not analysis.get("is_complex", False):
                    # Tarea simple, usar respuesta directa
                    return results

                # Procesar subtareas
                for subtask in analysis.get("subtasks", [])[:max_iterations]:
                    agent_id = subtask.get("agent", "coordinator")
                    subtask_desc = subtask.get("task", "")

                    if subtask_desc:
                        subtask_result = await self.process_task(
                            subtask_desc,
                            agent_id=agent_id,
                            context={"original_task": task},
                        )
                        results.append(subtask_result)

        except json.JSONDecodeError:
            # Si no puede parsear, procesar como tarea simple
            pass

        # Síntesis final si hay múltiples resultados
        if len(results) > 1:
            synthesis_prompt = f"""Sintetiza los siguientes resultados en una respuesta coherente:

Tarea original: {task}

Resultados de los agentes:
{chr(10).join(f'- {r.agent_name}: {r.result[:500]}...' for r in results)}

Proporciona una respuesta final clara y completa."""

            synthesis = await coordinator.process(synthesis_prompt)
            results.append(synthesis)

        return results

    def process_task_sync(
        self,
        task: str,
        agent_id: Optional[str] = None,
        context: Optional[Dict] = None,
    ) -> TaskResult:
        """Versión síncrona de process_task."""
        return asyncio.run(self.process_task(task, agent_id, context))

    def process_complex_task_sync(
        self,
        task: str,
        max_iterations: int = 5,
    ) -> List[TaskResult]:
        """Versión síncrona de process_complex_task."""
        return asyncio.run(self.process_complex_task(task, max_iterations))

    def get_conversation_summary(self) -> str:
        """Obtiene un resumen de la conversación multi-agente."""
        if not self.message_log:
            return "No hay mensajes en el historial."

        result = ["Historial de conversación multi-agente:\n"]

        for msg in self.message_log[-20:]:  # Últimos 20 mensajes
            timestamp = msg.timestamp.split("T")[1][:8] if "T" in msg.timestamp else ""
            result.append(f"[{timestamp}] {msg.from_agent} -> {msg.to_agent}:")
            result.append(f"  {msg.content[:200]}...")
            result.append("")

        return "\n".join(result)

    def clear_all_history(self):
        """Limpia el historial de todos los agentes."""
        for agent in self.agents.values():
            agent.clear_history()
        self.message_log = []
