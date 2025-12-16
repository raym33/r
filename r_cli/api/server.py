"""
R CLI API Server - FastAPI daemon for R Agent Runtime.

Usage:
    r serve                    # Start API server
    r serve --port 8080        # Custom port
    r serve --host 0.0.0.0     # Listen on all interfaces
"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from r_cli import __version__
from r_cli.api.models import (
    ChatChoice,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatStreamChoice,
    ChatStreamDelta,
    ChatStreamResponse,
    ChatUsage,
    ErrorDetail,
    ErrorResponse,
    HealthStatus,
    LLMStatus,
    SkillInfo,
    SkillsResponse,
    StatusResponse,
    ToolCallRequest,
    ToolCallResponse,
    ToolInfo,
    ToolParameter,
)
from r_cli.core.agent import Agent
from r_cli.core.config import Config

# Global state
_agent: Optional[Agent] = None
_start_time: float = 0
_config: Optional[Config] = None


def get_agent() -> Agent:
    """Get or create the global agent instance."""
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return _agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _agent, _start_time, _config

    # Startup
    _start_time = time.time()
    _config = Config.load()

    # Create agent with all skills
    _agent = Agent(_config)
    _agent.load_skills()

    yield

    # Shutdown
    _agent = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="R CLI API",
        description="REST API for R Agent Runtime - Your Local AI Operating System",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure as needed
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    register_routes(app)

    return app


def register_routes(app: FastAPI) -> None:
    """Register all API routes."""

    # ========================================================================
    # Health & Status
    # ========================================================================

    @app.get("/", tags=["Health"])
    async def root():
        """Root endpoint - basic health check."""
        return {"message": "R CLI API", "version": __version__, "docs": "/docs"}

    @app.get("/health", tags=["Health"])
    async def health():
        """Simple health check."""
        return {"status": "ok"}

    @app.get("/v1/status", response_model=StatusResponse, tags=["Status"])
    async def get_status():
        """Get detailed server status."""
        agent = get_agent()
        uptime = time.time() - _start_time

        # Check LLM connection
        llm_connected = agent.check_connection()
        llm_status = LLMStatus(
            connected=llm_connected,
            backend=_config.llm.provider if _config else None,
            model=_config.llm.model if _config else None,
            base_url=_config.llm.base_url if _config else None,
        )

        status = HealthStatus.HEALTHY if llm_connected else HealthStatus.DEGRADED

        return StatusResponse(
            status=status,
            version=__version__,
            uptime_seconds=uptime,
            llm=llm_status,
            skills_loaded=len(agent.skills),
            timestamp=datetime.now(),
        )

    # ========================================================================
    # Chat Completions
    # ========================================================================

    @app.post("/v1/chat", tags=["Chat"])
    async def chat_completions(request: ChatRequest):
        """
        Chat completion endpoint.

        Compatible with OpenAI's chat completions API.
        Supports streaming responses.
        """
        agent = get_agent()

        # Build conversation
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        # Get the last user message
        user_message = None
        for msg in reversed(messages):
            if msg["role"] == "user":
                user_message = msg["content"]
                break

        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found")

        # Generate response ID
        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        model = request.model or (_config.llm.model if _config else "unknown")

        if request.stream:
            return StreamingResponse(
                stream_chat_response(agent, user_message, response_id, created, model),
                media_type="text/event-stream",
            )
        else:
            # Non-streaming response
            response_text = await asyncio.to_thread(agent.run, user_message)

            return ChatResponse(
                id=response_id,
                created=created,
                model=model,
                choices=[
                    ChatChoice(
                        index=0,
                        message=ChatMessage(role="assistant", content=response_text),
                        finish_reason="stop",
                    )
                ],
                usage=ChatUsage(
                    prompt_tokens=len(user_message.split()),  # Approximate
                    completion_tokens=len(response_text.split()),
                    total_tokens=len(user_message.split()) + len(response_text.split()),
                ),
            )

    async def stream_chat_response(
        agent: Agent,
        user_message: str,
        response_id: str,
        created: int,
        model: str,
    ) -> AsyncGenerator[str, None]:
        """Generate streaming chat response."""
        # Send role first
        initial_chunk = ChatStreamResponse(
            id=response_id,
            created=created,
            model=model,
            choices=[
                ChatStreamChoice(
                    index=0,
                    delta=ChatStreamDelta(role="assistant"),
                )
            ],
        )
        yield f"data: {initial_chunk.model_dump_json()}\n\n"

        # Run sync generator in thread
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        async def producer():
            def run():
                try:
                    for chunk in agent.run_stream(user_message):
                        asyncio.run_coroutine_threadsafe(queue.put(chunk), loop)
                    asyncio.run_coroutine_threadsafe(queue.put(None), loop)
                except Exception as e:
                    asyncio.run_coroutine_threadsafe(queue.put(e), loop)

            await asyncio.to_thread(run)

        # Start producer (keep reference to prevent GC)
        producer_task = asyncio.create_task(producer())

        # Consume chunks
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item

            chunk_response = ChatStreamResponse(
                id=response_id,
                created=created,
                model=model,
                choices=[
                    ChatStreamChoice(
                        index=0,
                        delta=ChatStreamDelta(content=item),
                    )
                ],
            )
            yield f"data: {chunk_response.model_dump_json()}\n\n"

        # Send finish
        final_chunk = ChatStreamResponse(
            id=response_id,
            created=created,
            model=model,
            choices=[
                ChatStreamChoice(
                    index=0,
                    delta=ChatStreamDelta(),
                    finish_reason="stop",
                )
            ],
        )
        yield f"data: {final_chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

        # Ensure producer task is complete
        await producer_task

    # ========================================================================
    # Skills
    # ========================================================================

    @app.get("/v1/skills", response_model=SkillsResponse, tags=["Skills"])
    async def list_skills():
        """List all available skills and their tools."""
        agent = get_agent()

        skills_list = []
        for name, skill in agent.skills.items():
            tools = []
            for tool in skill.get_tools():
                params = []
                if tool.parameters and "properties" in tool.parameters:
                    required = tool.parameters.get("required", [])
                    for param_name, param_info in tool.parameters["properties"].items():
                        params.append(
                            ToolParameter(
                                name=param_name,
                                type=param_info.get("type", "string"),
                                description=param_info.get("description", ""),
                                required=param_name in required,
                                default=param_info.get("default"),
                            )
                        )
                tools.append(
                    ToolInfo(
                        name=tool.name,
                        description=tool.description,
                        parameters=params,
                    )
                )

            skills_list.append(
                SkillInfo(
                    name=name,
                    description=skill.description,
                    tools=tools,
                )
            )

        return SkillsResponse(total=len(skills_list), skills=skills_list)

    @app.get("/v1/skills/{skill_name}", response_model=SkillInfo, tags=["Skills"])
    async def get_skill(skill_name: str):
        """Get details about a specific skill."""
        agent = get_agent()

        if skill_name not in agent.skills:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")

        skill = agent.skills[skill_name]
        tools = []
        for tool in skill.get_tools():
            params = []
            if tool.parameters and "properties" in tool.parameters:
                required = tool.parameters.get("required", [])
                for param_name, param_info in tool.parameters["properties"].items():
                    params.append(
                        ToolParameter(
                            name=param_name,
                            type=param_info.get("type", "string"),
                            description=param_info.get("description", ""),
                            required=param_name in required,
                            default=param_info.get("default"),
                        )
                    )
            tools.append(
                ToolInfo(
                    name=tool.name,
                    description=tool.description,
                    parameters=params,
                )
            )

        return SkillInfo(
            name=skill_name,
            description=skill.description,
            tools=tools,
        )

    @app.post("/v1/skills/call", response_model=ToolCallResponse, tags=["Skills"])
    async def call_tool(request: ToolCallRequest):
        """
        Call a specific tool directly.

        This bypasses the LLM and calls the tool handler directly.
        """
        agent = get_agent()
        start_time = time.time()

        if request.skill not in agent.skills:
            return ToolCallResponse(
                success=False,
                error=f"Skill not found: {request.skill}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        skill = agent.skills[request.skill]

        # Find the tool
        target_tool = None
        for tool in skill.get_tools():
            if tool.name == request.tool:
                target_tool = tool
                break

        if not target_tool:
            return ToolCallResponse(
                success=False,
                error=f"Tool not found: {request.tool} in skill {request.skill}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            # Call the tool handler
            result = await asyncio.to_thread(target_tool.handler, **request.arguments)
            return ToolCallResponse(
                success=True,
                result=result,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return ToolCallResponse(
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    # ========================================================================
    # Error Handlers
    # ========================================================================

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return ErrorResponse(
            error=ErrorDetail(
                code=f"HTTP_{exc.status_code}",
                message=exc.detail,
            )
        )


def run_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    reload: bool = False,
    workers: int = 1,
) -> None:
    """Run the API server."""
    import uvicorn

    uvicorn.run(
        "r_cli.api.server:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level="info",
    )


if __name__ == "__main__":
    run_server()
