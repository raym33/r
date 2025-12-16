"""
R CLI API Server - FastAPI daemon for R Agent Runtime.

Usage:
    r serve                    # Start API server
    r serve --port 8080        # Custom port
    r serve --host 0.0.0.0     # Listen on all interfaces
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from r_cli import __version__
from r_cli.api.audit import (
    AuditAction,
    AuditSeverity,
    audit_log,
    get_audit_logger,
)
from r_cli.api.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    AuthResult,
    Token,
    authenticate_user,
    create_access_token,
    get_current_auth,
    get_storage,
    require_auth,
    require_scopes,
)
from r_cli.api.models import (
    ChatChoice,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatStreamChoice,
    ChatStreamDelta,
    ChatStreamResponse,
    ChatUsage,
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
from r_cli.api.permissions import (
    PermissionChecker,
    Scope,
    check_skill_permission,
)
from r_cli.api.rate_limit import RateLimitMiddleware
from r_cli.core.agent import Agent
from r_cli.core.config import Config

# Global state
_agent: Optional[Agent] = None
_start_time: float = 0
_config: Optional[Config] = None

# Auth mode: "none", "optional", "required"
AUTH_MODE = os.getenv("R_AUTH_MODE", "optional")


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

    # Log server start
    audit_log(
        AuditAction.SERVER_STARTED,
        details={"version": __version__, "skills": len(_agent.skills)},
    )

    yield

    # Log server stop
    audit_log(AuditAction.SERVER_STOPPED)

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

    # Rate limiting middleware
    app.add_middleware(RateLimitMiddleware)

    # Register routes
    register_routes(app)

    return app


# ============================================================================
# Auth Models
# ============================================================================


class LoginRequest(BaseModel):
    """Login request."""

    username: str
    password: str


class CreateUserRequest(BaseModel):
    """Create user request."""

    username: str
    password: str
    scopes: list[str] = ["read", "chat"]


class CreateAPIKeyRequest(BaseModel):
    """Create API key request."""

    name: str
    scopes: list[str] = ["read", "chat"]
    expires_in_days: Optional[int] = None


class APIKeyResponse(BaseModel):
    """API key creation response (includes raw key only once)."""

    key: str  # Raw key - only shown once
    key_id: str
    name: str
    scopes: list[str]
    expires_at: Optional[datetime] = None


class APIKeyInfo(BaseModel):
    """API key info (without raw key)."""

    key_id: str
    name: str
    scopes: list[str]
    created_at: datetime
    last_used: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool


# ============================================================================
# Routes
# ============================================================================


def register_routes(app: FastAPI) -> None:
    """Register all API routes."""

    # ========================================================================
    # Health & Status (Public)
    # ========================================================================

    @app.get("/", tags=["Health"])
    async def root():
        """Root endpoint - basic health check."""
        return {
            "message": "R CLI API",
            "version": __version__,
            "docs": "/docs",
            "auth_mode": AUTH_MODE,
        }

    @app.get("/health", tags=["Health"])
    async def health():
        """Simple health check."""
        return {"status": "ok"}

    @app.get("/v1/status", response_model=StatusResponse, tags=["Status"])
    async def get_status(auth: AuthResult = Depends(get_current_auth)):
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

        health_status = HealthStatus.HEALTHY if llm_connected else HealthStatus.DEGRADED

        return StatusResponse(
            status=health_status,
            version=__version__,
            uptime_seconds=uptime,
            llm=llm_status,
            skills_loaded=len(agent.skills),
            timestamp=datetime.now(),
        )

    # ========================================================================
    # Authentication
    # ========================================================================

    @app.post("/auth/login", response_model=Token, tags=["Auth"])
    async def login(request: LoginRequest, req: Request):
        """Login with username and password to get JWT token."""
        user = authenticate_user(request.username, request.password)

        if not user:
            audit_log(
                AuditAction.AUTH_FAILED,
                username=request.username,
                client_ip=req.client.host if req.client else None,
                success=False,
                severity=AuditSeverity.WARNING,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create token
        access_token = create_access_token(
            data={
                "sub": user.user_id,
                "username": user.username,
                "scopes": user.scopes,
            }
        )

        audit_log(
            AuditAction.AUTH_LOGIN,
            user_id=user.user_id,
            username=user.username,
            client_ip=req.client.host if req.client else None,
        )

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @app.get("/auth/me", tags=["Auth"])
    async def get_current_user(auth: AuthResult = Depends(require_auth)):
        """Get current authenticated user info."""
        return {
            "user_id": auth.user_id,
            "username": auth.username,
            "auth_type": auth.auth_type,
            "scopes": auth.scopes,
        }

    @app.post("/auth/users", tags=["Auth"])
    async def create_user(
        request: CreateUserRequest,
        auth: AuthResult = Depends(require_scopes(Scope.ADMIN)),
    ):
        """Create a new user (admin only)."""
        storage = get_storage()

        try:
            user = storage.create_user(
                username=request.username,
                password=request.password,
                scopes=request.scopes,
            )

            audit_log(
                AuditAction.USER_CREATED,
                user_id=auth.user_id,
                username=auth.username,
                resource=request.username,
            )

            return {
                "user_id": user.user_id,
                "username": user.username,
                "scopes": user.scopes,
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/auth/api-keys", response_model=APIKeyResponse, tags=["Auth"])
    async def create_api_key(
        request: CreateAPIKeyRequest,
        auth: AuthResult = Depends(require_auth),
    ):
        """Create a new API key."""
        storage = get_storage()

        # Users can only create keys with their own scopes or subset
        allowed_scopes = set(auth.scopes)
        if Scope.ADMIN not in allowed_scopes:
            requested_scopes = set(request.scopes)
            if not requested_scopes.issubset(allowed_scopes):
                raise HTTPException(
                    status_code=403,
                    detail="Cannot create API key with scopes you don't have",
                )

        raw_key, api_key = storage.create_api_key(
            name=request.name,
            scopes=request.scopes,
            expires_in_days=request.expires_in_days,
        )

        audit_log(
            AuditAction.API_KEY_CREATED,
            user_id=auth.user_id,
            username=auth.username,
            resource=api_key.key_id,
            details={"name": request.name, "scopes": request.scopes},
        )

        return APIKeyResponse(
            key=raw_key,
            key_id=api_key.key_id,
            name=api_key.name,
            scopes=api_key.scopes,
            expires_at=api_key.expires_at,
        )

    @app.get("/auth/api-keys", response_model=list[APIKeyInfo], tags=["Auth"])
    async def list_api_keys(auth: AuthResult = Depends(require_auth)):
        """List all API keys (admin) or own keys."""
        storage = get_storage()
        keys = storage.list_api_keys()

        return [
            APIKeyInfo(
                key_id=k.key_id,
                name=k.name,
                scopes=k.scopes,
                created_at=k.created_at,
                last_used=k.last_used,
                expires_at=k.expires_at,
                is_active=k.is_active,
            )
            for k in keys
        ]

    @app.delete("/auth/api-keys/{key_id}", tags=["Auth"])
    async def revoke_api_key(
        key_id: str,
        auth: AuthResult = Depends(require_auth),
    ):
        """Revoke an API key."""
        storage = get_storage()

        if storage.revoke_api_key(key_id):
            audit_log(
                AuditAction.API_KEY_REVOKED,
                user_id=auth.user_id,
                username=auth.username,
                resource=key_id,
            )
            return {"status": "revoked", "key_id": key_id}

        raise HTTPException(status_code=404, detail="API key not found")

    # ========================================================================
    # Chat Completions
    # ========================================================================

    @app.post("/v1/chat", tags=["Chat"])
    async def chat_completions(
        request: ChatRequest,
        req: Request,
        auth: AuthResult = Depends(get_current_auth),
    ):
        """
        Chat completion endpoint.

        Compatible with OpenAI's chat completions API.
        Supports streaming responses.
        """
        # Check auth if required
        if AUTH_MODE == "required" and not auth.authenticated:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
            )

        # Check chat permission
        if auth.authenticated:
            checker = PermissionChecker(auth.scopes)
            if not checker.can_chat(streaming=request.stream):
                raise HTTPException(
                    status_code=403,
                    detail="Missing chat permission",
                )

        agent = get_agent()
        start_time = time.time()

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

        # Log the request
        audit_log(
            AuditAction.CHAT_REQUEST,
            user_id=auth.user_id if auth.authenticated else None,
            username=auth.username if auth.authenticated else None,
            auth_type=auth.auth_type if auth.authenticated else None,
            client_ip=req.client.host if req.client else None,
            details={"stream": request.stream, "message_length": len(user_message)},
        )

        # Generate response ID
        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        model = request.model or (_config.llm.model if _config else "unknown")

        if request.stream:
            return StreamingResponse(
                stream_chat_response(
                    agent, user_message, response_id, created, model, auth, start_time
                ),
                media_type="text/event-stream",
            )
        else:
            # Non-streaming response
            response_text = await asyncio.to_thread(agent.run, user_message)
            duration_ms = (time.time() - start_time) * 1000

            audit_log(
                AuditAction.CHAT_RESPONSE,
                user_id=auth.user_id if auth.authenticated else None,
                username=auth.username if auth.authenticated else None,
                duration_ms=duration_ms,
                details={"response_length": len(response_text)},
            )

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
                    prompt_tokens=len(user_message.split()),
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
        auth: AuthResult,
        start_time: float,
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

        # Start producer
        producer_task = asyncio.create_task(producer())

        # Consume chunks
        total_content = ""
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item

            total_content += item
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

        # Log completion
        duration_ms = (time.time() - start_time) * 1000
        audit_log(
            AuditAction.CHAT_RESPONSE,
            user_id=auth.user_id if auth.authenticated else None,
            username=auth.username if auth.authenticated else None,
            duration_ms=duration_ms,
            details={"response_length": len(total_content), "stream": True},
        )

        await producer_task

    # ========================================================================
    # Skills
    # ========================================================================

    @app.get("/v1/skills", response_model=SkillsResponse, tags=["Skills"])
    async def list_skills(auth: AuthResult = Depends(get_current_auth)):
        """List all available skills and their tools."""
        agent = get_agent()

        # Filter skills based on permissions if authenticated
        checker = None
        if auth.authenticated:
            checker = PermissionChecker(auth.scopes)

        skills_list = []
        for name, skill in agent.skills.items():
            # Check permission
            if checker and not checker.can_use_skill(name):
                continue

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
    async def get_skill(skill_name: str, auth: AuthResult = Depends(get_current_auth)):
        """Get details about a specific skill."""
        agent = get_agent()

        if skill_name not in agent.skills:
            raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")

        # Check permission
        if auth.authenticated:
            checker = PermissionChecker(auth.scopes)
            if not checker.can_use_skill(skill_name):
                raise HTTPException(
                    status_code=403,
                    detail=f"No permission for skill: {skill_name}",
                )

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
    async def call_tool(
        request: ToolCallRequest,
        req: Request,
        auth: AuthResult = Depends(get_current_auth),
    ):
        """
        Call a specific tool directly.

        This bypasses the LLM and calls the tool handler directly.
        """
        # Check auth if required
        if AUTH_MODE == "required" and not auth.authenticated:
            raise HTTPException(status_code=401, detail="Authentication required")

        agent = get_agent()
        start_time = time.time()

        # Check skill permission
        if auth.authenticated:
            allowed, reason = check_skill_permission(request.skill, auth.scopes)
            if not allowed:
                audit_log(
                    AuditAction.SKILL_DENIED,
                    user_id=auth.user_id,
                    username=auth.username,
                    resource=request.skill,
                    details={"tool": request.tool, "reason": reason},
                    success=False,
                    severity=AuditSeverity.WARNING,
                )
                return ToolCallResponse(
                    success=False,
                    error=reason,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

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

        # Log skill call
        audit_log(
            AuditAction.SKILL_CALLED,
            user_id=auth.user_id if auth.authenticated else None,
            username=auth.username if auth.authenticated else None,
            client_ip=req.client.host if req.client else None,
            resource=request.skill,
            resource_id=request.tool,
            details={"arguments": list(request.arguments.keys())},
        )

        try:
            # Call the tool handler
            result = await asyncio.to_thread(target_tool.handler, **request.arguments)
            duration_ms = (time.time() - start_time) * 1000

            audit_log(
                AuditAction.SKILL_COMPLETED,
                user_id=auth.user_id if auth.authenticated else None,
                username=auth.username if auth.authenticated else None,
                resource=request.skill,
                resource_id=request.tool,
                duration_ms=duration_ms,
            )

            return ToolCallResponse(
                success=True,
                result=result,
                execution_time_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            audit_log(
                AuditAction.SKILL_ERROR,
                user_id=auth.user_id if auth.authenticated else None,
                username=auth.username if auth.authenticated else None,
                resource=request.skill,
                resource_id=request.tool,
                success=False,
                error_message=str(e),
                duration_ms=duration_ms,
                severity=AuditSeverity.ERROR,
            )

            return ToolCallResponse(
                success=False,
                error=str(e),
                execution_time_ms=duration_ms,
            )

    # ========================================================================
    # Audit Logs (Admin)
    # ========================================================================

    @app.get("/v1/audit/logs", tags=["Admin"])
    async def get_audit_logs(
        limit: int = 100,
        auth: AuthResult = Depends(require_scopes(Scope.ADMIN)),
    ):
        """Get recent audit logs (admin only)."""
        logger = get_audit_logger()
        events = logger.get_recent_events(limit=limit)

        return {
            "total": len(events),
            "events": [e.model_dump() for e in events],
        }

    # ========================================================================
    # Error Handlers
    # ========================================================================

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail,
                }
            },
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
