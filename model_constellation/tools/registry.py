"""Tool registry - Manages registration and discovery of tools."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from model_constellation.tools.definitions import Tool, ToolCategory, ToolParameter

logger = logging.getLogger(__name__)


@dataclass
class ToolMetadata:
    """Metadata for a registered tool.

    Attributes:
        tool: The tool instance.
        registered_at: When the tool was registered.
        use_count: Number of times the tool has been executed.
        last_used: Last time the tool was used.
    """

    tool: Tool
    registered_at: Any = field(default_factory=lambda: __import__("datetime").datetime.now())
    use_count: int = 0
    last_used: Optional[Any] = field(default=None)


class ToolRegistry:
    """Central registry for all available tools.

    Manages tool registration, discovery, and lifecycle.
    """

    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, ToolMetadata] = {}
        self._categories: Dict[ToolCategory, Set[str]] = {
            category: set() for category in ToolCategory
        }
        self._aliases: Dict[str, str] = {}

    def register(
        self,
        tool: Tool,
        aliases: Optional[List[str]] = None,
        override: bool = False,
    ) -> None:
        """Register a tool with the registry.

        Args:
            tool: Tool to register.
            aliases: Optional list of aliases for the tool.
            override: Whether to override an existing tool with the same name.

        Raises:
            ValueError: If tool name is already registered and override=False.
        """
        if tool.name in self._tools and not override:
            raise ValueError(f"Tool '{tool.name}' is already registered")

        self._tools[tool.name] = ToolMetadata(tool=tool)

        if tool.category in self._categories:
            self._categories[tool.category].add(tool.name)
        else:
            self._categories[tool.category] = {tool.name}

        if aliases:
            for alias in aliases:
                self._aliases[alias] = tool.name

        logger.info(f"Registered tool: {tool.name}")

    def unregister(self, tool_name: str) -> bool:
        """Unregister a tool from the registry.

        Args:
            tool_name: Name of the tool to unregister.

        Returns:
            True if tool was unregistered, False if not found.
        """
        if tool_name not in self._tools:
            return False

        tool = self._tools[tool_name].tool
        if tool.category in self._categories:
            self._categories[tool.category].discard(tool_name)

        for alias, original in list(self._aliases.items()):
            if original == tool_name:
                del self._aliases[alias]

        del self._tools[tool_name]
        logger.info(f"Unregistered tool: {tool_name}")
        return True

    def get(self, tool_name: str) -> Optional[Tool]:
        """Get a tool by name or alias.

        Args:
            tool_name: Name or alias of the tool.

        Returns:
            Tool instance or None if not found.
        """
        if tool_name in self._aliases:
            tool_name = self._aliases[tool_name]

        metadata = self._tools.get(tool_name)
        return metadata.tool if metadata else None

    def get_metadata(self, tool_name: str) -> Optional[ToolMetadata]:
        """Get metadata for a tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            ToolMetadata or None if not found.
        """
        if tool_name in self._aliases:
            tool_name = self._aliases[tool_name]
        return self._tools.get(tool_name)

    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        enabled_only: bool = True,
    ) -> List[Tool]:
        """List all registered tools.

        Args:
            category: Filter by category.
            enabled_only: Only return enabled tools.

        Returns:
            List of tools.
        """
        tools = []

        if category:
            tool_names = self._categories.get(category, set())
        else:
            tool_names = set(self._tools.keys())

        for name in tool_names:
            metadata = self._tools.get(name)
            if metadata:
                if enabled_only and not metadata.tool.enabled:
                    continue
                tools.append(metadata.tool)

        return tools

    def list_categories(self) -> List[ToolCategory]:
        """List all categories that have registered tools.

        Returns:
            List of categories.
        """
        return [category for category, tools in self._categories.items() if tools]

    def get_by_category(self, category: ToolCategory) -> List[Tool]:
        """Get all tools in a category.

        Args:
            category: Category to filter by.

        Returns:
            List of tools in the category.
        """
        return self.list_tools(category=category)

    def enable(self, tool_name: str) -> bool:
        """Enable a tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            True if enabled, False if not found.
        """
        tool = self.get(tool_name)
        if tool:
            tool.enabled = True
            return True
        return False

    def disable(self, tool_name: str) -> bool:
        """Disable a tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            True if disabled, False if not found.
        """
        tool = self.get(tool_name)
        if tool:
            tool.enabled = False
            return True
        return False

    def record_usage(self, tool_name: str) -> None:
        """Record that a tool was used.

        Args:
            tool_name: Name of the tool.
        """
        import datetime

        metadata = self.get_metadata(tool_name)
        if metadata:
            metadata.use_count += 1
            metadata.last_used = datetime.datetime.now()

    def get_statistics(self) -> Dict[str, Any]:
        """Get usage statistics for all tools.

        Returns:
            Dictionary of statistics.
        """
        stats = {}
        for name, metadata in self._tools.items():
            stats[name] = {
                "use_count": metadata.use_count,
                "last_used": metadata.last_used.isoformat() if metadata.last_used else None,
                "enabled": metadata.tool.enabled,
                "category": str(metadata.tool.category),
            }
        return stats

    def find_tools(self, query: str) -> List[Tool]:
        """Find tools matching a query string.

        Searches tool names and descriptions.

        Args:
            query: Search query.

        Returns:
            List of matching tools.
        """
        query_lower = query.lower()
        results = []

        for metadata in self._tools.values():
            tool = metadata.tool
            if query_lower in tool.name.lower() or query_lower in tool.description.lower():
                results.append(tool)

        return results

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        self._categories = {category: set() for category in ToolCategory}
        self._aliases.clear()
        logger.info("Tool registry cleared")

    def __len__(self) -> int:
        """Return number of registered tools."""
        return len(self._tools)

    def __contains__(self, tool_name: str) -> bool:
        """Check if a tool is registered."""
        return tool_name in self._tools or tool_name in self._aliases


_global_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry instance.

    Returns:
        The global ToolRegistry instance.
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def set_registry(registry: ToolRegistry) -> None:
    """Set the global tool registry.

    Args:
        registry: ToolRegistry instance to use.
    """
    global _global_registry
    _global_registry = registry
