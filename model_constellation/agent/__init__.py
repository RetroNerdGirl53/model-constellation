"""Agent package for model-constellation framework.

This package provides the agent management system including:
- Base agent class
- Primary planning agent
- Sub-agent class
- Agent swarm coordinator
- Agent registry
- Agent communication
"""

from model_constellation.agent.base import (
    AgentConfig,
    AgentMode,
    AgentState,
    AgentType,
    BaseAgent,
    Message,
    ModelParameters,
    ToolDefinition,
)
from model_constellation.agent.communication import (
    AgentCommunicator,
    AgentMessage,
    CommunicationBus,
    CommunicationMode,
    MessagePriority,
    MessageQueue,
)
from model_constellation.agent.primary import PrimaryAgent, PrimaryAgentFactory
from model_constellation.agent.registry import (
    AgentRegistry,
    GlobalRegistry,
    RegistryEntry,
    RegistryEvent,
)
from model_constellation.agent.sub import SubAgent, SubAgentConfig, SubAgentFactory
from model_constellation.agent.swarm import (
    AgentSwarm,
    GlobalSwarmManager,
    SwarmManager,
    SwarmMode,
    SwarmResult,
    SwarmState,
    TaskDistribution,
)

__all__ = [
    # Base classes
    "BaseAgent",
    "AgentConfig",
    "AgentType",
    "AgentMode",
    "AgentState",
    "Message",
    "ModelParameters",
    "ToolDefinition",
    # Primary agent
    "PrimaryAgent",
    "PrimaryAgentFactory",
    "PermissionRequest",
    "ToolRequest",
    # Sub-agent
    "SubAgent",
    "SubAgentConfig",
    "SubAgentFactory",
    # Swarm
    "AgentSwarm",
    "SwarmManager",
    "SwarmMode",
    "SwarmState",
    "SwarmResult",
    "TaskDistribution",
    "GlobalSwarmManager",
    # Registry
    "AgentRegistry",
    "GlobalRegistry",
    "RegistryEntry",
    "RegistryEvent",
    # Communication
    "AgentCommunicator",
    "AgentMessage",
    "CommunicationBus",
    "CommunicationMode",
    "MessagePriority",
    "MessageQueue",
]
