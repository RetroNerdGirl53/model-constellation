"""Tool definitions - Base classes and data structures for the model-constellation tool system."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Categories for organizing tools.

    Attributes:
        FILE: File operations (read, write, glob, grep)
        SYSTEM: System operations (bash, environment)
        NETWORK: Network operations (webfetch, websearch)
        AGENT: Agent operations (create_agent, delegate_task)
        GENERAL: General-purpose tools
        CUSTOM: User-defined custom tools
    """

    FILE = "file"
    SYSTEM = "system"
    NETWORK = "network"
    AGENT = "agent"
    GENERAL = "general"
    CUSTOM = "custom"

    def __str__(self) -> str:
        return self.value


class ParameterType(Enum):
    """Supported parameter types for tools.

    Attributes:
        STRING: String value
        INTEGER: Integer value
        FLOAT: Floating-point value
        BOOLEAN: Boolean value
        ARRAY: Array/list value
        OBJECT: Object/dict value
    """

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"

    def __str__(self) -> str:
        return self.value


@dataclass
class ToolParameter:
    """Definition of a parameter for a tool.

    Attributes:
        name: Parameter name.
        type: Parameter type.
        description: Human-readable description.
        required: Whether the parameter is required.
        default: Default value if optional.
        enum: Allowed values for enum-like parameters.
        min_value: Minimum value for numeric types.
        max_value: Maximum value for numeric types.
    """

    name: str
    type: ParameterType
    description: str
    required: bool = False
    default: Any = None
    enum: Optional[List[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None

    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """Validate a value for this parameter.

        Args:
            value: The value to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if value is None:
            if self.required:
                return False, f"Required parameter '{self.name}' is missing"
            return True, None

        if self.type == ParameterType.STRING:
            if not isinstance(value, str):
                return False, f"Parameter '{self.name}' must be a string"
        elif self.type == ParameterType.INTEGER:
            if not isinstance(value, int) or isinstance(value, bool):
                return False, f"Parameter '{self.name}' must be an integer"
            if self.min_value is not None and value < self.min_value:
                return False, f"Parameter '{self.name}' must be >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Parameter '{self.name}' must be <= {self.max_value}"
        elif self.type == ParameterType.FLOAT:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False, f"Parameter '{self.name}' must be a number"
            if self.min_value is not None and value < self.min_value:
                return False, f"Parameter '{self.name}' must be >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Parameter '{self.name}' must be <= {self.max_value}"
        elif self.type == ParameterType.BOOLEAN:
            if not isinstance(value, bool):
                return False, f"Parameter '{self.name}' must be a boolean"
        elif self.type == ParameterType.ARRAY:
            if not isinstance(value, list):
                return False, f"Parameter '{self.name}' must be an array"
        elif self.type == ParameterType.OBJECT:
            if not isinstance(value, dict):
                return False, f"Parameter '{self.name}' must be an object"

        if self.enum and value not in self.enum:
            return False, f"Parameter '{self.name}' must be one of: {self.enum}"

        return True, None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary representation of the parameter.
        """
        result = {
            "name": self.name,
            "type": str(self.type),
            "description": self.description,
            "required": self.required,
        }
        if self.default is not None:
            result["default"] = self.default
        if self.enum:
            result["enum"] = self.enum
        if self.min_value is not None:
            result["min_value"] = self.min_value
        if self.max_value is not None:
            result["max_value"] = self.max_value
        return result


@dataclass
class ToolResult:
    """Result of tool execution.

    Attributes:
        success: Whether the tool executed successfully.
        output: The output from the tool.
        error: Error message if execution failed.
        duration_ms: Execution time in milliseconds.
        tool_name: Name of the tool that was executed.
        parameters: Parameters used for execution.
    """

    success: bool
    output: Any = ""
    error: Optional[str] = None
    duration_ms: int = 0
    tool_name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def ok(cls, output: Any = "", tool_name: str = "", **kwargs) -> ToolResult:
        """Create a successful result.

        Args:
            output: The tool output.
            tool_name: Name of the tool.
            **kwargs: Additional fields.

        Returns:
            ToolResult with success=True.
        """
        return cls(success=True, output=output, tool_name=tool_name, **kwargs)

    @classmethod
    def error(cls, error: str, tool_name: str = "", **kwargs) -> ToolResult:
        """Create an error result.

        Args:
            error: Error message.
            tool_name: Name of the tool.
            **kwargs: Additional fields.

        Returns:
            ToolResult with success=False.
        """
        return cls(success=False, error=error, tool_name=tool_name, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary representation of the result.
        """
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Tool:
    """Base class for all tools in model-constellation.

    Attributes:
        name: Unique identifier for the tool.
        description: Human-readable description of what the tool does.
        category: Category the tool belongs to.
        parameters: List of parameter definitions.
        handler: Callable that executes the tool.
        timeout: Maximum execution time in milliseconds.
        enabled: Whether the tool is currently enabled.
        danger_level: Risk level associated with the tool.
    """

    name: str
    description: str
    category: ToolCategory
    parameters: List[ToolParameter] = field(default_factory=list)
    handler: Optional[Callable[..., Any]] = None
    timeout: int = 30000
    enabled: bool = True
    danger_level: str = "safe"

    def __post_init__(self):
        """Validate tool after initialization."""
        if not self.name:
            raise ValueError("Tool name cannot be empty")
        if not self.description:
            raise ValueError("Tool description cannot be empty")

    def validate_parameters(self, params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate parameters against the tool's schema.

        Args:
            params: Parameters to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        for param in self.parameters:
            value = params.get(param.name)
            is_valid, error = param.validate(value)
            if not is_valid:
                return False, error

        required_params = [p.name for p in self.parameters if p.required]
        missing = [p for p in required_params if p not in params]
        if missing:
            return False, f"Missing required parameters: {missing}"

        return True, None

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """Execute the tool with given parameters.

        Args:
            parameters: Parameters to pass to the tool handler.

        Returns:
            ToolResult of the execution.
        """
        if not self.enabled:
            return ToolResult.error(
                f"Tool '{self.name}' is disabled",
                tool_name=self.name,
                parameters=parameters,
            )

        is_valid, error = self.validate_parameters(parameters)
        if not is_valid:
            return ToolResult.error(
                f"Parameter validation failed: {error}",
                tool_name=self.name,
                parameters=parameters,
            )

        if self.handler is None:
            return ToolResult.error(
                f"Tool '{self.name}' has no handler configured",
                tool_name=self.name,
                parameters=parameters,
            )

        start_time = datetime.now()
        try:
            result = self.handler(**parameters)
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return ToolResult.ok(
                output=result,
                tool_name=self.name,
                parameters=parameters,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            logger.exception(f"Error executing tool '{self.name}'")
            return ToolResult.error(
                error=str(e),
                tool_name=self.name,
                parameters=parameters,
                duration_ms=duration_ms,
            )

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get JSON schema for the tool's parameters.

        Returns:
            JSON schema dictionary.
        """
        properties = {}
        required = []

        for param in self.parameters:
            prop = {
                "description": param.description,
            }

            if param.type == ParameterType.STRING:
                prop["type"] = "string"
            elif param.type == ParameterType.INTEGER:
                prop["type"] = "integer"
            elif param.type == ParameterType.FLOAT:
                prop["type"] = "number"
            elif param.type == ParameterType.BOOLEAN:
                prop["type"] = "boolean"
            elif param.type == ParameterType.ARRAY:
                prop["type"] = "array"
            elif param.type == ParameterType.OBJECT:
                prop["type"] = "object"

            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            if param.min_value is not None:
                prop["minimum"] = param.min_value
            if param.max_value is not None:
                prop["maximum"] = param.max_value

            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        schema = {
            "type": "object",
            "properties": properties,
        }
        if required:
            schema["required"] = required

        return schema

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary representation of the tool.
        """
        return {
            "name": self.name,
            "description": self.description,
            "category": str(self.category),
            "parameters": [p.to_dict() for p in self.parameters],
            "timeout": self.timeout,
            "enabled": self.enabled,
            "danger_level": self.danger_level,
        }


@dataclass
class ToolExecution:
    """Record of a tool execution for logging/tracking.

    Attributes:
        id: Unique execution ID.
        tool_name: Name of the tool executed.
        parameters: Parameters used.
        result: Result of the execution.
        status: Execution status (success, failed, timeout).
        duration_ms: Execution time in milliseconds.
        timestamp: When the execution occurred.
    """

    id: str
    tool_name: str
    parameters: Dict[str, Any]
    result: Optional[ToolResult] = None
    status: str = "pending"
    duration_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "result": self.result.to_dict() if self.result else None,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }
