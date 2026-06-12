"""Agent swarm coordinator for model-constellation framework."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from model_constellation.agent.base import AgentState, ModelParameters
from model_constellation.agent.communication import (
    AgentCommunicator,
    CommunicationBus,
    CommunicationMode,
    MessagePriority,
)
from model_constellation.agent.sub import SubAgent, SubAgentConfig


class SwarmMode(Enum):
    """Execution modes for agent swarms."""

    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    PIPELINE = "pipeline"
    ADAPTIVE = "adaptive"


class SwarmState(Enum):
    """States of a swarm."""

    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


@dataclass
class TaskDistribution:
    """Represents how a task is distributed across swarm."""

    task_id: str
    description: str
    assigned_agents: List[str] = field(default_factory=list)
    status: str = "pending"
    results: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SwarmResult:
    """Result from swarm execution."""

    swarm_id: str
    status: str
    total_duration_ms: int
    task_results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class AgentSwarm:
    """Coordinator for managing multiple agents working together.

    A swarm is a collection of sub-agents that collaborate on tasks.
    The swarm coordinates task distribution, communication, and
    result aggregation.

    Attributes:
        id: Unique swarm identifier
        name: Human-readable name
        mode: Execution mode (parallel, sequential, pipeline, adaptive)
        agents: List of agents in the swarm
        coordinator: Agent that coordinates the swarm
        shared_context: Shared data between agents
    """

    def __init__(
        self,
        name: str,
        mode: SwarmMode = SwarmMode.PARALLEL,
        coordinator_id: Optional[str] = None,
        shared_context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize agent swarm.

        Args:
            name: Swarm name
            mode: Execution mode
            coordinator_id: ID of coordinator agent
            shared_context: Initial shared context
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.mode = mode
        self.coordinator_id = coordinator_id or str(uuid.uuid4())
        self.shared_context = shared_context or {}
        self.state = SwarmState.IDLE

        self.agents: List[SubAgent] = []

        # Shared execution dependencies, injected via :meth:`configure`. Without
        # these the swarm's agents cannot reach the model — this is what wires the
        # swarm into the live Ollama client and tool executor.
        self.ollama_client: Optional[Any] = None
        self.tool_executor: Optional[Any] = None
        self.tool_schemas: List[Dict[str, Any]] = []
        self.session_id: str = "default"

        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._result_queue: asyncio.Queue = asyncio.Queue()
        self._active_tasks: Dict[str, TaskDistribution] = {}

        self.communicator = CommunicationBus().get_communicator(CommunicationMode.SWARM)
        self.communicator.add_swarm_member(self.coordinator_id)

        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

    def configure(
        self,
        ollama_client: Optional[Any] = None,
        tool_executor: Optional[Any] = None,
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        session_id: str = "default",
    ) -> None:
        """Inject shared execution dependencies into the swarm and its agents.

        Args:
            ollama_client: Client agents use to call the model.
            tool_executor: Executor agents use to run tools.
            tool_schemas: Native tool schemas to expose to each agent.
            session_id: Session identifier for permission scoping.
        """
        self.ollama_client = ollama_client
        self.tool_executor = tool_executor
        self.tool_schemas = tool_schemas or []
        self.session_id = session_id
        for agent in self.agents:
            self._apply_dependencies(agent)

    def _apply_dependencies(self, agent: SubAgent) -> None:
        """Propagate shared tool schemas / session to a single agent.

        Each agent only receives schemas for the tools it is permitted to use, so
        the model is never offered a tool the agent would reject.
        """
        if self.tool_schemas and agent.tool_names:
            schemas = [
                schema
                for schema in self.tool_schemas
                if schema.get("function", {}).get("name") in agent.tool_names
            ]
        else:
            schemas = []
        agent.set_tool_schemas(schemas)
        agent.session_id = self.session_id

    @property
    def agent_ids(self) -> List[str]:
        """Get list of agent IDs in the swarm."""
        return [agent.id for agent in self.agents]

    @property
    def is_active(self) -> bool:
        """Check if swarm is currently active."""
        return self.state == SwarmState.RUNNING

    async def add_agent(self, agent: SubAgent) -> None:
        """Add an agent to the swarm.

        Args:
            agent: Sub-agent to add
        """
        agent.swarm_id = self.id
        self.agents.append(agent)
        self._apply_dependencies(agent)
        self.communicator.add_swarm_member(agent.id)

    async def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent from the swarm.

        Args:
            agent_id: ID of agent to remove

        Returns:
            True if agent was removed
        """
        for i, agent in enumerate(self.agents):
            if agent.id == agent_id:
                self.agents.pop(i)
                self.communicator.remove_swarm_member(agent_id)
                return True
        return False

    async def create_and_add_agent(
        self,
        name: str,
        agent_type: str = "worker",
        model: str = "llama2",
        parameters: Optional[ModelParameters] = None,
        tools: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
    ) -> SubAgent:
        """Create and add an agent to the swarm.

        Args:
            name: Agent name
            agent_type: Type of agent
            model: Ollama model
            parameters: Model parameters
            tools: Tool names
            system_prompt: System prompt

        Returns:
            Created agent
        """
        config = SubAgentConfig(
            name=name,
            description=f"Swarm agent: {name}",
            agent_subtype=agent_type,
            model=model,
            parameters=parameters or ModelParameters(),
            system_prompt=system_prompt or "",
            tool_names=tools or [],
            communication_mode=CommunicationMode.SWARM,
        )

        agent = SubAgent(
            config=config,
            swarm_id=self.id,
            communicator=self.communicator,
        )

        await self.add_agent(agent)
        return agent

    async def execute_task(
        self,
        task: str,
        wait: bool = True,
        timeout: float = 300.0,
    ) -> SwarmResult:
        """Execute a task across the swarm.

        Args:
            task: Task description
            wait: Whether to wait for completion
            timeout: Timeout in seconds

        Returns:
            Swarm execution result
        """
        self.state = SwarmState.RUNNING
        self.started_at = datetime.now()

        task_id = str(uuid.uuid4())
        distribution = TaskDistribution(
            task_id=task_id,
            description=task,
            assigned_agents=self.agent_ids,
        )
        self._active_tasks[task_id] = distribution

        if self.mode == SwarmMode.PARALLEL:
            result = await self._execute_parallel(task)
        elif self.mode == SwarmMode.SEQUENTIAL:
            result = await self._execute_sequential(task)
        elif self.mode == SwarmMode.PIPELINE:
            result = await self._execute_pipeline(task)
        elif self.mode == SwarmMode.ADAPTIVE:
            result = await self._execute_adaptive(task)
        else:
            result = await self._execute_parallel(task)

        self.completed_at = datetime.now()
        # The per-mode helpers compute duration before completed_at is set, so
        # populate the real total here.
        result.total_duration_ms = int(
            (self.completed_at - self.started_at).total_seconds() * 1000
        )

        if self.state == SwarmState.RUNNING:
            self.state = SwarmState.COMPLETED

        return result

    async def _execute_parallel(self, task: str) -> SwarmResult:
        """Execute task in parallel across all agents.

        Args:
            task: Task description

        Returns:
            Swarm result
        """
        task_results = []
        errors = []

        async def execute_agent_task(agent: SubAgent) -> Dict[str, Any]:
            try:
                result = await agent.execute_task(
                    task, agent.ollama_client or self.ollama_client, self.tool_executor
                )
                return {
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "status": "success",
                    "result": result,
                }
            except Exception as e:
                return {
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "status": "failed",
                    "error": str(e),
                }

        results = await asyncio.gather(
            *[execute_agent_task(agent) for agent in self.agents],
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            elif isinstance(result, dict):
                task_results.append(result)
                if result.get("status") == "failed":
                    errors.append(result.get("error", "Unknown error"))

        duration = 0
        if self.started_at and self.completed_at:
            duration = int((self.completed_at - self.started_at).total_seconds() * 1000)

        return SwarmResult(
            swarm_id=self.id,
            status="completed" if not errors else "partial",
            total_duration_ms=duration,
            task_results=task_results,
            errors=errors,
        )

    async def _execute_sequential(self, task: str) -> SwarmResult:
        """Execute task sequentially across agents.

        Args:
            task: Task description

        Returns:
            Swarm result
        """
        task_results = []
        errors = []

        for agent in self.agents:
            try:
                result = await agent.execute_task(
                    task, agent.ollama_client or self.ollama_client, self.tool_executor
                )
                task_results.append(
                    {
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "status": "success",
                        "result": result,
                    }
                )
            except Exception as e:
                task_results.append(
                    {
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "status": "failed",
                        "error": str(e),
                    }
                )
                errors.append(str(e))

        duration = 0
        if self.started_at and self.completed_at:
            duration = int((self.completed_at - self.started_at).total_seconds() * 1000)

        return SwarmResult(
            swarm_id=self.id,
            status="completed" if not errors else "partial",
            total_duration_ms=duration,
            task_results=task_results,
            errors=errors,
        )

    async def _execute_pipeline(self, task: str) -> SwarmResult:
        """Execute task in pipeline mode (output feeds next agent).

        Args:
            task: Initial task

        Returns:
            Swarm result
        """
        task_results = []
        errors = []
        current_input = task

        for agent in self.agents:
            try:
                prompt = f"Previous output: {current_input}\n\nTask: {task}"
                result = await agent.execute_task(
                    prompt, agent.ollama_client or self.ollama_client, self.tool_executor
                )
                current_input = result

                task_results.append(
                    {
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "status": "success",
                        "result": result,
                    }
                )
            except Exception as e:
                task_results.append(
                    {
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "status": "failed",
                        "error": str(e),
                    }
                )
                errors.append(str(e))
                break

        duration = 0
        if self.started_at and self.completed_at:
            duration = int((self.completed_at - self.started_at).total_seconds() * 1000)

        return SwarmResult(
            swarm_id=self.id,
            status="completed" if not errors else "partial",
            total_duration_ms=duration,
            task_results=task_results,
            errors=errors,
        )

    async def _execute_adaptive(self, task: str) -> SwarmResult:
        """Execute task with adaptive mode selection.

        Args:
            task: Task description

        Returns:
            Swarm result
        """
        if len(self.agents) <= 2:
            return await self._execute_parallel(task)
        elif "process" in task.lower() or "transform" in task.lower():
            return await self._execute_pipeline(task)
        else:
            return await self._execute_parallel(task)

    async def broadcast_message(
        self,
        content: str,
        sender_id: Optional[str] = None,
    ) -> None:
        """Broadcast a message to all swarm agents.

        Args:
            content: Message content
            sender_id: Sender ID (uses coordinator if not specified)
        """
        sender = sender_id or self.coordinator_id

        for agent in self.agents:
            if agent.id != sender:
                self.communicator.send_message(
                    sender_id=sender,
                    sender_name="Swarm Coordinator",
                    content=content,
                    recipient_id=agent.id,
                    message_type="broadcast",
                    priority=MessagePriority.NORMAL,
                )

    async def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific agent.

        Args:
            agent_id: Agent ID

        Returns:
            Status dictionary
        """
        for agent in self.agents:
            if agent.id == agent_id:
                return {
                    "id": agent.id,
                    "name": agent.name,
                    "state": agent.state.value,
                    "type": agent.subtype,
                    "result": agent.result,
                }
        return None

    def get_all_status(self) -> List[Dict[str, Any]]:
        """Get status of all agents in swarm.

        Returns:
            List of status dictionaries
        """
        return [
            {
                "id": agent.id,
                "name": agent.name,
                "state": agent.state.value,
                "type": agent.subtype,
                "result": agent.result,
            }
            for agent in self.agents
        ]

    def update_shared_context(self, key: str, value: Any) -> None:
        """Update shared context.

        Args:
            key: Context key
            value: Context value
        """
        self.shared_context[key] = value

    def get_shared_context(self, key: str, default: Any = None) -> Any:
        """Get value from shared context.

        Args:
            key: Context key
            default: Default value

        Returns:
            Context value
        """
        return self.shared_context.get(key, default)

    async def terminate(self) -> None:
        """Terminate the swarm and all its agents."""
        self.state = SwarmState.TERMINATED
        self.completed_at = datetime.now()

        for agent in self.agents:
            agent.set_state(AgentState.TERMINATED)

    def to_dict(self) -> Dict[str, Any]:
        """Convert swarm to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "id": self.id,
            "name": self.name,
            "mode": self.mode.value,
            "state": self.state.value,
            "coordinator_id": self.coordinator_id,
            "agents": self.get_all_status(),
            "agent_count": len(self.agents),
            "shared_context": self.shared_context,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class SwarmManager:
    """Manager for creating and coordinating agent swarms."""

    def __init__(self):
        """Initialize swarm manager."""
        self._swarms: Dict[str, AgentSwarm] = {}

    def create_swarm(
        self,
        name: str,
        mode: SwarmMode = SwarmMode.PARALLEL,
        agent_count: int = 3,
        agent_type: str = "worker",
        model: str = "llama2",
        parameters: Optional[ModelParameters] = None,
        tools: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
    ) -> AgentSwarm:
        """Create a new agent swarm.

        Args:
            name: Swarm name
            mode: Execution mode
            agent_count: Number of agents to create
            agent_type: Type of agents
            model: Ollama model
            parameters: Model parameters
            tools: Tool names
            system_prompt: System prompt

        Returns:
            Created swarm
        """
        swarm = AgentSwarm(name=name, mode=mode)

        for i in range(agent_count):
            asyncio.create_task(
                swarm.create_and_add_agent(
                    name=f"{name}-agent-{i + 1}",
                    agent_type=agent_type,
                    model=model,
                    parameters=parameters,
                    tools=tools,
                    system_prompt=system_prompt,
                )
            )

        self._swarms[swarm.id] = swarm
        return swarm

    def get_swarm(self, swarm_id: str) -> Optional[AgentSwarm]:
        """Get a swarm by ID.

        Args:
            swarm_id: Swarm ID

        Returns:
            Swarm or None
        """
        return self._swarms.get(swarm_id)

    def list_swarms(self) -> List[AgentSwarm]:
        """List all swarms.

        Returns:
            List of swarms
        """
        return list(self._swarms.values())

    def delete_swarm(self, swarm_id: str) -> bool:
        """Delete a swarm.

        Args:
            swarm_id: Swarm ID

        Returns:
            True if deleted
        """
        swarm = self._swarms.pop(swarm_id, None)
        if swarm:
            asyncio.create_task(swarm.terminate())
            return True
        return False


class GlobalSwarmManager:
    """Singleton global swarm manager."""

    _instance: Optional[SwarmManager] = None

    @classmethod
    def get_instance(cls) -> SwarmManager:
        """Get or create the global swarm manager.

        Returns:
            The global swarm manager
        """
        if cls._instance is None:
            cls._instance = SwarmManager()
        return cls._instance
