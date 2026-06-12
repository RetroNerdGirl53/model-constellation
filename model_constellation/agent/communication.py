"""Agent communication system for model-constellation framework."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class CommunicationMode(Enum):
    """Communication modes for inter-agent messaging."""

    PRIMARY_ONLY = "primary_only"
    SWARM = "swarm"
    ISOLATED = "isolated"


class MessagePriority(Enum):
    """Priority levels for messages."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AgentMessage:
    """Message sent between agents."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    sender_name: str = ""
    recipient_id: Optional[str] = None
    recipient_name: Optional[str] = None
    content: str = ""
    message_type: str = "text"
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    reply_to: Optional[str] = None
    broadcast: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "recipient_id": self.recipient_id,
            "recipient_name": self.recipient_name,
            "content": self.content,
            "message_type": self.message_type,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "reply_to": self.reply_to,
            "broadcast": self.broadcast,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentMessage:
        """Create message from dictionary."""
        msg = cls(
            id=data.get("id", str(uuid.uuid4())),
            sender_id=data.get("sender_id", ""),
            sender_name=data.get("sender_name", ""),
            recipient_id=data.get("recipient_id"),
            recipient_name=data.get("recipient_name"),
            content=data.get("content", ""),
            message_type=data.get("message_type", "text"),
            priority=MessagePriority(data.get("priority", "normal")),
            metadata=data.get("metadata", {}),
            reply_to=data.get("reply_to"),
            broadcast=data.get("broadcast", False),
        )
        if "timestamp" in data:
            if isinstance(data["timestamp"], str):
                msg.timestamp = datetime.fromisoformat(data["timestamp"])
            else:
                msg.timestamp = data["timestamp"]
        return msg


class MessageQueue:
    """Queue for managing messages between agents."""

    def __init__(self, max_size: int = 1000):
        """Initialize message queue.

        Args:
            max_size: Maximum number of messages to store
        """
        self.max_size = max_size
        self._queues: Dict[str, asyncio.Queue] = {}
        self._history: List[AgentMessage] = []

    def get_queue(self, agent_id: str) -> asyncio.Queue:
        """Get or create queue for an agent.

        Args:
            agent_id: ID of the agent

        Returns:
            Queue for the agent
        """
        if agent_id not in self._queues:
            self._queues[agent_id] = asyncio.Queue(maxsize=self.max_size)
        return self._queues[agent_id]

    def enqueue(self, message: AgentMessage) -> None:
        """Add message to recipient's queue.

        Args:
            message: Message to enqueue
        """
        if message.recipient_id:
            queue = self.get_queue(message.recipient_id)
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                pass

        self._history.append(message)

    async def dequeue(self, agent_id: str, timeout: float = 1.0) -> Optional[AgentMessage]:
        """Get message from agent's queue.

        Args:
            agent_id: ID of the agent
            timeout: Timeout in seconds

        Returns:
            Message or None if queue is empty
        """
        queue = self.get_queue(agent_id)
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def get_history(
        self,
        agent_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AgentMessage]:
        """Get message history.

        Args:
            agent_id: Optional filter by agent (as sender or recipient)
            limit: Maximum number of messages to return

        Returns:
            List of messages
        """
        messages = self._history

        if agent_id:
            messages = [
                m for m in messages if m.sender_id == agent_id or m.recipient_id == agent_id
            ]

        return messages[-limit:]

    def clear_queue(self, agent_id: str) -> int:
        """Clear messages in agent's queue.

        Args:
            agent_id: ID of the agent

        Returns:
            Number of messages cleared
        """
        queue = self._queues.get(agent_id)
        if queue:
            cleared = queue.qsize()
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            return cleared
        return 0


class AgentCommunicator:
    """Handles communication between agents with different modes."""

    def __init__(
        self,
        mode: CommunicationMode = CommunicationMode.PRIMARY_ONLY,
        message_queue: Optional[MessageQueue] = None,
    ):
        """Initialize communicator.

        Args:
            mode: Communication mode
            message_queue: Optional shared message queue
        """
        self.mode = mode
        self.message_queue = message_queue or MessageQueue()
        self._handlers: Dict[str, Callable[[AgentMessage], None]] = {}
        self._primary_id: Optional[str] = None
        self._swarm_members: List[str] = []

    def set_primary_agent(self, agent_id: str) -> None:
        """Set the primary agent for PRIMARY_ONLY mode.

        Args:
            agent_id: ID of the primary agent
        """
        self._primary_id = agent_id

    def add_swarm_member(self, agent_id: str) -> None:
        """Add an agent to the swarm.

        Args:
            agent_id: ID of the agent to add
        """
        if agent_id not in self._swarm_members:
            self._swarm_members.append(agent_id)

    def remove_swarm_member(self, agent_id: str) -> None:
        """Remove an agent from the swarm.

        Args:
            agent_id: ID of the agent to remove
        """
        if agent_id in self._swarm_members:
            self._swarm_members.remove(agent_id)

    def get_swarm_members(self) -> List[str]:
        """Get list of swarm member IDs.

        Returns:
            List of agent IDs
        """
        return self._swarm_members.copy()

    def can_communicate(self, sender_id: str, recipient_id: Optional[str]) -> bool:
        """Check if communication is allowed between agents.

        Args:
            sender_id: ID of the sending agent
            recipient_id: ID of the receiving agent

        Returns:
            True if communication is allowed
        """
        if self.mode == CommunicationMode.ISOLATED:
            return False

        if self.mode == CommunicationMode.PRIMARY_ONLY:
            if recipient_id is None:
                return True
            return recipient_id == self._primary_id

        if self.mode == CommunicationMode.SWARM:
            return True

        return False

    def send_message(
        self,
        sender_id: str,
        sender_name: str,
        content: str,
        recipient_id: Optional[str] = None,
        recipient_name: Optional[str] = None,
        message_type: str = "text",
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
        broadcast: bool = False,
    ) -> Optional[AgentMessage]:
        """Send a message to another agent.

        Args:
            sender_id: ID of the sending agent
            sender_name: Name of the sending agent
            content: Message content
            recipient_id: ID of the recipient (None for broadcast in swarm mode)
            recipient_name: Name of the recipient
            message_type: Type of message
            priority: Message priority
            metadata: Additional metadata
            broadcast: Whether to broadcast to all

        Returns:
            The sent message or None if not allowed
        """
        if not self.can_communicate(sender_id, recipient_id):
            return None

        if broadcast and self.mode != CommunicationMode.SWARM:
            return None

        message = AgentMessage(
            sender_id=sender_id,
            sender_name=sender_name,
            recipient_id=recipient_id,
            recipient_name=recipient_name,
            content=content,
            message_type=message_type,
            priority=priority,
            metadata=metadata or {},
            broadcast=broadcast,
        )

        if broadcast:
            for member_id in self._swarm_members:
                if member_id != sender_id:
                    broadcast_msg = AgentMessage(
                        id=str(uuid.uuid4()),
                        sender_id=sender_id,
                        sender_name=sender_name,
                        recipient_id=member_id,
                        content=content,
                        message_type=message_type,
                        priority=priority,
                        metadata=metadata or {},
                    )
                    self.message_queue.enqueue(broadcast_msg)
        else:
            self.message_queue.enqueue(message)

        return message

    def broadcast_to_swarm(
        self,
        sender_id: str,
        sender_name: str,
        content: str,
        message_type: str = "text",
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[AgentMessage]:
        """Broadcast message to all swarm members.

        Args:
            sender_id: ID of the sending agent
            sender_name: Name of the sending agent
            content: Message content
            message_type: Type of message
            priority: Message priority
            metadata: Additional metadata

        Returns:
            List of broadcast messages
        """
        messages = []
        for member_id in self._swarm_members:
            if member_id != sender_id:
                msg = self.send_message(
                    sender_id=sender_id,
                    sender_name=sender_name,
                    content=content,
                    recipient_id=member_id,
                    message_type=message_type,
                    priority=priority,
                    metadata=metadata,
                )
                if msg:
                    messages.append(msg)
        return messages

    async def receive_message(
        self,
        agent_id: str,
        timeout: float = 1.0,
    ) -> Optional[AgentMessage]:
        """Receive a message for an agent.

        Args:
            agent_id: ID of the receiving agent
            timeout: Timeout in seconds

        Returns:
            Message or None if no message available
        """
        return await self.message_queue.dequeue(agent_id, timeout)

    def register_handler(
        self,
        message_type: str,
        handler: Callable[[AgentMessage], None],
    ) -> None:
        """Register a handler for a message type.

        Args:
            message_type: Type of message to handle
            handler: Handler function
        """
        self._handlers[message_type] = handler

    def handle_message(self, message: AgentMessage) -> None:
        """Handle a message with registered handler.

        Args:
            message: Message to handle
        """
        handler = self._handlers.get(message.message_type)
        if handler:
            handler(message)

    def get_message_history(
        self,
        agent_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AgentMessage]:
        """Get message history.

        Args:
            agent_id: Optional filter by agent
            limit: Maximum number of messages

        Returns:
            List of messages
        """
        return self.message_queue.get_history(agent_id, limit)

    def clear_agent_queue(self, agent_id: str) -> int:
        """Clear messages in agent's queue.

        Args:
            agent_id: ID of the agent

        Returns:
            Number of messages cleared
        """
        return self.message_queue.clear_queue(agent_id)


class CommunicationBus:
    """Global communication bus for all agents."""

    _instance: Optional[CommunicationBus] = None

    def __new__(cls) -> CommunicationBus:
        """Create or return singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the communication bus."""
        if self._initialized:
            return
        self._initialized = True
        self._communicators: Dict[str, AgentCommunicator] = {}
        self._default_communicator: Optional[AgentCommunicator] = None

    def get_communicator(
        self,
        mode: CommunicationMode = CommunicationMode.PRIMARY_ONLY,
    ) -> AgentCommunicator:
        """Get or create communicator for a mode.

        Args:
            mode: Communication mode

        Returns:
            Agent communicator
        """
        mode_key = mode.value
        if mode_key not in self._communicators:
            self._communicators[mode_key] = AgentCommunicator(mode=mode)
            if self._default_communicator is None:
                self._default_communicator = self._communicators[mode_key]
        return self._communicators[mode_key]

    def set_primary_only_mode(self, primary_agent_id: str) -> AgentCommunicator:
        """Set up primary-only communication mode.

        Args:
            primary_agent_id: ID of the primary agent

        Returns:
            Configured communicator
        """
        comm = self.get_communicator(CommunicationMode.PRIMARY_ONLY)
        comm.set_primary_agent(primary_agent_id)
        return comm

    def set_swarm_mode(self, member_ids: List[str]) -> AgentCommunicator:
        """Set up swarm communication mode.

        Args:
            member_ids: IDs of swarm members

        Returns:
            Configured communicator
        """
        comm = self.get_communicator(CommunicationMode.SWARM)
        for member_id in member_ids:
            comm.add_swarm_member(member_id)
        return comm

    def set_isolated_mode(self) -> AgentCommunicator:
        """Set up isolated communication mode.

        Returns:
            Configured communicator
        """
        return self.get_communicator(CommunicationMode.ISOLATED)
