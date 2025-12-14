"""
Multi-Agent Skill for R CLI.

Exposes multi-agent orchestration functionality as a skill.
Allows users to interact with multiple specialized agents.
"""

from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool
from r_cli.core.orchestrator import Orchestrator


class MultiAgentSkill(Skill):
    """Skill for multi-agent orchestration."""

    name = "multiagent"
    description = "Orchestrate multiple specialized agents for complex tasks"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orchestrator: Optional[Orchestrator] = None

    def _get_orchestrator(self) -> Orchestrator:
        """Get or initialize the orchestrator."""
        if self._orchestrator is None:
            from r_cli.core.llm import LLMClient

            llm = LLMClient(self.config)
            self._orchestrator = Orchestrator(llm)
        return self._orchestrator

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="ask_agent",
                description="Send a task to a specific specialized agent",
                parameters={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The task or question for the agent",
                        },
                        "agent": {
                            "type": "string",
                            "enum": [
                                "coordinator",
                                "coder",
                                "writer",
                                "analyst",
                                "researcher",
                                "designer",
                                "planner",
                            ],
                            "description": "The agent to use (optional, auto-detected)",
                        },
                    },
                    "required": ["task"],
                },
                handler=self.ask_agent,
            ),
            Tool(
                name="complex_task",
                description="Process a complex task using multiple agents",
                parameters={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The complex task to process",
                        },
                        "max_steps": {
                            "type": "integer",
                            "description": "Maximum steps/agents to use (default: 5)",
                        },
                    },
                    "required": ["task"],
                },
                handler=self.complex_task,
            ),
            Tool(
                name="list_agents",
                description="List all available specialized agents",
                parameters={"type": "object", "properties": {}},
                handler=self.list_agents,
            ),
            Tool(
                name="agent_conversation",
                description="Start a conversation between agents on a topic",
                parameters={
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "The topic of the conversation",
                        },
                        "agents": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of agents to include",
                        },
                        "rounds": {
                            "type": "integer",
                            "description": "Number of conversation rounds (default: 3)",
                        },
                    },
                    "required": ["topic"],
                },
                handler=self.agent_conversation,
            ),
            Tool(
                name="get_history",
                description="Get the multi-agent conversation history",
                parameters={"type": "object", "properties": {}},
                handler=self.get_history,
            ),
            Tool(
                name="clear_agents",
                description="Clear the history of all agents",
                parameters={"type": "object", "properties": {}},
                handler=self.clear_agents,
            ),
        ]

    def ask_agent(
        self,
        task: str,
        agent: Optional[str] = None,
    ) -> str:
        """Send a task to a specific agent."""
        try:
            orchestrator = self._get_orchestrator()
            result = orchestrator.process_task_sync(task, agent_id=agent)

            response = [f"Agent: {result.agent_name}"]
            response.append(f"Time: {result.execution_time:.2f}s")
            response.append("-" * 40)
            response.append(result.result)

            return "\n".join(response)

        except Exception as e:
            return f"Error processing task: {e}"

    def complex_task(
        self,
        task: str,
        max_steps: int = 5,
    ) -> str:
        """Process a complex task with multiple agents."""
        try:
            orchestrator = self._get_orchestrator()
            results = orchestrator.process_complex_task_sync(task, max_iterations=max_steps)

            if not results:
                return "No results obtained."

            response = [f"Task processed with {len(results)} steps:\n"]

            for i, result in enumerate(results, 1):
                response.append(f"Step {i} - {result.agent_name}:")
                response.append(f"  Time: {result.execution_time:.2f}s")
                # Truncate long result
                result_text = result.result
                if len(result_text) > 500:
                    result_text = result_text[:500] + "..."
                response.append(f"  {result_text}")
                response.append("")

            # Total time
            total_time = sum(r.execution_time for r in results)
            response.append(f"Total time: {total_time:.2f}s")

            return "\n".join(response)

        except Exception as e:
            return f"Error processing complex task: {e}"

    def list_agents(self) -> str:
        """List available agents."""
        try:
            orchestrator = self._get_orchestrator()
            return orchestrator.list_agents()
        except Exception as e:
            return f"Error listing agents: {e}"

    def agent_conversation(
        self,
        topic: str,
        agents: Optional[list] = None,
        rounds: int = 3,
    ) -> str:
        """Start a conversation between agents."""
        try:
            orchestrator = self._get_orchestrator()

            # Default agents
            if not agents:
                agents = ["researcher", "analyst", "writer"]

            # Validate agents
            available = list(orchestrator.agents.keys())
            agents = [a for a in agents if a in available]

            if len(agents) < 2:
                return "Error: At least 2 valid agents are required for a conversation."

            conversation = [f"Multi-agent conversation about: {topic}\n"]
            conversation.append(f"Participants: {', '.join(agents)}")
            conversation.append("=" * 50 + "\n")

            context = {"topic": topic, "previous_responses": []}

            for round_num in range(1, rounds + 1):
                conversation.append(f"--- Round {round_num} ---\n")

                for agent_id in agents:
                    # Build prompt with context
                    if round_num == 1 and agent_id == agents[0]:
                        prompt = f"Start a discussion about: {topic}"
                    else:
                        previous = (
                            context["previous_responses"][-3:]
                            if context["previous_responses"]
                            else []
                        )
                        prev_text = "\n".join(
                            [f"{p['agent']}: {p['response'][:200]}..." for p in previous]
                        )
                        prompt = f"""Continue the conversation about "{topic}".

Previous responses:
{prev_text}

Add your perspective as {agent_id}. Be concise (max 150 words)."""

                    result = orchestrator.process_task_sync(prompt, agent_id=agent_id)

                    # Truncate response
                    response_text = result.result
                    if len(response_text) > 400:
                        response_text = response_text[:400] + "..."

                    conversation.append(f"{result.agent_name}:")
                    conversation.append(f"  {response_text}")
                    conversation.append("")

                    # Add to context
                    context["previous_responses"].append(
                        {
                            "agent": result.agent_name,
                            "response": result.result,
                        }
                    )

            conversation.append("=" * 50)
            conversation.append("End of conversation")

            return "\n".join(conversation)

        except Exception as e:
            return f"Error in multi-agent conversation: {e}"

    def get_history(self) -> str:
        """Get conversation history."""
        try:
            orchestrator = self._get_orchestrator()
            return orchestrator.get_conversation_summary()
        except Exception as e:
            return f"Error getting history: {e}"

    def clear_agents(self) -> str:
        """Clear the history of all agents."""
        try:
            orchestrator = self._get_orchestrator()
            orchestrator.clear_all_history()
            return "History of all agents cleared."
        except Exception as e:
            return f"Error clearing history: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        task = kwargs.get("task")
        agent = kwargs.get("agent")
        complex_mode = kwargs.get("complex", False)

        if not task:
            return self.list_agents()

        if complex_mode:
            return self.complex_task(task, kwargs.get("steps", 5))
        else:
            return self.ask_agent(task, agent)
