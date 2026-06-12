"""Agent registry for managing agent lifecycle."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from model_constellation.agent.base import AgentState, BaseAgent


class RegistryEvent(Enum):
    """Events emitted by the registry."""

    AGENT_REGISTERED = "agent_registered"
    AGENT_UNREGISTERED = "agent_unregistered"
    AGENT_STATE_CHANGED = "agent_state_changed"
    AGENT_UPDATED = "agent_updated"


@dataclass
class RegistryEntry:
    """Entry for a registered agent."""

    agent: BaseAgent
    registered_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentRegistry:
    """Registry for managing agents in the model-constellation framework.

    This class provides functionality for:
    - Registering and unregistering agents
    - Agent discovery
    - Agent state tracking
    - Event handling

    Attributes:
        _agents: Dictionary of registered agents
        _entries: Registry entries with metadata
        _lock: Lock for thread-safe operations
    """

    def __init__(self):
        """Initialize the agent registry."""
        self._agents: Dict[str, BaseAgent] = {}
        self._entries: Dict[str, RegistryEntry] = {}
        self._lock = asyncio.Lock()
        self._event_handlers: Dict[RegistryEvent, List[callable]] = {
            event: [] for event in RegistryEvent
        }

    async def register(
        self,
        agent: BaseAgent,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Register an agent in the registry.

        Args:
            agent: Agent to register
            metadata: Optional metadata for the entry

        Returns:
            Agent ID
        """
        async with self._lock:
            if agent.id in self._agents:
                raise ValueError(f"Agent {agent.id} is already registered")

            self._agents[agent.id] = agent
            self._entries[agent.id] = RegistryEntry(
                agent=agent,
                metadata=metadata or {},
            )

            await self._emit_event(RegistryEvent.AGENT_REGISTERED, agent)

        return agent.id

    async def unregister(self, agent_id: str) -> bool:
        """Unregister an agent from the registry.

        Args:
            agent_id: ID of the agent to unregister

        Returns:
            True if agent was unregistered, False if not found
        """
        async with self._lock:
            if agent_id not in self._agents:
                return False

            agent = self._agents.pop(agent_id)
            self._entries.pop(agent_id, None)

            await self._emit_event(RegistryEvent.AGENT_UNREGISTERED, agent)

        return True

    async def get(self, agent_id: str) -> Optional[BaseAgent]:
        """Get an agent by ID.

        Args:
            agent_id: ID of the agent

        Returns:
            Agent or None if not found
        """
        async with self._lock:
            return self._agents.get(agent_id)

    async def get_entry(self, agent_id: str) -> Optional[RegistryEntry]:
        """Get registry entry for an agent.

        Args:
            agent_id: ID of the agent

        Returns:
            Registry entry or None if not found
        """
        async with self._lock:
            return self._entries.get(agent_id)

    async def list_agents(
        self,
        agent_type: Optional[str] = None,
        state: Optional[AgentState] = None,
        swarm_id: Optional[str] = None,
    ) -> List[BaseAgent]:
        """List agents with optional filters.

        Args:
            agent_type: Filter by agent type
            state: Filter by agent state
            swarm_id: Filter by swarm ID

        Returns:
            List of matching agents
        """
        async with self._lock:
            agents = list(self._agents.values())

        if agent_type:
            agents = [a for a in agents if a.agent_type.value == agent_type]

        if state:
            agents = [a for a in agents if a.state == state]

        if swarm_id:
            agents = [a for a in agents if a.swarm_id == swarm_id]

        return agents

    async def update_state(self, agent_id: str, state: AgentState) -> bool:
        """Update agent state and record activity.

        Args:
            agent_id: ID of the agent
            state: New state

        Returns:
            True if state was updated, False if agent not found
        """
        async with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return False

            old_state = agent.state
            agent.set_state(state)

            entry = self._entries.get(agent_id)
            if entry:
                entry.last_active = datetime.now()

            asyncio.create_task(
                self._emit_event(
                    RegistryEvent.AGENT_STATE_CHANGED,
                    agent,
                    {"old_state": old_state.value, "new_state": state.value},
                )
            )

        return True

    async def update_metadata(
        self,
        agent_id: str,
        key: str,
        value: Any,
    ) -> bool:
        """Update agent metadata.

        Args:
            agent_id: ID of the agent
            key: Metadata key
            value: Metadata value

        Returns:
            True if metadata was updated, False if agent not found
        """
        async with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return False

            agent.update_metadata(key, value)

            entry = self._entries.get(agent_id)
            if entry:
                entry.metadata[key] = value

            await self._emit_event(RegistryEvent.AGENT_UPDATED, agent)

        return True

    async def get_active_agents(self) -> List[BaseAgent]:
        """Get all active (running or waiting) agents.

        Returns:
            List of active agents
        """
        return await self.list_agents(
            state=None,
        )

    async def count(self) -> int:
        """Get total number of registered agents.

        Returns:
            Number of registered agents
        """
        async with self._lock:
            return len(self._agents)

    async def clear(self) -> int:
        """Clear all registered agents.

        Returns:
            Number of agents cleared
        """
        async with self._lock:
            count = len(self._agents)
            self._agents.clear()
            self._entries.clear()
            return count

    def on_event(
        self,
        event: RegistryEvent,
        handler: callable,
    ) -> None:
        """Register an event handler.

        Args:
            event: Event to listen for
            handler: Handler function
        """
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    async def _emit_event(
        self,
        event: RegistryEvent,
        agent: BaseAgent,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit an event to all handlers.

        Args:
            event: Event type
            agent: The agent related to the event
            extra_data: Additional event data
        """
        data = {
            "agent": agent,
            "agent_id": agent.id,
            "timestamp": datetime.now(),
        }
        if extra_data:
            data.update(extra_data)

        for handler in self._event_handlers.get(event, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception:
                pass


class GlobalRegistry:
    """Singleton global registry for agents."""

    _instance: Optional[AgentRegistry] = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_instance(cls) -> AgentRegistry:
        """Get or create the global registry instance.

        Returns:
            The global agent registry
        """
        async with cls._lock:
            if cls._instance is None:
                cls._instance = AgentRegistry()
            return cls._instance

    @classmethod
    async def register(
        cls,
        agent: BaseAgent,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Register an agent in the global registry.

        Args:
            agent: Agent to register
            metadata: Optional metadata

        Returns:
            Agent ID
        """
        registry = await cls.get_instance()
        return await registry.register(agent, metadata)

    @classmethod
    async def unregister(cls, agent_id: str) -> bool:
        """Unregister an agent from the global registry.

        Args:
            agent_id: ID of the agent

        Returns:
            True if unregistered
        """
        registry = await cls.get_instance()
        return await registry.unregister(agent_id)

    @classmethod
    async def get(cls, agent_id: str) -> Optional[BaseAgent]:
        """Get an agent from the global registry.

        Args:
            agent_id: ID of the agent

        Returns:
            Agent or None
        """
        registry = await cls.get_instance()
        return await registry.get(agent_id)

    @classmethod
    async def list_agents(
        cls,
        agent_type: Optional[str] = None,
        state: Optional[AgentState] = None,
        swarm_id: Optional[str] = None,
    ) -> List[BaseAgent]:
        """List agents from the global registry.

        Args:
            agent_type: Filter by type
            state: Filter by state
            swarm_id: Filter by swarm

        Returns:
            List of agents
        """
        registry = await cls.get_instance()
        return await registry.list_agents(agent_type, state, swarm_id)
