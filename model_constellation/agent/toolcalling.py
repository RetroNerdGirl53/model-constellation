"""Canonical tool-call handling for the agent framework.

This module is the single source of truth for two things every agent needs:

1. Turning a model response into a list of :class:`ToolCall` objects, using a
   **hybrid** strategy: prefer Ollama's native structured ``tool_calls`` and fall
   back to parsing ``[TOOL_CALL]`` text markers for models that don't support
   native function calling.
2. Building the native tool *schema* list that gets passed to Ollama via the
   ``tools=`` argument.

Keeping this logic here (rather than duplicated inside ``primary.py`` and
``sub.py``) is what makes tool calling behave identically everywhere.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TOOL_MARKER = "[TOOL_CALL]"


@dataclass
class ToolCall:
    """A normalized request from the model to run one tool.

    Attributes:
        name: The tool name.
        arguments: Keyword arguments to pass to the tool.
    """

    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)

    def to_native(self) -> Dict[str, Any]:
        """Return the Ollama-native ``tool_calls`` dict shape for this call."""
        return {"function": {"name": self.name, "arguments": self.arguments}}


def extract_tool_calls(
    content: str,
    native_tool_calls: Optional[List[Dict[str, Any]]] = None,
) -> List[ToolCall]:
    """Extract tool calls from a model response (hybrid native + text markers).

    Args:
        content: The assistant's text content.
        native_tool_calls: Normalized native tool calls from the Ollama response
            (``ChatResponse.tool_calls``), if any.

    Returns:
        A list of :class:`ToolCall`. Empty when the model asked for no tools.
    """
    if native_tool_calls:
        calls: List[ToolCall] = []
        for call in native_tool_calls:
            function = call.get("function", {}) if isinstance(call, dict) else {}
            name = function.get("name", "")
            arguments = function.get("arguments", {})
            if not isinstance(arguments, dict):
                arguments = {}
            if name:
                calls.append(ToolCall(name=name, arguments=arguments))
        if calls:
            return calls

    if content and _TOOL_MARKER in content:
        return _parse_text_markers(content)

    return []


def _parse_text_markers(content: str) -> List[ToolCall]:
    """Parse legacy ``[TOOL_CALL]`` text markers from a response.

    Two block formats are supported after each marker:

    * A JSON object: ``{"name": "bash", "arguments": {"command": "ls"}}``
    * Line-oriented: first line is the tool name, following ``key: value`` lines
      are arguments.
    """
    calls: List[ToolCall] = []

    for block in content.split(_TOOL_MARKER)[1:]:
        block = block.strip()
        if not block:
            continue

        call = _parse_json_block(block)
        if call is None:
            call = _parse_lines_block(block)
        if call is not None and call.name:
            calls.append(call)

    return calls


def _parse_json_block(block: str) -> Optional[ToolCall]:
    """Try to parse a tool call from a JSON object at the start of ``block``."""
    match = re.search(r"\{.*\}", block, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    name = data.get("name") or data.get("tool") or ""
    arguments = data.get("arguments") or data.get("parameters") or {}
    if not isinstance(arguments, dict):
        arguments = {}
    if not name:
        return None
    return ToolCall(name=str(name), arguments=arguments)


def _parse_lines_block(block: str) -> Optional[ToolCall]:
    """Parse a tool call from the line-oriented marker format."""
    lines = block.splitlines()
    if not lines:
        return None

    name = lines[0].strip()
    if not name:
        return None

    arguments: Dict[str, Any] = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            arguments[key.strip()] = value.strip()

    return ToolCall(name=name, arguments=arguments)


def tool_to_schema(tool: Any) -> Dict[str, Any]:
    """Build an Ollama-native tool schema from a tool-like object.

    Uses duck typing so the agent package stays decoupled from the tools package:
    any object exposing ``name``, ``description`` and ``get_parameters_schema()``
    works (notably :class:`model_constellation.tools.definitions.Tool`).

    Args:
        tool: A tool-like object.

    Returns:
        A dict in Ollama's ``{"type": "function", "function": {...}}`` format.
    """
    if hasattr(tool, "get_parameters_schema"):
        parameters = tool.get_parameters_schema()
    else:
        parameters = {"type": "object", "properties": {}}

    return {
        "type": "function",
        "function": {
            "name": getattr(tool, "name", ""),
            "description": getattr(tool, "description", ""),
            "parameters": parameters,
        },
    }


def tools_to_schemas(tools: List[Any]) -> List[Dict[str, Any]]:
    """Build native tool schemas for a list of tool-like objects."""
    return [tool_to_schema(tool) for tool in tools]


def coerce_result_text(result: Any) -> str:
    """Convert a tool execution result into text the model can read.

    Handles :class:`model_constellation.tools.definitions.ToolResult` (via duck
    typing on ``success``/``output``/``error``) as well as plain values, so agents
    never accidentally feed a dataclass ``repr`` back into the conversation.

    Args:
        result: The value returned by a tool executor.

    Returns:
        A human/model-readable string.
    """
    if result is None:
        return ""

    # Duck-type a ToolResult.
    if hasattr(result, "success") and (hasattr(result, "output") or hasattr(result, "error")):
        if getattr(result, "success"):
            output = getattr(result, "output", "")
            return output if isinstance(output, str) else str(output)
        return f"Error: {getattr(result, 'error', '') or 'tool failed'}"

    return result if isinstance(result, str) else str(result)
