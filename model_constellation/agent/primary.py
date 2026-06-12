"""Primary planning agent for model-constellation framework."""

from __future__ import annotations

import asyncio
import uuid
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
    CommunicationBus,
    CommunicationMode,
    MessagePriority,
)
from model_constellation.agent.sub import SubAgent, SubAgentConfig, SubAgentFactory
from model_constellation.agent.toolcalling import (
    ToolCall,
    coerce_result_text,
    extract_tool_calls,
)


@dataclass
class ToolRequest:
    """Represents a request to execute a tool."""

    tool_name: str
    parameters: Dict[str, Any]
    purpose: str = ""
    risk_level: str = "low"


@dataclass
class PermissionRequest:
    """Represents a request for user permission."""

    tool_request: ToolRequest
    agent_id: str
    agent_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    approved: Optional[bool] = None


class PrimaryAgent(BaseAgent):
    """Primary planning agent that coordinates sub-agents and tool execution.

    The primary agent is the main orchestrator that:
    - Receives and processes user queries
    - Plans task execution
    - Creates and manages sub-agents
    - Handles tool execution with permission system
    - Synthesizes results from sub-agents

    Attributes:
        sub_agents: Dictionary of active sub-agents
        permission_callback: Callback for permission requests
        tool_executor: Tool executor instance
        ollama_client: Ollama API client
    """

    def __init__(
        self,
        config: AgentConfig,
        agent_id: Optional[str] = None,
        permission_callback: Optional[callable] = None,
        tool_executor: Optional[Any] = None,
        ollama_client: Optional[Any] = None,
    ):
        """Initialize primary agent.

        Args:
            config: Agent configuration
            agent_id: Optional custom agent ID
            permission_callback: Callback for permission requests
            tool_executor: Tool executor instance
            ollama_client: Ollama API client
        """
        super().__init__(
            config=config,
            agent_type=AgentType.PRIMARY,
            mode=AgentMode.ISOLATED,
            agent_id=agent_id,
        )

        self.sub_agents: Dict[str, SubAgent] = {}
        self.permission_callback = permission_callback
        self.tool_executor = tool_executor
        self.ollama_client = ollama_client
        self.communicator = CommunicationBus().get_communicator(CommunicationMode.PRIMARY_ONLY)
        self.communicator.set_primary_agent(self.id)

        self.session_id: str = "default"
        # Audit trail of tools run during the most recent ``process`` call.
        self.tool_executions: List[Dict[str, Any]] = []

        self._permission_cache: Dict[str, bool] = {}
        self._iteration = 0

    async def process(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Process a user prompt as the primary agent.

        Args:
            prompt: User input prompt
            context: Optional context information

        Returns:
            Agent's response
        """
        self._iteration = 0
        self.tool_executions = []
        self.set_state(AgentState.RUNNING)

        self.add_user_message(prompt)

        if context:
            for key, value in context.items():
                self.update_metadata(key, value)

        final_content = ""

        while self._iteration < self.max_iterations:
            self._iteration += 1

            content, native_tool_calls = await self._generate_response()
            tool_calls = extract_tool_calls(content, native_tool_calls)

            self.add_assistant_message(content, native_tool_calls)
            if content:
                final_content = content

            if not tool_calls:
                break

            for tool_call in tool_calls:
                result = self._handle_tool_call(tool_call)
                self.add_tool_message(tool_call.name, result)

        if self._iteration >= self.max_iterations:
            self.update_metadata("max_iterations_reached", True)

        self.set_state(AgentState.COMPLETED)

        return final_content

    async def _generate_response(self) -> tuple[str, Optional[List[Dict[str, Any]]]]:
        """Generate a response from Ollama for the current conversation.

        Returns:
            Tuple of (assistant text content, native tool calls or None).
        """
        if not self.ollama_client:
            return "Error: Ollama client not available", None

        messages = self.get_messages_for_ollama()

        try:
            response = await self.ollama_client.async_chat(
                model=self.model,
                messages=messages,
                stream=False,
                tools=self.tool_schemas or None,
                **self.parameters.to_dict(),
            )
            return response.message.content, response.tool_calls
        except Exception as e:
            return f"Error generating response: {str(e)}", None

    def _handle_tool_call(self, tool_call: ToolCall) -> str:
        """Execute a single tool call through the tool executor.

        Permission enforcement and danger assessment live in the executor's
        :class:`~model_constellation.permissions.PermissionManager`, which is the
        single source of truth — the agent does not gate tools separately.

        Args:
            tool_call: The normalized tool call.

        Returns:
            Tool execution result as text.
        """
        tool_name = tool_call.name

        if not self.has_tool(tool_name):
            return self._record_tool_execution(
                tool_name, tool_call.arguments, False,
                f"Tool '{tool_name}' is not available to this agent",
            )

        if not self.tool_executor:
            return self._record_tool_execution(
                tool_name, tool_call.arguments, False, "Tool executor not available"
            )

        try:
            from model_constellation.tools.executor import ExecutionContext

            context = ExecutionContext(
                session_id=self.session_id,
                agent_id=self.id,
                agent_name=self.name,
            )
            result = self.tool_executor.execute(
                tool_name=tool_name,
                parameters=tool_call.arguments,
                context=context,
            )
        except Exception as e:  # pragma: no cover - defensive
            return self._record_tool_execution(
                tool_name, tool_call.arguments, False, f"Tool execution error: {str(e)}"
            )

        return self._record_tool_execution(
            tool_name,
            tool_call.arguments,
            getattr(result, "success", True),
            coerce_result_text(result),
        )

    def _record_tool_execution(
        self, tool_name: str, arguments: Dict[str, Any], success: bool, output: str
    ) -> str:
        """Append a tool execution to the audit trail and return its output text."""
        self.tool_executions.append(
            {
                "tool": tool_name,
                "arguments": arguments,
                "success": success,
                "output": output,
            }
        )
        return output

    async def _check_permission(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> bool:
        """Check if tool execution is permitted.

        Args:
            tool_name: Name of the tool
            parameters: Tool parameters

        Returns:
            True if allowed
        """
        if tool_name in self._permission_cache:
            return self._permission_cache[tool_name]

        if self.permission_callback:
            request = PermissionRequest(
                tool_request=ToolRequest(
                    tool_name=tool_name,
                    parameters=parameters,
                ),
                agent_id=self.id,
                agent_name=self.name,
            )
            approved = await self.permission_callback(request)
            if approved is not None:
                self._permission_cache[tool_name] = approved
                return approved

        return True

    async def create_sub_agent(
        self,
        name: str,
        agent_subtype: str = "specialized",
        model: Optional[str] = None,
        tools: Optional[List[str]] = None,
        mode: CommunicationMode = CommunicationMode.PRIMARY_ONLY,
    ) -> SubAgent:
        """Create a sub-agent.

        Args:
            name: Agent name
            agent_subtype: Type of sub-agent
            model: Ollama model (uses primary's model if not specified)
            tools: List of tool names
            mode: Communication mode

        Returns:
            Created sub-agent
        """
        config = SubAgentConfig(
            name=name,
            description=f"Sub-agent: {name}",
            agent_subtype=agent_subtype,
            model=model or self.model,
            parameters=self.parameters,
            system_prompt=self.system_prompt,
            tool_names=tools or self.tool_names,
            communication_mode=mode,
        )

        agent = SubAgent(
            config=config,
            parent_id=self.id,
            communicator=self.communicator,
        )

        self.sub_agents[agent.id] = agent

        if mode == CommunicationMode.SWARM:
            self.communicator.add_swarm_member(agent.id)

        return agent

    async def create_research_agent(
        self,
        name: str,
        tools: Optional[List[str]] = None,
    ) -> SubAgent:
        """Create a research sub-agent.

        Args:
            name: Agent name
            tools: Tool names

        Returns:
            Created research agent
        """
        return await self.create_sub_agent(
            name=name,
            agent_subtype="research",
            tools=tools,
        )

    async def create_code_agent(
        self,
        name: str,
        tools: Optional[List[str]] = None,
    ) -> SubAgent:
        """Create a code sub-agent.

        Args:
            name: Agent name
            tools: Tool names

        Returns:
            Created code agent
        """
        return await self.create_sub_agent(
            name=name,
            agent_subtype="code",
            tools=tools,
        )

    async def delegate_task(
        self,
        agent_id: str,
        task: str,
    ) -> Optional[str]:
        """Delegate a task to a sub-agent.

        Args:
            agent_id: ID of the sub-agent
            task: Task description

        Returns:
            Task result or None
        """
        agent = self.sub_agents.get(agent_id)
        if not agent:
            return None

        if not self.ollama_client:
            return "Ollama client not available"

        result = await agent.execute_task(
            task=task,
            ollama_client=self.ollama_client,
            tool_executor=self.tool_executor,
        )

        await agent.send_to_primary(
            content=f"Task completed: {result}",
            message_type="result",
        )

        return result

    async def get_sub_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a sub-agent.

        Args:
            agent_id: Sub-agent ID

        Returns:
            Status dictionary
        """
        agent = self.sub_agents.get(agent_id)
        if not agent:
            return None

        return {
            "id": agent.id,
            "name": agent.name,
            "state": agent.state.value,
            "type": agent.subtype,
            "result": agent.result,
            "message_count": len(agent.conversation_history),
        }

    async def terminate_sub_agent(self, agent_id: str) -> bool:
        """Terminate a sub-agent.

        Args:
            agent_id: Sub-agent ID

        Returns:
            True if terminated
        """
        agent = self.sub_agents.pop(agent_id, None)
        if not agent:
            return False

        agent.set_state(AgentState.TERMINATED)
        self.communicator.remove_swarm_member(agent_id)
        return True

    def clear_permission_cache(self) -> None:
        """Clear the permission cache."""
        self._permission_cache.clear()

    def get_active_sub_agents(self) -> List[SubAgent]:
        """Get list of active sub-agents.

        Returns:
            List of active sub-agents
        """
        return [agent for agent in self.sub_agents.values() if agent.state == AgentState.RUNNING]

    async def wait_for_sub_agent_results(
        self,
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """Wait for results from sub-agents.

        Args:
            timeout: Timeout in seconds

        Returns:
            Dictionary of results
        """
        results = {}
        start_time = datetime.now()

        while (datetime.now() - start_time).total_seconds() < timeout:
            active = self.get_active_sub_agents()
            if not active:
                break

            for agent in active:
                msg = await self.communicator.receive_message(
                    self.id,
                    timeout=0.5,
                )
                if msg and msg.message_type == "result":
                    results[agent.id] = {
                        "agent_name": agent.name,
                        "result": msg.content,
                    }

            await asyncio.sleep(0.1)

        return results

    def to_dict(self) -> Dict[str, Any]:
        """Convert primary agent to dictionary.

        Returns:
            Dictionary representation
        """
        data = super().to_dict()
        data.update(
            {
                "sub_agents": [
                    {
                        "id": agent.id,
                        "name": agent.name,
                        "type": agent.subtype,
                        "state": agent.state.value,
                    }
                    for agent in self.sub_agents.values()
                ],
                "iteration": self._iteration,
                "permission_cache_size": len(self._permission_cache),
            }
        )
        return data


class PrimaryAgentFactory:
    """Factory for creating primary agents."""

    @staticmethod
    def create(
        name: str = "Primary Agent",
        model: str = "llama2",
        system_prompt: Optional[str] = None,
        tools: Optional[List[str]] = None,
        permission_callback: Optional[callable] = None,
        tool_executor: Optional[Any] = None,
        ollama_client: Optional[Any] = None,
    ) -> PrimaryAgent:
        """Create a primary agent.

        Args:
            name: Agent name
            model: Ollama model
            system_prompt: System prompt
            tools: List of tool names
            permission_callback: Permission callback
            tool_executor: Tool executor
            ollama_client: Ollama client

        Returns:
            Configured primary agent
        """
        default_tools = [
            "bash",
            "read",
            "write",
            "glob",
            "grep",
            "webfetch",
            "websearch",
            "codesearch",
        ]

        default_prompt = (
            "You are model-constellation, an AI assistant powered by Ollama. "
            "You can execute tools to help complete tasks. "
            "Always explain your reasoning and ask for clarification when needed."
        )

        config = AgentConfig(
            name=name,
            description="Primary planning agent",
            model=model,
            system_prompt=system_prompt or default_prompt,
            tool_names=tools or default_tools,
        )

        return PrimaryAgent(
            config=config,
            permission_callback=permission_callback,
            tool_executor=tool_executor,
            ollama_client=ollama_client,
        )
