"""Base agent class for model-constellation framework."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentType(Enum):
    """Types of agents in the model-constellation framework."""

    PRIMARY = "primary"
    SPECIALIZED = "specialized"
    WORKER = "worker"
    RESEARCH = "research"
    CODE = "code"


class AgentMode(Enum):
    """Communication modes for agents."""

    ISOLATED = "isolated"
    SWARM = "swarm"
    HIERARCHICAL = "hierarchical"


class AgentState(Enum):
    """States an agent can be in."""

    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


@dataclass
class Message:
    """Represents a message in agent communication."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: str = "user"
    content: str = ""
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_result: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "tool_calls": self.tool_calls,
            "tool_result": self.tool_result,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ToolDefinition:
    """Definition of a tool available to an agent."""

    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    handler: Optional[str] = None
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert tool definition to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "handler": self.handler,
            "enabled": self.enabled,
        }


@dataclass
class ModelParameters:
    """Parameters for the Ollama model."""

    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    seed: Optional[int] = None
    num_ctx: int = 4096
    num_gpu: int = -1
    num_thread: int = -1

    def to_dict(self) -> Dict[str, Any]:
        """Convert parameters to dictionary for Ollama API."""
        params = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repeat_penalty": self.repeat_penalty,
            "num_ctx": self.num_ctx,
        }
        if self.seed is not None:
            params["seed"] = self.seed
        if self.num_gpu > 0:
            params["num_gpu"] = self.num_gpu
        if self.num_thread > 0:
            params["num_thread"] = self.num_thread
        return params


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    description: str = ""
    model: str = "llama2"
    parameters: ModelParameters = field(default_factory=ModelParameters)
    system_prompt: str = ""
    tools: List[ToolDefinition] = field(default_factory=list)
    tool_names: List[str] = field(default_factory=list)
    max_iterations: int = 100
    timeout: int = 300000


class BaseAgent(ABC):
    """Abstract base class for all agents in the model-constellation framework.

    This class provides the common interface and functionality for all agent types.
    Subclasses must implement the process method for specific agent behaviors.

    Attributes:
        id: Unique identifier for the agent
        name: Human-readable name for the agent
        description: Description of the agent's purpose
        agent_type: Type of agent (primary, specialized, worker, etc.)
        mode: Communication mode (isolated, swarm, hierarchical)
        state: Current state of the agent
        model: Ollama model to use
        parameters: Model parameters
        system_prompt: System prompt for the agent
        tools: List of tool definitions available to the agent
        tool_names: List of tool names enabled for the agent
        parent_id: ID of parent agent (if hierarchical)
        swarm_id: ID of swarm the agent belongs to
        created_at: Timestamp when agent was created
        metadata: Additional agent metadata
    """

    def __init__(
        self,
        config: AgentConfig,
        agent_type: AgentType = AgentType.PRIMARY,
        mode: AgentMode = AgentMode.ISOLATED,
        agent_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        swarm_id: Optional[str] = None,
    ):
        """Initialize a base agent.

        Args:
            config: Agent configuration
            agent_type: Type of agent being created
            mode: Communication mode
            agent_id: Optional custom agent ID
            parent_id: ID of parent agent for hierarchical mode
            swarm_id: ID of swarm agent belongs to
        """
        self.id = agent_id or str(uuid.uuid4())
        self.name = config.name
        self.description = config.description
        self.agent_type = agent_type
        self.mode = mode
        self.state = AgentState.IDLE

        self.model = config.model
        self.parameters = config.parameters
        self.system_prompt = config.system_prompt
        self.tools = config.tools
        self.tool_names = config.tool_names
        self.max_iterations = config.max_iterations
        self.timeout = config.timeout

        self.parent_id = parent_id
        self.swarm_id = swarm_id
        self.created_at = datetime.now()
        self.metadata: Dict[str, Any] = {}

        # Native Ollama tool schemas (the ``tools=`` payload). Set by the runtime
        # so the model can request tools via structured function calling.
        self.tool_schemas: List[Dict[str, Any]] = []

        self._messages: List[Message] = []
        self._conversation_history: List[Message] = []

    @property
    def id(self) -> str:
        """Get the agent's unique identifier."""
        return self._id

    @id.setter
    def id(self, value: str) -> None:
        """Set the agent's unique identifier."""
        self._id = value

    @property
    def name(self) -> str:
        """Get the agent's name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set the agent's name."""
        self._name = value

    @property
    def description(self) -> str:
        """Get the agent's description."""
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        """Set the agent's description."""
        self._description = value

    @property
    def model(self) -> str:
        """Get the Ollama model name."""
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        """Set the Ollama model name."""
        self._model = value

    @property
    def messages(self) -> List[Message]:
        """Get the agent's message history."""
        return self._messages.copy()

    @property
    def conversation_history(self) -> List[Message]:
        """Get the full conversation history."""
        return self._conversation_history.copy()

    def add_message(self, message: Message) -> None:
        """Add a message to the agent's history.

        Args:
            message: Message to add
        """
        self._messages.append(message)
        self._conversation_history.append(message)

    def add_user_message(self, content: str) -> Message:
        """Add a user message to the conversation.

        Args:
            content: Message content

        Returns:
            The created message
        """
        message = Message(role="user", content=content)
        self.add_message(message)
        return message

    def add_assistant_message(
        self,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> Message:
        """Add an assistant message to the conversation.

        Args:
            content: Message content
            tool_calls: Optional tool calls made by the assistant

        Returns:
            The created message
        """
        message = Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        )
        self.add_message(message)
        return message

    def add_tool_message(self, tool_name: str, result: str) -> Message:
        """Add a tool result message to the conversation.

        Args:
            tool_name: Name of the tool that was executed
            result: Result from tool execution

        Returns:
            The created message
        """
        message = Message(
            role="tool",
            content=f"Tool '{tool_name}' result: {result}",
            tool_result=result,
            metadata={"tool_name": tool_name},
        )
        self.add_message(message)
        return message

    def add_system_message(self, content: str) -> Message:
        """Add a system message to the conversation.

        Args:
            content: Message content

        Returns:
            The created message
        """
        message = Message(role="system", content=content)
        self.add_message(message)
        return message

    def clear_messages(self) -> None:
        """Clear the current message list (not conversation history)."""
        self._messages.clear()

    def clear_history(self) -> None:
        """Clear all conversation history."""
        self._conversation_history.clear()
        self._messages.clear()

    def get_messages_for_ollama(self) -> List[Dict[str, Any]]:
        """Get messages in format expected by Ollama API.

        Returns:
            List of message dictionaries
        """
        result = []

        if self.system_prompt:
            result.append({"role": "system", "content": self.system_prompt})

        for msg in self._conversation_history:
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            if msg.tool_result and msg.role == "tool":
                msg_dict["content"] = msg.tool_result
            result.append(msg_dict)

        return result

    def set_state(self, state: AgentState) -> None:
        """Set the agent's state.

        Args:
            state: New state for the agent
        """
        self.state = state

    def update_metadata(self, key: str, value: Any) -> None:
        """Update agent metadata.

        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value.

        Args:
            key: Metadata key
            default: Default value if key not found

        Returns:
            Metadata value or default
        """
        return self.metadata.get(key, default)

    def set_tool_schemas(self, schemas: List[Dict[str, Any]]) -> None:
        """Set the native Ollama tool schemas available to this agent.

        Args:
            schemas: List of ``{"type": "function", "function": {...}}`` dicts.
        """
        self.tool_schemas = schemas or []

    def has_tool(self, tool_name: str) -> bool:
        """Check if agent has access to a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            True if tool is available
        """
        return tool_name in self.tool_names

    def get_tool_definition(self, tool_name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool definition or None if not found
        """
        for tool in self.tools:
            if tool.name == tool_name:
                return tool
        return None

    def enable_tool(self, tool_name: str) -> None:
        """Enable a tool for the agent.

        Args:
            tool_name: Name of the tool to enable
        """
        if tool_name not in self.tool_names:
            self.tool_names.append(tool_name)

    def disable_tool(self, tool_name: str) -> None:
        """Disable a tool for the agent.

        Args:
            tool_name: Name of the tool to disable
        """
        if tool_name in self.tool_names:
            self.tool_names.remove(tool_name)

    @abstractmethod
    async def process(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Process a prompt and return the response.

        This is the main method that subclasses must implement to define
        agent-specific behavior.

        Args:
            prompt: Input prompt to process
            context: Optional context information

        Returns:
            Agent's response to the prompt
        """
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert agent to dictionary representation.

        Returns:
            Dictionary containing agent data
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agent_type": self.agent_type.value,
            "mode": self.mode.value,
            "state": self.state.value,
            "model": self.model,
            "parameters": self.parameters.to_dict(),
            "system_prompt": self.system_prompt,
            "tools": [t.to_dict() for t in self.tools],
            "tool_names": self.tool_names,
            "parent_id": self.parent_id,
            "swarm_id": self.swarm_id,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "message_count": len(self._conversation_history),
        }

    def __repr__(self) -> str:
        """Return string representation of the agent."""
        return (
            f"{self.__class__.__name__}("
            f"id={self.id!r}, "
            f"name={self.name!r}, "
            f"type={self.agent_type.value}, "
            f"mode={self.mode.value}, "
            f"state={self.state.value})"
        )
