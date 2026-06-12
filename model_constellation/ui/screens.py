"""Main UI screens for model-constellation TUI."""

from typing import Any, Callable, Optional
from dataclasses import dataclass, field

from model_constellation.models import Agent, AgentType, Message, Swarm, PermissionMode, ModelParameters
from model_constellation.ui.widgets import (
    MessageBubble,
    AgentStatusIndicator,
    ModelInfoDisplay,
    ToolCallDisplay,
    SwarmStatusWidget,
    PermissionRequestDialog,
    ProgressIndicator,
    TokenCountDisplay,
    HeaderWidget,
    StatusBar,
)


@dataclass
class Screen:
    """Base class for UI screens."""

    name: str = ""
    title: str = ""


@dataclass
class ChatScreen(Screen):
    """Main chat screen with message display."""

    messages: list[Message] = field(default_factory=list)
    model: str = "llama2"
    agent_name: str = "Primary Agent"
    show_tokens: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
    streaming: bool = True

    def add_message(self, message: Message) -> None:
        """Add a message to the chat."""
        self.messages.append(message)

    def get_message_widgets(self) -> list[MessageBubble]:
        """Get widget list for messages."""
        widgets = []
        for msg in self.messages:
            is_user = msg.role == "user"
            widgets.append(MessageBubble(message=msg, is_user=is_user))
        return widgets


@dataclass
class AgentSelectionScreen(Screen):
    """Screen for selecting and managing agents."""

    agents: list[Agent] = field(default_factory=list)
    selected_index: int = 0

    def get_agent_widgets(self) -> list[AgentStatusIndicator]:
        """Get widget list for agents."""
        return [AgentStatusIndicator(agent, show_details=True) for agent in self.agents]

    def select_next(self) -> None:
        """Select next agent."""
        if self.agents:
            self.selected_index = (self.selected_index + 1) % len(self.agents)

    def select_previous(self) -> None:
        """Select previous agent."""
        if self.agents:
            self.selected_index = (self.selected_index - 1) % len(self.agents)

    def get_selected_agent(self) -> Optional[Agent]:
        """Get currently selected agent."""
        if self.agents and 0 <= self.selected_index < len(self.agents):
            return self.agents[self.selected_index]
        return None


@dataclass
class ModelSelectionScreen(Screen):
    """Screen for selecting Ollama models."""

    models: list[str] = field(default_factory=list)
    current_model: str = "llama2"
    selected_index: int = 0

    def get_model_widgets(self) -> list:
        """Get widget list for models."""
        widgets = []
        for i, model in enumerate(self.models):
            prefix = "▶ " if i == self.selected_index else "  "
            current = " (current)" if model == self.current_model else ""
            widgets.append(f"{prefix}{model}{current}")
        return widgets

    def select_next(self) -> None:
        """Select next model."""
        if self.models:
            self.selected_index = (self.selected_index + 1) % len(self.models)

    def select_previous(self) -> None:
        """Select previous model."""
        if self.models:
            self.selected_index = (self.selected_index - 1) % len(self.models)

    def get_selected_model(self) -> Optional[str]:
        """Get currently selected model."""
        if self.models and 0 <= self.selected_index < len(self.models):
            return self.models[self.selected_index]
        return None


@dataclass
class SettingsScreen(Screen):
    """Settings screen for configuration."""

    settings: dict[str, Any] = field(default_factory=dict)

    def get_setting_lines(self) -> list[str]:
        """Get setting lines for display."""
        lines = []
        for key, value in self.settings.items():
            lines.append(f"{key}: {value}")
        return lines


@dataclass
class PermissionScreen(Screen):
    """Screen for real-time permission requests."""

    pending_requests: list[dict[str, Any]] = field(default_factory=list)

    def add_request(
        self, tool_name: str, parameters: dict[str, Any], risk_level: str = "medium"
    ) -> None:
        """Add a pending permission request."""
        self.pending_requests.append(
            {
                "tool_name": tool_name,
                "parameters": parameters,
                "risk_level": risk_level,
            }
        )

    def get_request_widgets(self) -> list[PermissionRequestDialog]:
        """Get widget list for pending requests."""
        widgets = []
        for req in self.pending_requests:
            widgets.append(
                PermissionRequestDialog(
                    tool_name=req["tool_name"],
                    parameters=req["parameters"],
                    risk_level=req["risk_level"],
                )
            )
        return widgets


@dataclass
class HelpScreen(Screen):
    """Help screen with keyboard shortcuts and usage info."""

    def get_content(self) -> list[str]:
        """Get help content lines."""
        return [
            "Keyboard Shortcuts",
            "─" * 40,
            "",
            "General:",
            "  Ctrl+C      - Cancel current operation",
            "  Ctrl+L      - Clear screen",
            "  Ctrl+Q      - Quit",
            "  Tab         - Navigate",
            "",
            "Chat:",
            "  Enter       - Send message",
            "  Ctrl+N      - New chat",
            "  Ctrl+H      - Show history",
            "  Ctrl+T      - Toggle token count",
            "",
            "Navigation:",
            "  1           - Go to Chat",
            "  2           - Go to Agents",
            "  3           - Go to Models",
            "  4           - Go to Settings",
            "  ?           - Show Help",
            "",
            "Commands",
            "─" * 40,
            "",
            "/quit, /exit - Exit the application",
            "/clear       - Clear chat history",
            "/model       - Switch model",
            "/agent       - Switch agent",
            "/swarm       - Manage swarms",
            "/history     - View history",
            "/help        - Show this help",
        ]


@dataclass
class SwarmScreen(Screen):
    """Screen for managing agent swarms."""

    swarms: list[Swarm] = field(default_factory=list)
    selected_index: int = 0

    def get_swarm_widgets(self) -> list[SwarmStatusWidget]:
        """Get widget list for swarms."""
        return [SwarmStatusWidget(swarm) for swarm in self.swarms]

    def select_next(self) -> None:
        """Select next swarm."""
        if self.swarms:
            self.selected_index = (self.selected_index + 1) % len(self.swarms)

    def select_previous(self) -> None:
        """Select previous swarm."""
        if self.swarms:
            self.selected_index = (self.selected_index - 1) % len(self.swarms)

    def get_selected_swarm(self) -> Optional[Swarm]:
        """Get currently selected swarm."""
        if self.swarms and 0 <= self.selected_index < len(self.swarms):
            return self.swarms[self.selected_index]
        return None


@dataclass
class MainMenuScreen(Screen):
    """Main menu screen with navigation options."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="main_menu", title="model-constellation")

    def get_content(self) -> list[str]:
        """Get main menu content lines."""
        return [
            "╔══════════════════════════════════════════╗",
            "║     🤖 model-constellation - Ollama AI Agent Framework  ║",
            "╚══════════════════════════════════════════╝",
            "",
            "Select an option:",
            "",
            "1. Chat - Start a conversation",
            "2. Agents - Manage agents",
            "3. Models - Select model",
            "4. Swarms - Manage swarms",
            "5. Settings - Configure",
            "6. Help - Keyboard shortcuts",
            "",
            "Press number or click to navigate",
        ]


def build_chat_display(
    messages: list[Message],
    model: str,
    agent_name: str,
    show_tokens: bool = False,
) -> str:
    """Build a chat display with messages."""
    lines = [
        f"Chat - {agent_name} ({model})",
        "─" * 40,
        "",
    ]

    for msg in messages:
        is_user = msg.role == "user"
        prefix = "You" if is_user else "model-constellation"
        timestamp = msg.timestamp.strftime("%H:%M")
        role_color = "cyan" if is_user else "green"

        lines.append(f"[{timestamp}] {prefix}: {msg.content}")
        lines.append("")

    return "\n".join(lines)


def build_agent_list_display(
    agents: list[Agent],
    selected_index: int = 0,
) -> str:
    """Build a display for agent list."""
    lines = [
        "Agents",
        "─" * 40,
        "",
    ]

    for i, agent in enumerate(agents):
        prefix = "▶" if i == selected_index else " "
        lines.append(f"{prefix} {agent.name} ({agent.agent_type.value})")

    return "\n".join(lines)


def build_model_list_display(
    models: list[str],
    current_model: str,
    selected_index: int = 0,
) -> str:
    """Build a display for model list."""
    lines = [
        "Models",
        "─" * 40,
        "",
    ]

    for i, model in enumerate(models):
        prefix = "▶" if i == selected_index else " "
        current = " (current)" if model == current_model else ""
        lines.append(f"{prefix} {model}{current}")

    return "\n".join(lines)


def build_settings_display(settings: dict[str, Any]) -> str:
    """Build a settings display."""
    lines = [
        "Settings",
        "─" * 40,
        "",
    ]

    for key, value in settings.items():
        lines.append(f"{key}: {value}")

    return "\n".join(lines)


def build_help_display() -> str:
    """Build a help display."""
    help_screen = HelpScreen()
    return "\n".join(help_screen.get_content())
