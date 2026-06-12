"""model-constellation Tools System - Package initialization.

Provides tools for agent execution including:
- Tool definitions and schemas
- Tool registry for managing tools
- Tool executor for running tools
- Built-in tools (bash, read, write, glob, grep, web search, etc.
"""

from model_constellation.tools.definitions import (
    Tool,
    ToolCategory,
    ToolParameter,
    ToolParameter as Parameter,
    ToolResult,
    ToolExecution,
    ParameterType,
)

from model_constellation.tools.registry import (
    ToolRegistry,
    get_registry,
    set_registry,
)

from model_constellation.tools.executor import (
    ToolExecutor,
    ExecutionContext,
    CommandExecutor,
)

from model_constellation.tools.builtin import (
    get_all_builtin_tools,
    register_builtin_tools,
    create_bash_tool,
    create_read_tool,
    create_write_tool,
    create_glob_tool,
    create_grep_tool,
    create_websearch_tool,
    create_webfetch_tool,
    create_codesearch_tool,
    create_list_tool,
    create_tree_tool,
    BashTool,
    ReadTool,
    WriteTool,
    GlobTool,
    GrepTool,
    WebSearchTool,
    WebFetchTool,
    CodeSearchTool,
    ListTool,
    TreeTool,
)

__all__ = [
    # Definitions
    "Tool",
    "ToolCategory",
    "ToolParameter",
    "Parameter",
    "ToolResult",
    "ToolExecution",
    "ParameterType",
    # Registry
    "ToolRegistry",
    "get_registry",
    "set_registry",
    # Executor
    "ToolExecutor",
    "ExecutionContext",
    "CommandExecutor",
    # Built-in tools
    "get_all_builtin_tools",
    "register_builtin_tools",
    "create_bash_tool",
    "create_read_tool",
    "create_write_tool",
    "create_glob_tool",
    "create_grep_tool",
    "create_websearch_tool",
    "create_webfetch_tool",
    "create_codesearch_tool",
    "create_list_tool",
    "create_tree_tool",
    # Tool classes
    "BashTool",
    "ReadTool",
    "WriteTool",
    "GlobTool",
    "GrepTool",
    "WebSearchTool",
    "WebFetchTool",
    "CodeSearchTool",
    "ListTool",
    "TreeTool",
]
