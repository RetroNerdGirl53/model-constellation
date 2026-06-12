"""Tool executor - Executes tools with permission checking and error handling."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

from model_constellation.permissions import (
    PermissionManager,
    PermissionMode,
    PermissionResult,
    DangerLevel,
    DangerDetector,
)
from model_constellation.tools.definitions import Tool, ToolExecution, ToolResult
from model_constellation.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """Context for tool execution.

    Attributes:
        session_id: Current session identifier.
        agent_id: ID of the agent requesting execution.
        agent_name: Name of the agent requesting execution.
        conversation_id: ID of the current conversation.
        metadata: Additional context metadata.
    """

    session_id: str = "default"
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    conversation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolExecutor:
    """Executes tools with permission checking and error handling.

    Manages the full lifecycle of tool execution including:
    - Permission checking
    - Danger assessment
    - Execution with timeout
    - Error handling
    - Result logging
    """

    def __init__(
        self,
        registry: ToolRegistry,
        permission_manager: Optional[PermissionManager] = None,
        danger_detector: Optional[DangerDetector] = None,
    ):
        """Initialize the tool executor.

        Args:
            registry: Tool registry to use.
            permission_manager: Permission manager for authorization.
            danger_detector: Danger detector for risk assessment.
        """
        self.registry = registry
        self.permission_manager = permission_manager
        self.danger_detector = danger_detector or DangerDetector()
        self._execution_history: List[ToolExecution] = []
        self._max_history: int = 1000

    def execute(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        context: Optional[ExecutionContext] = None,
        skip_permission_check: bool = False,
    ) -> ToolResult:
        """Execute a tool with the given parameters.

        Args:
            tool_name: Name of the tool to execute.
            parameters: Parameters to pass to the tool.
            context: Execution context.
            skip_permission_check: Skip permission check (for testing).

        Returns:
            ToolResult of the execution.
        """
        context = context or ExecutionContext()
        execution_id = str(uuid.uuid4())

        tool = self.registry.get(tool_name)
        if not tool:
            return ToolResult.error(
                error=f"Tool '{tool_name}' not found",
                tool_name=tool_name,
                parameters=parameters,
            )

        if not tool.enabled:
            return ToolResult.error(
                error=f"Tool '{tool_name}' is disabled",
                tool_name=tool_name,
                parameters=parameters,
            )

        execution = ToolExecution(
            id=execution_id,
            tool_name=tool_name,
            parameters=parameters,
            status="pending",
        )

        if not skip_permission_check:
            permission_result = self._check_permission(tool, parameters, context)
            if not permission_result.allowed:
                execution.status = "denied"
                self._record_execution(execution)
                return ToolResult.error(
                    error=permission_result.reason or "Permission denied",
                    tool_name=tool_name,
                    parameters=parameters,
                )

        execution.status = "running"
        execution.timestamp = datetime.now()

        logger.info(
            f"Executing tool '{tool_name}' "
            f"(agent: {context.agent_name}, session: {context.session_id})"
        )

        try:
            result = self._execute_with_timeout(tool, parameters, tool.timeout)
            execution.result = result
            execution.status = "success" if result.success else "failed"
            execution.duration_ms = result.duration_ms

            self.registry.record_usage(tool_name)

        except TimeoutError:
            execution.status = "timeout"
            result = ToolResult.error(
                error=f"Tool execution timed out after {tool.timeout}ms",
                tool_name=tool_name,
                parameters=parameters,
            )
            execution.result = result

        except Exception as e:
            execution.status = "failed"
            logger.exception(f"Tool execution failed: {tool_name}")
            result = ToolResult.error(
                error=str(e),
                tool_name=tool_name,
                parameters=parameters,
            )
            execution.result = result

        self._record_execution(execution)
        return result

    def _check_permission(
        self,
        tool: Tool,
        parameters: Dict[str, Any],
        context: ExecutionContext,
    ) -> PermissionResult:
        """Check if tool execution is permitted.

        Args:
            tool: Tool to check.
            parameters: Tool parameters.
            context: Execution context.

        Returns:
            PermissionResult indicating whether execution is allowed.
        """
        if not self.permission_manager:
            return PermissionResult.allow(reason="No permission manager configured")

        category = self._get_tool_category(tool)

        return self.permission_manager.check_permission(
            tool_name=tool.name,
            parameters=parameters,
            category=category,
            session_id=context.session_id,
        )

    def _get_tool_category(self, tool: Tool) -> str:
        """Get the permission category for a tool.

        Args:
            tool: Tool to categorize.

        Returns:
            Category string.
        """
        category_map = {
            "file": "file",
            "system": "system",
            "network": "network",
            "agent": "agent",
        }
        return category_map.get(str(tool.category), "general")

    def _execute_with_timeout(
        self,
        tool: Tool,
        parameters: Dict[str, Any],
        timeout_ms: int,
    ) -> ToolResult:
        """Execute a tool with timeout handling.

        Args:
            tool: Tool to execute.
            parameters: Parameters.
            timeout_ms: Timeout in milliseconds.

        Returns:
            ToolResult of execution.
        """
        import signal

        class TimeoutException(Exception):
            pass

        def timeout_handler(signum, frame):
            raise TimeoutException()

        # SIGALRM-based timeouts only work on the main thread of the main
        # interpreter. When that isn't available (worker threads, some embedded
        # contexts) we degrade gracefully to running without a hard timeout
        # rather than crashing the whole execution.
        alarm_active = False
        old_handler = signal.SIG_DFL
        if timeout_ms > 0 and hasattr(signal, "SIGALRM"):
            try:
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.setitimer(signal.ITIMER_REAL, timeout_ms / 1000.0)
                alarm_active = True
            except (ValueError, OSError):
                alarm_active = False

        try:
            result = tool.execute(parameters)
        except TimeoutException as exc:
            raise TimeoutError(f"Tool timed out after {timeout_ms}ms") from exc
        finally:
            if alarm_active:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, old_handler)

        return result

    def _record_execution(self, execution: ToolExecution) -> None:
        """Record an execution in history.

        Args:
            execution: Execution to record.
        """
        self._execution_history.append(execution)
        if len(self._execution_history) > self._max_history:
            self._execution_history = self._execution_history[-self._max_history :]

    def get_history(
        self,
        limit: Optional[int] = None,
        tool_name: Optional[str] = None,
    ) -> List[ToolExecution]:
        """Get execution history.

        Args:
            limit: Maximum number of records to return.
            tool_name: Filter by tool name.

        Returns:
            List of executions.
        """
        history = self._execution_history

        if tool_name:
            history = [e for e in history if e.tool_name == tool_name]

        if limit:
            history = history[-limit:]

        return history

    def clear_history(self) -> None:
        """Clear execution history."""
        self._execution_history.clear()

    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics.

        Returns:
            Dictionary of statistics.
        """
        total = len(self._execution_history)
        if total == 0:
            return {
                "total_executions": 0,
                "success_rate": 0.0,
                "by_tool": {},
            }

        success = sum(1 for e in self._execution_history if e.status == "success")
        failed = sum(1 for e in self._execution_history if e.status == "failed")
        denied = sum(1 for e in self._execution_history if e.status == "denied")
        timeout = sum(1 for e in self._execution_history if e.status == "timeout")

        by_tool: Dict[str, Dict[str, int]] = {}
        for e in self._execution_history:
            if e.tool_name not in by_tool:
                by_tool[e.tool_name] = {
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "denied": 0,
                    "timeout": 0,
                }
            by_tool[e.tool_name]["total"] += 1
            if e.status in by_tool[e.tool_name]:
                by_tool[e.tool_name][e.status] += 1

        return {
            "total_executions": total,
            "success": success,
            "failed": failed,
            "denied": denied,
            "timeout": timeout,
            "success_rate": success / total if total > 0 else 0.0,
            "by_tool": by_tool,
        }


class CommandExecutor:
    """Executes shell commands for the bash tool.

    Provides a secure way to execute shell commands with proper
    environment handling and output capture.
    """

    def __init__(self, working_directory: Optional[str] = None):
        """Initialize the command executor.

        Args:
            working_directory: Default working directory for commands.
        """
        import os

        self.working_directory = working_directory or os.getcwd()
        self.env = os.environ.copy()

    def execute(
        self,
        command: str,
        timeout: int = 30000,
        environment: Optional[Dict[str, str]] = None,
        shell: bool = True,
    ) -> Dict[str, Any]:
        """Execute a shell command.

        Args:
            command: Command to execute.
            timeout: Timeout in milliseconds.
            environment: Additional environment variables.
            shell: Whether to execute through shell.

        Returns:
            Dictionary with output, error, return_code, and duration_ms.
        """
        import subprocess
        import os

        start_time = datetime.now()

        env = self.env.copy()
        if environment:
            env.update(environment)

        cwd = self.working_directory

        try:
            process = subprocess.Popen(
                command,
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=cwd,
                text=True,
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout / 1000.0)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                return {
                    "output": stdout,
                    "error": "Command timed out",
                    "return_code": -1,
                    "duration_ms": duration_ms,
                    "timed_out": True,
                }

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return {
                "output": stdout,
                "error": stderr,
                "return_code": process.returncode,
                "duration_ms": duration_ms,
                "timed_out": False,
            }

        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return {
                "output": "",
                "error": str(e),
                "return_code": -1,
                "duration_ms": duration_ms,
                "timed_out": False,
            }

    def set_working_directory(self, path: str) -> None:
        """Set the working directory.

        Args:
            path: New working directory.
        """
        import os

        if os.path.isdir(path):
            self.working_directory = path
        else:
            raise ValueError(f"Directory does not exist: {path}")

    def get_working_directory(self) -> str:
        """Get the current working directory.

        Returns:
            Current working directory.
        """
        return self.working_directory
