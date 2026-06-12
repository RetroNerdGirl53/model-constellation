"""FastAPI application exposing the model-constellation engine over HTTP.

Design notes
------------
* **Thin layer.** Every endpoint delegates to the same library used by the CLI
  (``AgentRuntime`` / ``OllamaClient``). No business logic is duplicated here.
* **Async-native.** Endpoints ``await`` the runtime's async methods directly, so
  everything shares the server's single event loop (the Ollama async client binds
  to it once). The synchronous ``AgentRuntime.run`` wrapper is *not* used here.
* **Safe by default.** Tool execution is OFF unless the server is started with
  ``allow_tools=True`` (env ``MC_ALLOW_TOOLS=1``). There are no interactive
  permission prompts over the wire — only the policy modes ``allow-all`` /
  ``deny-all`` are honored; ``first-time`` / ``every-time`` are rejected.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional

try:
    from fastapi import Depends, FastAPI, Header, HTTPException
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "The HTTP API requires extra dependencies. Install with:\n"
        '    pip install "model-constellation[api]"'
    ) from exc

from model_constellation import __version__
from model_constellation.agent.toolcalling import tools_to_schemas
from model_constellation.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaModelError,
)
from model_constellation.permissions import PermissionManager, PermissionMode
from model_constellation.runtime import DEFAULT_TOOLS, AgentRuntime
from model_constellation.tools import ToolRegistry, register_builtin_tools

# Permission modes that make sense for a headless service (no human at the socket).
_SERVER_PERMISSION_MODES = {"allow-all", "deny-all"}


@dataclass
class APISettings:
    """Server configuration.

    Attributes:
        ollama_url: Base URL of the Ollama server the engine talks to.
        default_model: Model used when a request omits one.
        allow_tools: Master switch — tools only run when this is True.
        default_permission_mode: Policy applied when a request omits one.
        api_key: If set, requests must present it (Bearer or ``X-API-Key``).
        max_iterations: Max agent loop turns per request.
    """

    ollama_url: str = "http://localhost:11434"
    default_model: str = "llama3.1"
    allow_tools: bool = False
    default_permission_mode: str = "deny-all"
    api_key: Optional[str] = None
    max_iterations: int = 8

    @classmethod
    def from_env(cls) -> "APISettings":
        """Build settings from ``MC_*`` environment variables."""
        return cls(
            ollama_url=os.environ.get("MC_OLLAMA_URL", cls.ollama_url),
            default_model=os.environ.get("MC_DEFAULT_MODEL", cls.default_model),
            allow_tools=os.environ.get("MC_ALLOW_TOOLS", "0").lower() in ("1", "true", "yes"),
            default_permission_mode=os.environ.get(
                "MC_PERMISSION_MODE", cls.default_permission_mode
            ),
            api_key=os.environ.get("MC_API_KEY") or None,
            max_iterations=int(os.environ.get("MC_MAX_ITERATIONS", cls.max_iterations)),
        )


# --- Request / response schemas ---------------------------------------------


class ChatMessageIn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    prompt: Optional[str] = None
    messages: Optional[List[ChatMessageIn]] = None
    model: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ChatResponseOut(BaseModel):
    content: str
    model: str
    eval_count: Optional[int] = None


class RunRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    tools: Optional[List[str]] = None
    system_prompt: Optional[str] = None
    permission_mode: Optional[str] = None
    max_iterations: Optional[int] = Field(default=None, ge=1, le=50)


class ToolExecutionOut(BaseModel):
    tool: str
    arguments: Dict[str, Any]
    success: bool
    output: str


class RunResponse(BaseModel):
    content: str
    model: str
    iterations: int
    tools_enabled: bool
    tool_executions: List[ToolExecutionOut]


class AgentSpecIn(BaseModel):
    name: str
    model: Optional[str] = None
    type: str = "worker"
    tools: Optional[List[str]] = None
    system_prompt: Optional[str] = None
    base_url: Optional[str] = None


class SwarmRequest(BaseModel):
    task: str
    agents: List[AgentSpecIn]
    mode: str = "parallel"
    tools: Optional[List[str]] = None
    permission_mode: Optional[str] = None


class SwarmResultOut(BaseModel):
    status: str
    duration_ms: int
    results: List[Dict[str, Any]]
    errors: List[str]


# --- App factory ------------------------------------------------------------


def create_app(settings: Optional[APISettings] = None, client: Optional[OllamaClient] = None) -> FastAPI:
    """Create the FastAPI application.

    Args:
        settings: Server configuration (defaults to :meth:`APISettings.from_env`).
        client: Optional pre-built Ollama client (mainly for tests). When omitted a
            client is created from ``settings.ollama_url``.

    Returns:
        A configured FastAPI app.
    """
    settings = settings or APISettings.from_env()
    app = FastAPI(
        title="model-constellation",
        version=__version__,
        description="HTTP backend for the model-constellation agent engine.",
    )
    app.state.settings = settings
    app.state.client = client or OllamaClient(
        base_url=settings.ollama_url, default_model=settings.default_model
    )

    def require_api_key(
        authorization: Optional[str] = Header(default=None),
        x_api_key: Optional[str] = Header(default=None),
    ) -> None:
        """Auth dependency — a no-op unless an API key is configured."""
        if not settings.api_key:
            return
        presented = x_api_key
        if not presented and authorization and authorization.lower().startswith("bearer "):
            presented = authorization[7:]
        if presented != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    auth = Depends(require_api_key)

    def _resolve_permission_mode(requested: Optional[str]) -> str:
        mode = requested or settings.default_permission_mode
        if mode not in _SERVER_PERMISSION_MODES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"permission_mode '{mode}' is not allowed over HTTP. "
                    f"Use one of: {sorted(_SERVER_PERMISSION_MODES)} "
                    "(interactive modes require a terminal)."
                ),
            )
        return mode

    def _make_runtime(
        model: Optional[str],
        tools: Optional[List[str]],
        system_prompt: Optional[str],
        permission_mode: Optional[str],
        max_iterations: Optional[int],
    ) -> AgentRuntime:
        tools_enabled = settings.allow_tools
        mode = _resolve_permission_mode(permission_mode)
        manager = PermissionManager(mode=PermissionMode(mode))  # no prompt callback
        return AgentRuntime(
            app.state.client,
            model=model or settings.default_model,
            tool_names=tools if tools is not None else (DEFAULT_TOOLS if tools_enabled else []),
            system_prompt=system_prompt,
            session_id="api",
            max_iterations=max_iterations or settings.max_iterations,
            enable_tools=tools_enabled,
            permission_manager=manager,
        )

    # -- Meta endpoints ------------------------------------------------------

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/version")
    def version() -> Dict[str, str]:
        return {"name": "model-constellation", "version": __version__}

    @app.get("/v1/models", dependencies=[auth])
    async def list_models() -> Dict[str, Any]:
        try:
            models = await app.state.client.async_list_models()
        except OllamaConnectionError as e:
            raise HTTPException(status_code=502, detail=str(e))
        return {
            "models": [
                {"name": m.name, "size": m.size, "modified_at": m.modified_at} for m in models
            ]
        }

    @app.get("/v1/tools", dependencies=[auth])
    def list_tools() -> Dict[str, Any]:
        registry = ToolRegistry()
        register_builtin_tools(registry)
        schemas = tools_to_schemas(registry.list_tools(enabled_only=False))
        return {"tools_enabled": settings.allow_tools, "tools": schemas}

    # -- Chat (no tools) -----------------------------------------------------

    @app.post("/v1/chat", response_model=ChatResponseOut, dependencies=[auth])
    async def chat(req: ChatRequest) -> ChatResponseOut:
        messages = _build_messages(req)
        model = req.model or settings.default_model
        options: Dict[str, Any] = {}
        if req.temperature is not None:
            options["temperature"] = req.temperature
        if req.top_p is not None:
            options["top_p"] = req.top_p
        try:
            response = await app.state.client.async_chat(
                model=model, messages=messages, stream=False, **options
            )
        except OllamaModelError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except OllamaConnectionError as e:
            raise HTTPException(status_code=502, detail=str(e))
        return ChatResponseOut(
            content=response.message.content, model=response.model or model,
            eval_count=response.eval_count,
        )

    @app.post("/v1/chat/stream", dependencies=[auth])
    async def chat_stream(req: ChatRequest) -> StreamingResponse:
        messages = _build_messages(req)
        model = req.model or settings.default_model

        async def event_stream() -> AsyncGenerator[bytes, None]:
            try:
                stream = await app.state.client.async_chat(
                    model=model, messages=messages, stream=True
                )
                async for chunk in stream:
                    delta = chunk.message.content
                    if delta:
                        yield _sse({"content": delta})
                yield _sse({"done": True})
            except (OllamaConnectionError, OllamaModelError) as e:
                yield _sse({"error": str(e)})

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # -- Agentic run (tools) -------------------------------------------------

    @app.post("/v1/run", response_model=RunResponse, dependencies=[auth])
    async def run(req: RunRequest) -> RunResponse:
        runtime = _make_runtime(
            req.model, req.tools, req.system_prompt, req.permission_mode, req.max_iterations
        )
        try:
            result = await runtime.arun(req.prompt)
        except OllamaModelError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except OllamaConnectionError as e:
            raise HTTPException(status_code=502, detail=str(e))
        return RunResponse(
            content=result.content,
            model=runtime.model,
            iterations=result.iterations,
            tools_enabled=runtime.enable_tools,
            tool_executions=[ToolExecutionOut(**ex) for ex in result.tool_executions],
        )

    # -- Swarm ---------------------------------------------------------------

    @app.post("/v1/swarm", response_model=SwarmResultOut, dependencies=[auth])
    async def swarm(req: SwarmRequest) -> SwarmResultOut:
        runtime = _make_runtime(None, req.tools, None, req.permission_mode, None)
        specs = [spec.model_dump(exclude_none=True) for spec in req.agents]
        try:
            result = await runtime._arun_swarm(req.task, specs, req.mode)
        except OllamaConnectionError as e:
            raise HTTPException(status_code=502, detail=str(e))
        return SwarmResultOut(
            status=result.status,
            duration_ms=result.total_duration_ms,
            results=result.task_results,
            errors=result.errors,
        )

    return app


def _build_messages(req: ChatRequest) -> List[Dict[str, str]]:
    """Turn a chat request into Ollama message dicts."""
    if req.messages:
        return [{"role": m.role, "content": m.content} for m in req.messages]
    if req.prompt:
        return [{"role": "user", "content": req.prompt}]
    raise HTTPException(status_code=400, detail="Provide either 'prompt' or 'messages'")


def _sse(data: Dict[str, Any]) -> bytes:
    """Encode a dict as one Server-Sent Event."""
    return f"data: {json.dumps(data)}\n\n".encode()


# Module-level app for ``uvicorn model_constellation.api:app`` / ``...api.server:app``.
app = create_app()
