"""Standardized agent runtime — the single place that wires everything together.

The agent, tools, and permission subsystems were each built in isolation. This
module is the *standard* way to assemble them into something runnable:

    runtime = AgentRuntime.from_config(config)
    result = runtime.run("List the Python files in this directory")
    print(result.content)

What it standardizes:

* **One assembly path.** A tool registry (with the built-in tools), a permission
  manager, and a tool executor are created and connected consistently every time.
* **One permission authority.** All tool gating goes through the executor's
  :class:`~model_constellation.permissions.PermissionManager`; agents never gate
  tools themselves. Interactive prompts are handled by
  :class:`TerminalPermissionPrompter`.
* **One async/sync boundary.** The agent framework is async; the CLI is sync.
  :meth:`AgentRuntime.run` / :meth:`AgentRuntime.run_swarm` bridge with
  ``asyncio.run`` so callers never deal with the event loop.
* **Hybrid tool calling.** Native Ollama tool schemas are passed to the model and
  the agents fall back to text-marker parsing for non-tool-capable models.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from model_constellation import constants
from model_constellation.agent.base import AgentConfig
from model_constellation.agent.primary import PrimaryAgent
from model_constellation.agent.swarm import AgentSwarm, SwarmMode, SwarmResult
from model_constellation.agent.toolcalling import tools_to_schemas
from model_constellation.ollama_client import OllamaClient
from model_constellation.permissions import (
    DangerDetector,
    PermissionManager,
    PermissionMode,
    PermissionRequest,
    PermissionResult,
)
from model_constellation.tools import (
    CommandExecutor,
    ToolExecutor,
    ToolRegistry,
    register_builtin_tools,
)

DEFAULT_TOOLS = ["bash", "read", "write", "glob", "grep", "ls", "tree"]
DEFAULT_MAX_ITERATIONS = 8

DEFAULT_SYSTEM_PROMPT = (
    "You are model-constellation, an AI assistant running on Ollama. "
    "You can call tools to inspect files, run commands, and search. "
    "When a tool would help, call it; otherwise answer directly. "
    "Explain what you are doing and summarize results clearly."
)


@dataclass
class RuntimeResult:
    """Outcome of a single :meth:`AgentRuntime.run` call.

    Attributes:
        content: Final assistant text.
        tool_executions: Audit list of tools that ran (name, args, success, output).
        iterations: Number of model turns taken.
        agent_id: ID of the agent that produced the result.
    """

    content: str
    tool_executions: List[Dict[str, Any]] = field(default_factory=list)
    iterations: int = 0
    agent_id: str = ""


class TerminalPermissionPrompter:
    """Interactive permission prompt backed by a danger assessment.

    Installed as the :class:`PermissionManager` prompt callback for the
    ``first-time`` and ``every-time`` modes. ``allow-all`` / ``deny-all`` never
    reach it.
    """

    def __init__(
        self,
        manager: PermissionManager,
        detector: Optional[DangerDetector] = None,
        console: Optional[Any] = None,
    ):
        """Initialize the prompter.

        Args:
            manager: Permission manager (used to persist "remember" decisions).
            detector: Danger detector for risk assessment.
            console: Optional Rich console; falls back to ``print``.
        """
        self.manager = manager
        self.detector = detector or DangerDetector()
        self.console = console

    def _print(self, message: str) -> None:
        if self.console is not None:
            self.console.print(message)
        else:  # pragma: no cover - exercised only without Rich
            print(message)

    def __call__(self, request: PermissionRequest) -> PermissionResult:
        """Prompt the user to allow or deny a tool execution."""
        assessment = self.detector.get_risk_assessment(request.tool_name, request.parameters)

        level = assessment["danger_level"]
        color = "red" if assessment["requires_confirmation"] else "yellow"
        self._print("")
        self._print(f"[bold {color}]Permission request[/bold {color}]: {request.tool_name}")
        self._print(f"  Risk: {level} — {assessment['summary']}")
        if request.parameters:
            for key, value in request.parameters.items():
                shown = str(value)
                if len(shown) > 120:
                    shown = shown[:120] + "…"
                self._print(f"  {key}: {shown}")
        for warning in assessment["warnings"]:
            self._print(f"  [red]![/red] {warning}")

        try:
            choice = input("Allow? [y]es / [n]o / [a]lways: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            self._print("[yellow]No input — denying.[/yellow]")
            return PermissionResult.deny(reason="No interactive input available")

        if choice in ("a", "always", "r", "remember"):
            self.manager.cache_decision(
                request.tool_name, request.parameters, True, request.session_id
            )
            return PermissionResult.allow(remember=True, reason="User allowed (remembered)")
        if choice in ("y", "yes"):
            return PermissionResult.allow(reason="User allowed")
        return PermissionResult.deny(reason="User denied")


class AgentRuntime:
    """Assembles and runs the agent / tools / permission stack."""

    def __init__(
        self,
        ollama_client: OllamaClient,
        *,
        model: Optional[str] = None,
        tool_names: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
        permission_mode: str = constants.DEFAULT_PERMISSION_MODE,
        session_id: str = "default",
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        enable_tools: bool = True,
        console: Optional[Any] = None,
        command_executor: Optional[CommandExecutor] = None,
        permission_manager: Optional[PermissionManager] = None,
    ):
        """Build a runtime.

        Args:
            ollama_client: Connected Ollama client.
            model: Model name (defaults to the client's default model).
            tool_names: Tools to expose (defaults to :data:`DEFAULT_TOOLS`).
            system_prompt: System prompt for the primary agent.
            permission_mode: One of the values in ``constants.PERMISSION_MODES``.
            session_id: Session identifier for permission scoping.
            max_iterations: Max model turns per ``run``.
            enable_tools: When False, no tools are offered (plain chat).
            console: Optional Rich console for permission prompts.
            command_executor: Optional command executor for the bash tool.
            permission_manager: Optional pre-built permission manager (mainly for
                tests). When omitted one is created from ``permission_mode`` with a
                :class:`TerminalPermissionPrompter` attached.
        """
        self.ollama_client = ollama_client
        self.model = model or getattr(ollama_client, "default_model", constants.DEFAULT_MODEL)
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.session_id = session_id
        self.max_iterations = max_iterations
        self.enable_tools = enable_tools
        self.console = console

        # A single, persistent event loop for this runtime. The Ollama async client
        # (httpx under the hood) binds to the loop it first runs on, so every call
        # must use the *same* loop — otherwise reusing the runtime across calls (e.g.
        # interactive mode's per-turn run, or two run_swarm calls) raises
        # "Event loop is closed".
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Tool registry + built-in tools.
        self.registry = ToolRegistry()
        register_builtin_tools(self.registry, command_executor)

        available = {tool.name for tool in self.registry.list_tools(enabled_only=False)}
        requested = tool_names if tool_names is not None else DEFAULT_TOOLS
        self.tool_names = [name for name in requested if name in available] if enable_tools else []

        # Permission manager (single authority) + executor.
        if permission_manager is not None:
            self.permission_manager = permission_manager
        else:
            self.permission_manager = PermissionManager(mode=PermissionMode(permission_mode))
            self.permission_manager.set_prompt_callback(
                TerminalPermissionPrompter(self.permission_manager, console=console)
            )
        self.tool_executor = ToolExecutor(self.registry, self.permission_manager)

        # Native tool schemas for the selected tools.
        selected = [
            tool
            for tool in self.registry.list_tools(enabled_only=False)
            if tool.name in self.tool_names
        ]
        self.tool_schemas: List[Dict[str, Any]] = tools_to_schemas(selected)

    # -- Construction helpers -------------------------------------------------

    @classmethod
    def from_config(
        cls,
        config: Any,
        ollama_client: Optional[OllamaClient] = None,
        **overrides: Any,
    ) -> "AgentRuntime":
        """Build a runtime from a :class:`ModelConstellationConfig`.

        Args:
            config: Loaded configuration object.
            ollama_client: Optional pre-built client; created from config if absent.
            **overrides: Keyword overrides forwarded to ``__init__`` (e.g. ``model``,
                ``tool_names``, ``permission_mode``, ``enable_tools``, ``console``).

        Returns:
            A configured runtime.
        """
        if ollama_client is None:
            ollama_client = OllamaClient(
                base_url=config.ollama.base_url,
                default_model=config.ollama.default_model,
            )

        params = {
            "model": config.ollama.default_model,
            "permission_mode": str(config.permission.mode.value)
            if hasattr(config.permission.mode, "value")
            else str(config.permission.mode),
        }
        params.update(overrides)
        return cls(ollama_client, **params)

    def build_agent(self) -> PrimaryAgent:
        """Create a primary agent wired to this runtime's tools and client."""
        agent_config = AgentConfig(
            name="primary",
            description="Primary agent",
            model=self.model,
            system_prompt=self.system_prompt,
            tool_names=list(self.tool_names),
            max_iterations=self.max_iterations,
        )
        agent = PrimaryAgent(
            config=agent_config,
            tool_executor=self.tool_executor if self.enable_tools else None,
            ollama_client=self.ollama_client,
        )
        agent.session_id = self.session_id
        agent.set_tool_schemas(self.tool_schemas if self.enable_tools else [])
        return agent

    # -- Running --------------------------------------------------------------

    def _run_sync(self, coro: Any) -> Any:
        """Drive a coroutine to completion on this runtime's persistent loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "AgentRuntime.run()/run_swarm() cannot be called from within a "
                "running event loop; await the async methods instead."
            )

        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        return self._loop.run_until_complete(coro)

    def close(self) -> None:
        """Close the runtime's event loop (releases the Ollama async client)."""
        if self._loop is not None and not self._loop.is_closed():
            self._loop.close()
        self._loop = None

    def run(self, prompt: str, agent: Optional[PrimaryAgent] = None) -> RuntimeResult:
        """Run a prompt to completion (synchronous wrapper).

        Args:
            prompt: User prompt.
            agent: Optional existing agent to reuse (preserves conversation across
                calls, e.g. in interactive mode). A fresh agent is built otherwise.

        Returns:
            The runtime result.
        """
        return self._run_sync(self.arun(prompt, agent))

    async def arun(self, prompt: str, agent: Optional[PrimaryAgent] = None) -> RuntimeResult:
        """Async core of :meth:`run`."""
        agent = agent or self.build_agent()
        content = await agent.process(prompt)
        return RuntimeResult(
            content=content,
            tool_executions=list(agent.tool_executions),
            iterations=agent._iteration,
            agent_id=agent.id,
        )

    def run_swarm(
        self,
        task: str,
        agent_specs: List[Dict[str, Any]],
        mode: str = "parallel",
    ) -> SwarmResult:
        """Run a task across a swarm of agents (synchronous wrapper).

        Args:
            task: Task description.
            agent_specs: One dict per agent. Recognized keys: ``name``, ``type``,
                ``model``, ``tools`` (list of tool names), ``system_prompt``.
            mode: Swarm mode (``parallel``, ``sequential``, ``pipeline``, ``adaptive``).

        Returns:
            The swarm result.
        """
        return self._run_sync(self._arun_swarm(task, agent_specs, mode))

    async def _arun_swarm(
        self,
        task: str,
        agent_specs: List[Dict[str, Any]],
        mode: str,
    ) -> SwarmResult:
        try:
            swarm_mode = SwarmMode(mode)
        except ValueError:
            swarm_mode = SwarmMode.PARALLEL

        swarm = AgentSwarm(name="swarm", mode=swarm_mode)
        swarm.configure(
            ollama_client=self.ollama_client,
            tool_executor=self.tool_executor if self.enable_tools else None,
            tool_schemas=self.tool_schemas,
            session_id=self.session_id,
        )

        for spec in agent_specs:
            tools = spec.get("tools")
            if tools is None:
                tools = list(self.tool_names)
            agent = await swarm.create_and_add_agent(
                name=spec.get("name", "agent"),
                agent_type=spec.get("type", "worker"),
                model=spec.get("model", self.model),
                tools=tools if self.enable_tools else [],
                system_prompt=spec.get("system_prompt", self.system_prompt),
            )
            # A per-agent base_url lets agents run on different Ollama servers,
            # enabling cross-server / cross-model swarms.
            base_url = spec.get("base_url")
            if base_url:
                agent.ollama_client = OllamaClient(
                    base_url=base_url,
                    default_model=spec.get("model", self.model),
                )

        return await swarm.execute_task(task, wait=True)
