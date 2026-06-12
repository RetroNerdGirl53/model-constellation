"""Sub-agent class for model-constellation framework."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

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
    CommunicationMode,
    MessagePriority,
)
from model_constellation.agent.toolcalling import (
    ToolCall,
    coerce_result_text,
    extract_tool_calls,
)


@dataclass
class SubAgentConfig:
    """Configuration for a sub-agent."""

    name: str
    description: str = ""
    agent_subtype: str = "specialized"
    model: str = "llama2"
    parameters: ModelParameters = field(default_factory=ModelParameters)
    system_prompt: str = ""
    tools: List[ToolDefinition] = field(default_factory=list)
    tool_names: List[str] = field(default_factory=list)
    max_iterations: int = 100
    timeout: int = 300000
    communication_mode: CommunicationMode = CommunicationMode.PRIMARY_ONLY


class SubAgent(BaseAgent):
    """Sub-agent for executing specific tasks.

    Sub-agents are created by the primary agent for specialized tasks.
    They can operate in different communication modes:
    - ISOLATED: Only communicates with primary agent
    - SWARM: Can communicate with other swarm agents
    - HIERARCHICAL: Reports only to parent agent

    Attributes:
        subtype: Type of sub-agent (specialized, worker, research, code)
        communication_mode: How the agent communicates
        parent_id: ID of the parent (primary) agent
        communicator: Communication handler
        result: Result from task execution
    """

    def __init__(
        self,
        config: SubAgentConfig,
        agent_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        swarm_id: Optional[str] = None,
        communicator: Optional[AgentCommunicator] = None,
    ):
        """Initialize a sub-agent.

        Args:
            config: Sub-agent configuration
            agent_id: Optional custom agent ID
            parent_id: ID of parent agent
            swarm_id: ID of swarm to join
            communicator: Optional communication handler
        """
        agent_type_map = {
            "specialized": AgentType.SPECIALIZED,
            "worker": AgentType.WORKER,
            "research": AgentType.RESEARCH,
            "code": AgentType.CODE,
        }
        agent_type = agent_type_map.get(config.agent_subtype, AgentType.SPECIALIZED)

        mode_map = {
            CommunicationMode.PRIMARY_ONLY: AgentMode.ISOLATED,
            CommunicationMode.SWARM: AgentMode.SWARM,
            CommunicationMode.ISOLATED: AgentMode.ISOLATED,
        }
        mode = mode_map.get(config.communication_mode, AgentMode.ISOLATED)

        agent_config = AgentConfig(
            name=config.name,
            description=config.description,
            model=config.model,
            parameters=config.parameters,
            system_prompt=config.system_prompt,
            tools=config.tools,
            tool_names=config.tool_names,
            max_iterations=config.max_iterations,
            timeout=config.timeout,
        )

        super().__init__(
            config=agent_config,
            agent_type=agent_type,
            mode=mode,
            agent_id=agent_id,
            parent_id=parent_id,
            swarm_id=swarm_id,
        )

        self.subtype = config.agent_subtype
        self.communication_mode = config.communication_mode
        self.communicator = communicator
        self.result: Optional[str] = None
        # Optional per-agent Ollama client. When set, the swarm uses it instead of
        # the shared one — this is what enables cross-server / cross-model swarms.
        self.ollama_client: Optional[Any] = None
        self.session_id: str = "default"
        self.tool_executions: List[Dict[str, Any]] = []
        self._task: Optional[str] = None
        self._execution_start: Optional[datetime] = None

    @property
    def is_complete(self) -> bool:
        """Check if agent has completed its task."""
        return self.state in (AgentState.COMPLETED, AgentState.FAILED)

    async def process(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Process a prompt as a sub-agent.

        Args:
            prompt: Input prompt to process
            context: Optional context information

        Returns:
            Agent's response
        """
        self._task = prompt
        self._execution_start = datetime.now()
        self.set_state(AgentState.RUNNING)

        self.add_user_message(prompt)

        if context:
            for key, value in context.items():
                self.update_metadata(key, value)

        return ""

    async def execute_task(
        self,
        task: str,
        ollama_client: Any = None,
        tool_executor: Any = None,
    ) -> str:
        """Execute a task and return the result.

        Args:
            task: Task description
            ollama_client: Client for Ollama API
            tool_executor: Tool executor instance

        Returns:
            Task result
        """
        self._task = task
        self._execution_start = datetime.now()
        self.tool_executions = []
        self.set_state(AgentState.RUNNING)

        self.add_user_message(task)

        response = await self._process_with_ollama(ollama_client, tool_executor)

        self.result = response
        if self.state == AgentState.RUNNING:
            self.set_state(AgentState.COMPLETED)

        return response

    async def _process_with_ollama(
        self,
        ollama_client: Any,
        tool_executor: Any,
    ) -> str:
        """Run the agentic loop using Ollama and the tool executor.

        Mirrors :meth:`PrimaryAgent.process`: chat, run any requested tools
        (hybrid native/text-marker), feed results back, repeat until the model
        stops requesting tools or ``max_iterations`` is reached.

        Args:
            ollama_client: Ollama client (must expose ``async_chat``).
            tool_executor: Tool executor (synchronous ``execute``).

        Returns:
            The final assistant text.
        """
        if not ollama_client:
            return "Ollama client not available"

        final_content = ""
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            messages = self.get_messages_for_ollama()

            try:
                response = await ollama_client.async_chat(
                    model=self.model,
                    messages=messages,
                    stream=False,
                    tools=self.tool_schemas or None,
                    **self.parameters.to_dict(),
                )
            except Exception as e:
                self.set_state(AgentState.FAILED)
                return f"Error: {str(e)}"

            content = response.message.content
            native_tool_calls = response.tool_calls
            tool_calls = extract_tool_calls(content, native_tool_calls)

            self.add_assistant_message(content, native_tool_calls)
            if content:
                final_content = content

            if not tool_calls or not tool_executor:
                break

            for tool_call in tool_calls:
                result = self._execute_tool(tool_call, tool_executor)
                self.add_tool_message(tool_call.name, result)

        return final_content

    def _execute_tool(self, tool_call: ToolCall, tool_executor: Any) -> str:
        """Execute a single tool call through the (synchronous) tool executor.

        Args:
            tool_call: The normalized tool call.
            tool_executor: Tool executor.

        Returns:
            Tool execution result as text.
        """
        tool_name = tool_call.name

        if not self.has_tool(tool_name):
            return f"Tool '{tool_name}' is not available to this agent"

        try:
            from model_constellation.tools.executor import ExecutionContext

            context = ExecutionContext(
                session_id=self.session_id,
                agent_id=self.id,
                agent_name=self.name,
            )
            result = tool_executor.execute(
                tool_name=tool_name,
                parameters=tool_call.arguments,
                context=context,
            )
        except Exception as e:  # pragma: no cover - defensive
            return f"Tool execution error: {str(e)}"

        text = coerce_result_text(result)
        self.tool_executions.append(
            {
                "tool": tool_name,
                "arguments": tool_call.arguments,
                "success": getattr(result, "success", True),
                "output": text,
            }
        )
        return text

    async def send_to_primary(
        self,
        content: str,
        message_type: str = "result",
    ) -> Optional[AgentMessage]:
        """Send a message to the primary agent.

        Args:
            content: Message content
            message_type: Type of message

        Returns:
            Sent message or None
        """
        if not self.communicator or not self.parent_id:
            return None

        return self.communicator.send_message(
            sender_id=self.id,
            sender_name=self.name,
            content=content,
            recipient_id=self.parent_id,
            message_type=message_type,
        )

    async def send_to_swarm(
        self,
        content: str,
        message_type: str = "broadcast",
    ) -> List[AgentMessage]:
        """Send a broadcast message to swarm members.

        Args:
            content: Message content
            message_type: Type of message

        Returns:
            List of sent messages
        """
        if not self.communicator:
            return []

        return self.communicator.broadcast_to_swarm(
            sender_id=self.id,
            sender_name=self.name,
            content=content,
            message_type=message_type,
        )

    async def receive_from_primary(
        self,
        timeout: float = 5.0,
    ) -> Optional[AgentMessage]:
        """Receive a message from the primary agent.

        Args:
            timeout: Timeout in seconds

        Returns:
            Received message or None
        """
        if not self.communicator:
            return None

        return await self.communicator.receive_message(self.id, timeout)

    def report_result(self, result: str) -> None:
        """Report task result.

        Args:
            result: Task result to report
        """
        self.result = result
        self.set_state(AgentState.COMPLETED)

    def report_error(self, error: str) -> None:
        """Report task error.

        Args:
            error: Error message
        """
        self.update_metadata("error", error)
        self.set_state(AgentState.FAILED)

    def get_execution_duration(self) -> Optional[float]:
        """Get execution duration in seconds.

        Returns:
            Duration in seconds or None if not executed
        """
        if self._execution_start:
            return (datetime.now() - self._execution_start).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert sub-agent to dictionary.

        Returns:
            Dictionary representation
        """
        data = super().to_dict()
        data.update(
            {
                "subtype": self.subtype,
                "communication_mode": self.communication_mode.value,
                "parent_id": self.parent_id,
                "task": self._task,
                "result": self.result,
                "execution_duration": self.get_execution_duration(),
            }
        )
        return data


class SubAgentFactory:
    """Factory for creating sub-agents."""

    @staticmethod
    def create_research_agent(
        name: str,
        model: str = "llama2",
        parent_id: Optional[str] = None,
        tools: Optional[List[str]] = None,
    ) -> SubAgent:
        """Create a research agent.

        Args:
            name: Agent name
            model: Ollama model
            parent_id: Parent agent ID
            tools: List of tool names

        Returns:
            Configured sub-agent
        """
        config = SubAgentConfig(
            name=name,
            description="Research agent for information gathering",
            agent_subtype="research",
            model=model,
            system_prompt=(
                "You are a research agent. Your goal is to gather and analyze information. "
                "Use available tools to search for information and provide comprehensive answers."
            ),
            tool_names=tools or ["websearch", "webfetch", "codesearch"],
            communication_mode=CommunicationMode.PRIMARY_ONLY,
        )
        return SubAgent(config=config, parent_id=parent_id)

    @staticmethod
    def create_code_agent(
        name: str,
        model: str = "llama2",
        parent_id: Optional[str] = None,
        tools: Optional[List[str]] = None,
    ) -> SubAgent:
        """Create a code agent.

        Args:
            name: Agent name
            model: Ollama model
            parent_id: Parent agent ID
            tools: List of tool names

        Returns:
            Configured sub-agent
        """
        config = SubAgentConfig(
            name=name,
            description="Code agent for software development",
            agent_subtype="code",
            model=model,
            system_prompt=(
                "You are a code agent. Your goal is to write, modify, and analyze code. "
                "Use available tools to read, write, and execute code. "
                "Always follow best practices and write clean, efficient code."
            ),
            tool_names=tools or ["bash", "read", "write", "glob", "grep"],
            communication_mode=CommunicationMode.PRIMARY_ONLY,
        )
        return SubAgent(config=config, parent_id=parent_id)

    @staticmethod
    def create_worker_agent(
        name: str,
        model: str = "llama2",
        parent_id: Optional[str] = None,
        swarm_id: Optional[str] = None,
        tools: Optional[List[str]] = None,
    ) -> SubAgent:
        """Create a worker agent for swarm execution.

        Args:
            name: Agent name
            model: Ollama model
            parent_id: Parent agent ID
            swarm_id: Swarm ID
            tools: List of tool names

        Returns:
            Configured sub-agent
        """
        config = SubAgentConfig(
            name=name,
            description="Worker agent for parallel task execution",
            agent_subtype="worker",
            model=model,
            system_prompt=(
                "You are a worker agent. Execute tasks assigned to you efficiently. "
                "Report results back to the coordinator."
            ),
            tool_names=tools or ["bash", "read", "write"],
            communication_mode=CommunicationMode.SWARM
            if swarm_id
            else CommunicationMode.PRIMARY_ONLY,
        )
        return SubAgent(
            config=config,
            parent_id=parent_id,
            swarm_id=swarm_id,
        )
