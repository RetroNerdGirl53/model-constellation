"""Built-in tools for model-constellation.

Provides the core set of tools available to agents:
- Bash/Shell execution
- File read/write/list
- Web search/fetch
- Grep/Glob search
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from model_constellation.tools.definitions import (
    ParameterType,
    Tool,
    ToolCategory,
    ToolParameter,
)
from model_constellation.tools.executor import CommandExecutor

logger = logging.getLogger(__name__)


class BashTool:
    """Tool for executing shell commands."""

    name = "bash"
    description = "Execute shell commands in the terminal. Use for running programs, git commands, and other shell operations."
    category = ToolCategory.SYSTEM
    danger_level = "high"

    parameters = [
        ToolParameter(
            name="command",
            type=ParameterType.STRING,
            description="The shell command to execute",
            required=True,
        ),
        ToolParameter(
            name="timeout",
            type=ParameterType.INTEGER,
            description="Timeout in milliseconds (default: 30000)",
            required=False,
            default=30000,
            min_value=0,
            max_value=300000,
        ),
        ToolParameter(
            name="environment",
            type=ParameterType.OBJECT,
            description="Additional environment variables to set",
            required=False,
            default=None,
        ),
        ToolParameter(
            name="working_directory",
            type=ParameterType.STRING,
            description="Working directory for the command",
            required=False,
            default=None,
        ),
    ]

    def __init__(self, executor: Optional[CommandExecutor] = None):
        """Initialize the bash tool.

        Args:
            executor: Command executor to use.
        """
        self._executor = executor or CommandExecutor()

    def execute(
        self,
        command: str,
        timeout: int = 30000,
        environment: Optional[Dict[str, str]] = None,
        working_directory: Optional[str] = None,
    ) -> str:
        """Execute a shell command.

        Args:
            command: Command to execute.
            timeout: Timeout in milliseconds.
            environment: Environment variables.
            working_directory: Working directory.

        Returns:
            Command output as string.
        """
        old_cwd = None
        if working_directory:
            old_cwd = self._executor.get_working_directory()
            self._executor.set_working_directory(working_directory)

        try:
            result = self._executor.execute(
                command=command,
                timeout=timeout,
                environment=environment,
            )

            output_parts = []
            if result.get("output"):
                output_parts.append(result["output"])
            if result.get("error") and result.get("return_code", 0) != 0:
                output_parts.append(f"Error: {result['error']}")

            output = "\n".join(output_parts) if output_parts else ""

            if result.get("timed_out"):
                output += f"\n[Command timed out after {timeout}ms]"

            return output

        finally:
            if old_cwd:
                self._executor.set_working_directory(old_cwd)


class ReadTool:
    """Tool for reading file contents."""

    name = "read"
    description = "Read the contents of a file. Returns the file content as a string."
    category = ToolCategory.FILE
    danger_level = "safe"

    parameters = [
        ToolParameter(
            name="path",
            type=ParameterType.STRING,
            description="Path to the file to read",
            required=True,
        ),
        ToolParameter(
            name="offset",
            type=ParameterType.INTEGER,
            description="Line offset to start reading from (1-indexed)",
            required=False,
            default=0,
            min_value=0,
        ),
        ToolParameter(
            name="limit",
            type=ParameterType.INTEGER,
            description="Maximum number of lines to read",
            required=False,
            default=None,
            min_value=1,
        ),
    ]

    def execute(
        self,
        path: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> str:
        """Read file contents.

        Args:
            path: Path to file.
            offset: Line offset (0-indexed).
            limit: Maximum lines to read.

        Returns:
            File contents as string.
        """
        file_path = Path(path).expanduser().resolve()

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if offset > 0:
            lines = lines[offset:]

        if limit is not None:
            lines = lines[:limit]

        return "".join(lines)


class WriteTool:
    """Tool for writing content to files."""

    name = "write"
    description = "Write content to a file. Can create new files or overwrite existing ones."
    category = ToolCategory.FILE
    danger_level = "high"

    parameters = [
        ToolParameter(
            name="path",
            type=ParameterType.STRING,
            description="Path to the file to write",
            required=True,
        ),
        ToolParameter(
            name="content",
            type=ParameterType.STRING,
            description="Content to write to the file",
            required=True,
        ),
        ToolParameter(
            name="append",
            type=ParameterType.BOOLEAN,
            description="Append to file instead of overwriting",
            required=False,
            default=False,
        ),
    ]

    def execute(
        self,
        path: str,
        content: str,
        append: bool = False,
    ) -> str:
        """Write content to a file.

        Args:
            path: Path to file.
            content: Content to write.
            append: Whether to append instead of overwrite.

        Returns:
            Success message.
        """
        file_path = Path(path).expanduser().resolve()

        file_path.parent.mkdir(parents=True, exist_ok=True)

        mode = "a" if append else "w"
        with open(file_path, mode, encoding="utf-8") as f:
            f.write(content)

        action = "Appended to" if append else "Written to"
        return f"{action} {path}"


class GlobTool:
    """Tool for finding files by pattern."""

    name = "glob"
    description = (
        "Find files matching a glob pattern. Useful for searching for files by name patterns."
    )
    category = ToolCategory.FILE
    danger_level = "safe"

    parameters = [
        ToolParameter(
            name="pattern",
            type=ParameterType.STRING,
            description="Glob pattern to match (e.g., '**/*.py')",
            required=True,
        ),
        ToolParameter(
            name="path",
            type=ParameterType.STRING,
            description="Base directory to search from",
            required=False,
            default=".",
        ),
    ]

    def execute(
        self,
        pattern: str,
        path: str = ".",
    ) -> str:
        """Find files matching a glob pattern.

        Args:
            pattern: Glob pattern.
            path: Base directory.

        Returns:
            List of matching file paths as string.
        """
        base_path = Path(path).expanduser().resolve()

        if not base_path.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        matches = list(base_path.glob(pattern))

        if not matches:
            return "No files found matching pattern"

        result_lines = []
        for match in sorted(matches):
            rel_path = match.relative_to(base_path)
            result_lines.append(str(rel_path))

        return "\n".join(result_lines)


class GrepTool:
    """Tool for searching file contents."""

    name = "grep"
    description = "Search for text patterns in files. Returns matching lines with file paths."
    category = ToolCategory.FILE
    danger_level = "safe"

    parameters = [
        ToolParameter(
            name="pattern",
            type=ParameterType.STRING,
            description="Regex pattern to search for",
            required=True,
        ),
        ToolParameter(
            name="path",
            type=ParameterType.STRING,
            description="File or directory to search in",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="include",
            type=ParameterType.STRING,
            description="File pattern to include (e.g., '*.py')",
            required=False,
            default=None,
        ),
        ToolParameter(
            name="context",
            type=ParameterType.INTEGER,
            description="Number of lines of context to show",
            required=False,
            default=0,
            min_value=0,
            max_value=10,
        ),
    ]

    def execute(
        self,
        pattern: str,
        path: str = ".",
        include: Optional[str] = None,
        context: int = 0,
    ) -> str:
        """Search for pattern in files.

        Args:
            pattern: Regex pattern.
            path: Path to search.
            include: File pattern to include.
            context: Lines of context.

        Returns:
            Matching lines with file paths.
        """
        search_path = Path(path).expanduser().resolve()

        if not search_path.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        regex = re.compile(pattern)
        matches = []

        if search_path.is_file():
            files_to_search = [search_path]
        else:
            if include:
                files_to_search = list(search_path.glob(f"**/{include}"))
            else:
                files_to_search = [
                    f for f in search_path.rglob("*") if f.is_file() and not f.is_symlink()
                ]

        for file_path in files_to_search:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

                for i, line in enumerate(lines):
                    if regex.search(line):
                        rel_path = file_path.relative_to(search_path)
                        match_text = line.rstrip()
                        if context > 0:
                            start = max(0, i - context)
                            end = min(len(lines), i + context + 1)
                            context_lines = lines[start:end]
                            context_text = "".join(context_lines).rstrip()
                            matches.append(f"{rel_path}:{i + 1}:{context_text}")
                        else:
                            matches.append(f"{rel_path}:{i + 1}:{match_text}")

            except (UnicodeDecodeError, PermissionError):
                continue

        if not matches:
            return "No matches found"

        return "\n".join(matches)


class WebSearchTool:
    """Tool for searching the web."""

    name = "websearch"
    description = "Search the web for information using Exa AI search."
    category = ToolCategory.NETWORK
    danger_level = "medium"

    parameters = [
        ToolParameter(
            name="query",
            type=ParameterType.STRING,
            description="Search query",
            required=True,
        ),
        ToolParameter(
            name="num_results",
            type=ParameterType.INTEGER,
            description="Number of results to return",
            required=False,
            default=8,
            min_value=1,
            max_value=20,
        ),
    ]

    def execute(
        self,
        query: str,
        num_results: int = 8,
    ) -> str:
        """Search the web.

        Args:
            query: Search query.
            num_results: Number of results.

        Returns:
            Search results as string.
        """
        try:
            from model_constellation.tools.web_extras import web_search

            return web_search(query, num_results)
        except ImportError:
            return "Web search not available. Install required dependencies."


class WebFetchTool:
    """Tool for fetching web content."""

    name = "webfetch"
    description = "Fetch content from a URL. Supports HTML, Markdown, and plain text."
    category = ToolCategory.NETWORK
    danger_level = "medium"

    parameters = [
        ToolParameter(
            name="url",
            type=ParameterType.STRING,
            description="URL to fetch",
            required=True,
        ),
        ToolParameter(
            name="format",
            type=ParameterType.STRING,
            description="Output format: text, markdown, or html",
            required=False,
            default="markdown",
            enum=["text", "markdown", "html"],
        ),
    ]

    def execute(
        self,
        url: str,
        format: str = "markdown",
    ) -> str:
        """Fetch content from URL.

        Args:
            url: URL to fetch.
            format: Output format.

        Returns:
            Fetched content.
        """
        try:
            from model_constellation.tools.web_extras import web_fetch

            return web_fetch(url, format)
        except ImportError:
            return "Web fetch not available. Install required dependencies."


class CodeSearchTool:
    """Tool for searching code documentation."""

    name = "codesearch"
    description = "Search code documentation and examples using Exa Code API."
    category = ToolCategory.NETWORK
    danger_level = "medium"

    parameters = [
        ToolParameter(
            name="query",
            type=ParameterType.STRING,
            description="Search query for code examples",
            required=True,
        ),
        ToolParameter(
            name="tokens_num",
            type=ParameterType.INTEGER,
            description="Maximum tokens to return",
            required=False,
            default=5000,
            min_value=1000,
            max_value=50000,
        ),
    ]

    def execute(
        self,
        query: str,
        tokens_num: int = 5000,
    ) -> str:
        """Search code documentation.

        Args:
            query: Search query.
            tokens_num: Max tokens.

        Returns:
            Code search results.
        """
        try:
            from model_constellation.tools.web_extras import code_search

            return code_search(query, tokens_num)
        except ImportError:
            return "Code search not available. Install required dependencies."


class ListTool:
    """Tool for listing directory contents."""

    name = "ls"
    description = "List files and directories in a path."
    category = ToolCategory.FILE
    danger_level = "safe"

    parameters = [
        ToolParameter(
            name="path",
            type=ParameterType.STRING,
            description="Path to list",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="all",
            type=ParameterType.BOOLEAN,
            description="Show hidden files",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="long",
            type=ParameterType.BOOLEAN,
            description="Use long listing format",
            required=False,
            default=False,
        ),
    ]

    def execute(
        self,
        path: str = ".",
        all: bool = False,
        long: bool = False,
    ) -> str:
        """List directory contents.

        Args:
            path: Path to list.
            all: Show hidden files.
            long: Long format.

        Returns:
            Directory listing.
        """
        import os

        target_path = Path(path).expanduser().resolve()

        if not target_path.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        if not target_path.is_dir():
            return str(target_path.name)

        entries = []
        for entry in sorted(target_path.iterdir()):
            if not all and entry.name.startswith("."):
                continue

            if long:
                stat = entry.stat()
                mode = stat.st_mode
                size = stat.st_size
                name = entry.name
                if entry.is_dir():
                    name += "/"
                entries.append(f"{size:>10} {name}")
            else:
                name = entry.name
                if entry.is_dir():
                    name += "/"
                entries.append(name)

        return "\n".join(entries)


class TreeTool:
    """Tool for displaying directory tree."""

    name = "tree"
    description = "Display directory structure as a tree."
    category = ToolCategory.FILE
    danger_level = "safe"

    parameters = [
        ToolParameter(
            name="path",
            type=ParameterType.STRING,
            description="Root path for tree",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="depth",
            type=ParameterType.INTEGER,
            description="Maximum depth to display",
            required=False,
            default=3,
            min_value=1,
            max_value=10,
        ),
    ]

    def execute(
        self,
        path: str = ".",
        depth: int = 3,
    ) -> str:
        """Display directory tree.

        Args:
            path: Root path.
            depth: Max depth.

        Returns:
            Tree representation.
        """
        target_path = Path(path).expanduser().resolve()

        if not target_path.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        lines = [str(target_path)]

        def walk_directory(dir_path: Path, prefix: str = "", current_depth: int = 0):
            if current_depth >= depth:
                return

            try:
                entries = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            except PermissionError:
                return

            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                current_prefix = "└── " if is_last else "├── "
                lines.append(f"{prefix}{current_prefix}{entry.name}")

                if entry.is_dir():
                    extension = "    " if is_last else "│   "
                    walk_directory(entry, prefix + extension, current_depth + 1)

        if target_path.is_dir():
            walk_directory(target_path)

        return "\n".join(lines)


def create_bash_tool(executor: Optional[CommandExecutor] = None) -> Tool:
    """Create the bash tool.

    Args:
        executor: Command executor.

    Returns:
        Tool instance.
    """
    handler = BashTool(executor)
    return Tool(
        name=BashTool.name,
        description=BashTool.description,
        category=ToolCategory.SYSTEM,
        parameters=BashTool.parameters,
        handler=handler.execute,
        timeout=60000,
        danger_level="high",
    )


def create_read_tool() -> Tool:
    """Create the read tool.

    Returns:
        Tool instance.
    """
    return Tool(
        name=ReadTool.name,
        description=ReadTool.description,
        category=ToolCategory.FILE,
        parameters=ReadTool.parameters,
        handler=ReadTool().execute,
        timeout=10000,
        danger_level="safe",
    )


def create_write_tool() -> Tool:
    """Create the write tool.

    Returns:
        Tool instance.
    """
    return Tool(
        name=WriteTool.name,
        description=WriteTool.description,
        category=ToolCategory.FILE,
        parameters=WriteTool.parameters,
        handler=WriteTool().execute,
        timeout=30000,
        danger_level="high",
    )


def create_glob_tool() -> Tool:
    """Create the glob tool.

    Returns:
        Tool instance.
    """
    return Tool(
        name=GlobTool.name,
        description=GlobTool.description,
        category=ToolCategory.FILE,
        parameters=GlobTool.parameters,
        handler=GlobTool().execute,
        timeout=30000,
        danger_level="safe",
    )


def create_grep_tool() -> Tool:
    """Create the grep tool.

    Returns:
        Tool instance.
    """
    return Tool(
        name=GrepTool.name,
        description=GrepTool.description,
        category=ToolCategory.FILE,
        parameters=GrepTool.parameters,
        handler=GrepTool().execute,
        timeout=60000,
        danger_level="safe",
    )


def create_websearch_tool() -> Tool:
    """Create the websearch tool.

    Returns:
        Tool instance.
    """
    return Tool(
        name=WebSearchTool.name,
        description=WebSearchTool.description,
        category=ToolCategory.NETWORK,
        parameters=WebSearchTool.parameters,
        handler=WebSearchTool().execute,
        timeout=30000,
        danger_level="medium",
    )


def create_webfetch_tool() -> Tool:
    """Create the webfetch tool.

    Returns:
        Tool instance.
    """
    return Tool(
        name=WebFetchTool.name,
        description=WebFetchTool.description,
        category=ToolCategory.NETWORK,
        parameters=WebFetchTool.parameters,
        handler=WebFetchTool().execute,
        timeout=30000,
        danger_level="medium",
    )


def create_codesearch_tool() -> Tool:
    """Create the codesearch tool.

    Returns:
        Tool instance.
    """
    return Tool(
        name=CodeSearchTool.name,
        description=CodeSearchTool.description,
        category=ToolCategory.NETWORK,
        parameters=CodeSearchTool.parameters,
        handler=CodeSearchTool().execute,
        timeout=30000,
        danger_level="medium",
    )


def create_list_tool() -> Tool:
    """Create the ls tool.

    Returns:
        Tool instance.
    """
    return Tool(
        name=ListTool.name,
        description=ListTool.description,
        category=ToolCategory.FILE,
        parameters=ListTool.parameters,
        handler=ListTool().execute,
        timeout=10000,
        danger_level="safe",
    )


def create_tree_tool() -> Tool:
    """Create the tree tool.

    Returns:
        Tool instance.
    """
    return Tool(
        name=TreeTool.name,
        description=TreeTool.description,
        category=ToolCategory.FILE,
        parameters=TreeTool.parameters,
        handler=TreeTool().execute,
        timeout=30000,
        danger_level="safe",
    )


def get_all_builtin_tools(
    command_executor: Optional[CommandExecutor] = None,
) -> List[Tool]:
    """Get all built-in tools.

    Args:
        command_executor: Optional command executor for bash tool.

    Returns:
        List of all built-in tools.
    """
    return [
        create_bash_tool(command_executor),
        create_read_tool(),
        create_write_tool(),
        create_glob_tool(),
        create_grep_tool(),
        create_websearch_tool(),
        create_webfetch_tool(),
        create_codesearch_tool(),
        create_list_tool(),
        create_tree_tool(),
    ]


def register_builtin_tools(registry, command_executor: Optional[CommandExecutor] = None):
    """Register all built-in tools with a registry.

    Args:
        registry: Tool registry to register with.
        command_executor: Optional command executor for bash tool.
    """
    for tool in get_all_builtin_tools(command_executor):
        registry.register(tool)
