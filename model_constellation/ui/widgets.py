"""Custom widgets for model-constellation TUI."""

from datetime import datetime
from typing import Any, Optional, Callable
import uuid

from pytermgui import Window, Label, Button, Splitter, Container

from model_constellation.models import Agent, AgentType, AgentMode, Message, ToolExecution, Swarm, SwarmMode


class MessageBubble(Container):
    """A message bubble widget for displaying chat messages."""

    def __init__(self, message: Message, *, is_user: bool = True, **kwargs: Any) -> None:
        self.message = message
        self.is_user = is_user
        self.message_id: str = str(uuid.uuid4())[:8]

        prefix = "You" if is_user else "model-constellation"
        timestamp = message.timestamp.strftime("%H:%M")

        role_color = "cyan" if is_user else "green"
        prefix_str = f"[{role_color} bold]{prefix}[/]"

        content = self._format_content(message.content)

        super().__init__(Label(f"[{timestamp}] {prefix_str}"), Label(content), **kwargs)

    def _format_content(self, content: str) -> str:
        """Format message content with markdown-like styling."""
        formatted = content
        formatted = formatted.replace("```", "[secondary]```[/]")
        formatted = formatted.replace("**", "[bold]")
        formatted = formatted.replace("*", "[italic]")
        return formatted

    def get_id(self) -> str:
        """Get unique identifier for this widget."""
        return self.message_id


class AgentStatusIndicator(Container):
    """Widget displaying agent status with visual indicator."""

    def __init__(self, agent: Agent, *, show_details: bool = False, **kwargs: Any) -> None:
        self.agent = agent

        status_icon = self._get_status_icon()
        status_color = self._get_status_color()

        type_emoji = self._get_type_emoji()
        type_str = type_emoji + " " + agent.agent_type.value.capitalize()
        mode_str = f"({agent.mode.value})"

        lines = [
            f"[bold]{agent.name}[/] {status_icon}",
            f"  Type: {type_str} {mode_str}",
            f"  Model: [italic]{agent.model}[/]",
        ]

        if show_details:
            lines.extend(
                [
                    f"  Tools: {', '.join(agent.tools) if agent.tools else 'none'}",
                    f"  Created: {agent.created_at.strftime('%Y-%m-%d %H:%M')}",
                ]
            )

            if agent.swarm_id:
                lines.append(f"  Swarm: {agent.swarm_id}")

        super().__init__(*[Label(line) for line in lines], **kwargs)

    def _get_status_icon(self) -> str:
        """Get status icon based on agent type."""
        return "●"

    def _get_status_color(self) -> str:
        """Get color for agent status."""
        if self.agent.agent_type == AgentType.PRIMARY:
            return "green"
        elif self.agent.agent_type == AgentType.CODE:
            return "blue"
        elif self.agent.agent_type == AgentType.RESEARCH:
            return "yellow"
        return "white"

    def _get_type_emoji(self) -> str:
        """Get emoji for agent type."""
        mapping = {
            AgentType.PRIMARY: "🎯",
            AgentType.SPECIALIZED: "🔧",
            AgentType.WORKER: "⚙️",
            AgentType.RESEARCH: "🔍",
            AgentType.CODE: "💻",
        }
        return mapping.get(self.agent.agent_type, "🤖")


class AgentListWidget(Container):
    """Widget displaying a list of agents."""

    def __init__(self, agents: list[Agent], *, selected_index: int = 0, **kwargs: Any) -> None:
        self.agents = agents
        self.selected_index = selected_index

        items = []
        for i, agent in enumerate(agents):
            prefix = "▶" if i == selected_index else " "
            items.append(AgentStatusIndicator(agent, show_details=False))

        super().__init__(*items, **kwargs)


class ModelInfoDisplay(Container):
    """Widget displaying model information."""

    def __init__(
        self, model_name: str, *, parameters: Optional[dict[str, Any]] = None, **kwargs: Any
    ) -> None:
        self.model_name = model_name
        self.parameters = parameters or {}

        lines = [
            f"[bold underline]{model_name}[/]",
            "",
        ]

        if self.parameters:
            lines.append("[bold]Parameters:[/]")
            for key, value in self.parameters.items():
                lines.append(f"  {key}: {value}")

        super().__init__(*[Label(line) for line in lines], **kwargs)


class ToolCallDisplay(Container):
    """Widget displaying tool call information."""

    def __init__(
        self, tool_name: str, parameters: dict[str, Any], *, status: str = "pending", **kwargs: Any
    ) -> None:
        self.tool_name = tool_name
        self.parameters = parameters
        self.status = status

        status_colors = {
            "pending": "yellow",
            "running": "blue",
            "success": "green",
            "failed": "red",
        }
        status_icon = {
            "pending": "○",
            "running": "◐",
            "success": "●",
            "failed": "✕",
        }

        color = status_colors.get(status, "white")
        icon = status_icon.get(status, "?")

        lines = [
            f"[{color}]{icon}[/] [bold]{tool_name}[/]",
        ]

        for key, value in parameters.items():
            if key != "self" and key != "cls":
                lines.append(f"  {key}: {value}")

        super().__init__(*[Label(line) for line in lines], **kwargs)


class SwarmStatusWidget(Container):
    """Widget displaying swarm status."""

    def __init__(self, swarm: Swarm, **kwargs: Any) -> None:
        self.swarm = swarm

        mode_icon = self._get_mode_icon()
        lines = [
            f"[bold underline]{swarm.name}[/] (ID: {swarm.id[:8]}...)",
            f"  Mode: {mode_icon} {swarm.mode.value}",
            f"  Agents: {len(swarm.agents)}",
            f"  Coordinator: {swarm.coordinator_id[:8]}...",
            f"  Created: {swarm.created_at.strftime('%Y-%m-%d %H:%M')}",
        ]

        super().__init__(*[Label(line) for line in lines], **kwargs)

    def _get_mode_icon(self) -> str:
        """Get icon for swarm mode."""
        mapping = {
            SwarmMode.PARALLEL: "⫴",
            SwarmMode.SEQUENTIAL: "→",
            SwarmMode.PIPELINE: "⟫",
            SwarmMode.ADAPTIVE: "⚡",
        }
        return mapping.get(self.swarm.mode, "?")


class PermissionRequestDialog(Container):
    """Dialog for requesting tool execution permission."""

    def __init__(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        *,
        risk_level: str = "medium",
        callback: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> None:
        self.tool_name = tool_name
        self.parameters = parameters
        self.risk_level = risk_level
        self.callback = callback

        risk_colors = {
            "low": "green",
            "medium": "yellow",
            "high": "red",
            "critical": "bold red",
        }
        risk_icons = {
            "low": "✓",
            "medium": "⚠",
            "high": "⚠⚠",
            "critical": "⛔",
        }

        color = risk_colors.get(risk_level, "white")
        icon = risk_icons.get(risk_level, "?")

        lines = [
            f"[{color} bold]{icon} Tool Execution Request[/]",
            "[bold]─────────────────────────────────[/]",
            f"Tool: [bold]{tool_name}[/]",
            "",
            "[bold]Parameters:[/]",
        ]

        for key, value in parameters.items():
            if key != "self" and key != "cls":
                val_str = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                lines.append(f"  {key}: {val_str}")

        super().__init__(*[Label(line) for line in lines], **kwargs)

    def get_buttons(self) -> list[Button]:
        """Get action buttons for the dialog."""
        return [
            Button("[green]Allow[/]", lambda *_: self._handle_response(True)),
            Button("[yellow]Deny[/]", lambda *_: self._handle_response(False)),
            Button("[blue]Allow All Session[/]", lambda *_: self._handle_response(True, True)),
        ]

    def _handle_response(self, allowed: bool, allow_all: bool = False) -> None:
        """Handle user response."""
        if self.callback:
            self.callback(allowed, allow_all)


class ProgressIndicator(Container):
    """Widget displaying progress indicator."""

    def __init__(
        self, *, label: str = "Processing", total: int = 100, current: int = 0, **kwargs: Any
    ) -> None:
        self.label = label
        self.total = total
        self.current = current

        super().__init__(Label(f"[bold]{label}[/]"), self._build_bar(), **kwargs)

    def _build_bar(self) -> Label:
        """Build progress bar."""
        percentage = (self.current / self.total) * 100 if self.total > 0 else 0
        bar_width = 30
        filled = int(bar_width * percentage / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        return Label(f"[blue]{bar}[/] {percentage:.1f}%")

    def update(self, current: int) -> None:
        """Update progress."""
        self.current = current


class TokenCountDisplay(Label):
    """Widget displaying token count."""

    def __init__(
        self,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        **kwargs: Any,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens

        text = self._build_text()
        super().__init__(text, **kwargs)

    def _build_text(self) -> str:
        """Build token count text."""
        return (
            f"[dim]Tokens:[/] "
            f"Prompt: {self.prompt_tokens} | "
            f"Completion: {self.completion_tokens} | "
            f"Total: {self.total_tokens}"
        )

    def update(
        self,
        *,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
    ) -> None:
        """Update token counts."""
        if prompt_tokens is not None:
            self.prompt_tokens = prompt_tokens
        if completion_tokens is not None:
            self.completion_tokens = completion_tokens
        if total_tokens is not None:
            self.total_tokens = total_tokens


class HeaderWidget(Container):
    """Header widget displaying model-constellation branding."""

    def __init__(self, **kwargs: Any) -> None:
        lines = [
            r"╔══════════════════════════════════════════╗",
            r"║     🤖 model-constellation - Ollama AI Agent Framework  ║",
            r"╚══════════════════════════════════════════╝",
        ]

        super().__init__(*[Label(line) for line in lines], **kwargs)


class StatusBar(Container):
    """Status bar widget."""

    def __init__(
        self, *, model: str = "", agent: str = "", permission_mode: str = "", **kwargs: Any
    ) -> None:
        self.model = model
        self.agent = agent
        self.permission_mode = permission_mode

        parts = []
        if model:
            parts.append(f"Model: [cyan]{model}[/]")
        if agent:
            parts.append(f"Agent: [green]{agent}[/]")
        if permission_mode:
            mode_color = {
                "first-time": "yellow",
                "every-time": "red",
                "allow-all": "green",
                "deny-all": "red",
            }.get(permission_mode, "white")
            parts.append(f"Permission: [{mode_color}]{permission_mode}[/]")

        text = " │ ".join(parts) if parts else "[dim]Ready[/]"

        super().__init__(Label(text), **kwargs)
