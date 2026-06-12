"""Enhanced UI screens for model-constellation TUI with pytermgui integration.

This module provides screen classes for:
- ModelSelectionScreen - Ollama model selection with details
- AgentManagementScreen - Agent creation and management
- SettingsScreen - Application settings configuration
- HelpScreen - Keyboard shortcuts and usage tips
- SwarmManagementScreen - Agent swarm management
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

import pytermgui
from pytermgui import tim
from pytermgui import Container, Splitter, Window
from pytermgui.widgets import Button, InputField, Label

from model_constellation.agent.base import (
    AgentType,
    AgentMode,
    AgentState,
    BaseAgent,
)
from model_constellation.agent.registry import AgentRegistry, GlobalRegistry
from model_constellation.models import Agent, Swarm, SwarmMode, PermissionMode, ModelParameters as ModelParams
from model_constellation.ollama_client import OllamaClient, ModelInfo
from model_constellation.ui.theme import ThemeManager, Theme, ThemeName


class BaseScreen:
    """Base class for all screens in the TUI."""

    def __init__(
        self,
        app: Optional["ThemedChatApp"] = None,
        theme_manager: Optional[ThemeManager] = None,
    ) -> None:
        self._app = app
        self._theme_manager = theme_manager
        self._window: Optional[Window] = None

    @property
    def theme_manager(self) -> ThemeManager:
        """Get the theme manager."""
        if self._theme_manager is None:
            from model_constellation.ui.theme import get_theme_manager

            self._theme_manager = get_theme_manager()
        return self._theme_manager

    def get_current_theme(self) -> Theme:
        """Get the current theme."""
        return self.theme_manager.get_current_theme() or Theme(
            name="default",
            display_name="Default",
        )

    def get_color(self, color_name: str) -> str:
        """Get a color from the current theme."""
        return self.theme_manager.get_color(color_name)

    def get_window(self) -> Optional[Window]:
        """Get the screen's window."""
        return self._window

    def refresh(self) -> None:
        """Refresh the screen content."""
        pass


class ModelSelectionScreen(BaseScreen):
    """Screen for selecting and filtering Ollama models.

    Features:
    - Scrollable list of available models
    - Model details (size, modified date)
    - Search/filter functionality
    - Current model indicator
    """

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        app: Optional["ThemedChatApp"] = None,
        theme_manager: Optional[ThemeManager] = None,
        on_select: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(app, theme_manager)
        self._client = ollama_client or OllamaClient()
        self._on_select_callback = on_select
        self._models: list[ModelInfo] = []
        self._filtered_models: list[ModelInfo] = []
        self._current_model: str = "llama2"
        self._selected_index: int = 0
        self._filter_text: str = ""
        self._is_loading: bool = False
        self._error_message: Optional[str] = None
        self._build_window()

    def _build_window(self) -> None:
        """Build the model selection window."""
        theme = self.get_current_theme()

        title = Label(f"[{theme.colors.accent} bold]Model Selection[/]")
        title.styles.fill = theme.colors.background

        self._filter_input = InputField()
        self._filter_input.placeholder = "Filter models..."
        self._filter_input.bind.submit = self._on_filter_submit

        self._model_list = Container(
            Label(f"[{theme.colors.secondary}]Loading models...[/]"),
        )

        self._details_container = Container(
            Label(f"[{theme.colors.secondary}]Select a model to see details[/]"),
        )

        button_row = Container(
            Button("[green]Select[/]", self._on_select_pressed),
            Button("[blue]Refresh[/]", self._on_refresh_pressed),
            Button("[yellow]Back[/]", self._on_back_pressed),
        )

        container = Container(
            title,
            Label(""),
            Label(f"[{theme.colors.accent}]Filter:[/]"),
            self._filter_input,
            Label(""),
            self._model_list,
            Label(""),
            self._details_container,
            Label(""),
            button_row,
        )

        self._window = Window(
            container,
            style=f"@{theme.colors.background}",
        )

    def _on_filter_submit(self) -> None:
        """Handle filter input submission."""
        self._filter_text = self._filter_input.value
        self._apply_filter()
        self._update_model_list()

    def _apply_filter(self) -> None:
        """Apply the current filter to the model list."""
        if not self._filter_text:
            self._filtered_models = self._models.copy()
        else:
            filter_lower = self._filter_text.lower()
            self._filtered_models = [
                m
                for m in self._models
                if filter_lower in m.name.lower() or filter_lower in (m.model or "").lower()
            ]
        self._selected_index = 0

    def _update_model_list(self) -> None:
        """Update the model list display."""
        theme = self.get_current_theme()

        if self._is_loading:
            self._model_list.widgets = [Label(f"[{theme.colors.secondary}]Loading models...[/]")]
            return

        if self._error_message:
            self._model_list.widgets = [Label(f"[{theme.colors.error}]{self._error_message}[/]")]
            return

        if not self._filtered_models:
            self._model_list.widgets = [Label(f"[{theme.colors.warning}]No models found[/]")]
            return

        widgets = []
        for i, model in enumerate(self._filtered_models):
            size_mb = (model.size / (1024 * 1024)) if model.size else 0
            prefix = "[green]▶[/]" if i == self._selected_index else "  "
            current = (
                f" [{theme.colors.accent}](current)[/]" if model.name == self._current_model else ""
            )
            widgets.append(
                Label(
                    f"{prefix} [{theme.colors.foreground}]{model.name}[/] ({size_mb:.1f} MB){current}"
                )
            )

        self._model_list.widgets = widgets

    def _update_details(self) -> None:
        """Update the model details panel."""
        theme = self.get_current_theme()

        if not self._filtered_models or self._selected_index >= len(self._filtered_models):
            self._details_container.widgets = [
                Label(f"[{theme.colors.secondary}]Select a model to see details[/]")
            ]
            return

        model = self._filtered_models[self._selected_index]
        size_mb = (model.size / (1024 * 1024)) if model.size else 0
        size_gb = size_mb / 1024

        details = [
            f"[{theme.colors.accent} bold underline]{model.name}[/]",
            f"[{theme.colors.foreground}]Size:[/] {size_gb:.2f} GB ({size_mb:.1f} MB)",
            f"[{theme.colors.foreground}]Modified:[/] {model.modified_at or 'Unknown'}",
        ]

        if model.details:
            if hasattr(model.details, "family"):
                details.append(f"[{theme.colors.foreground}]Family:[/] {model.details.family}")
            if hasattr(model.details, "parameter_size"):
                details.append(
                    f"[{theme.colors.foreground}]Parameters:[/] {model.details.parameter_size}"
                )

        self._details_container.widgets = [Label(line) for line in details]

    def load_models(self) -> None:
        """Load models from Ollama."""
        self._is_loading = True
        self._error_message = None
        self._update_model_list()

        try:
            self._models = self._client.list_models()
            self._apply_filter()
        except Exception as e:
            self._error_message = f"Failed to load models: {str(e)}"

        self._is_loading = False
        self._update_model_list()

    def set_current_model(self, model_name: str) -> None:
        """Set the current model."""
        self._current_model = model_name
        self._update_model_list()

    def select_next(self) -> None:
        """Select the next model."""
        if self._filtered_models:
            self._selected_index = (self._selected_index + 1) % len(self._filtered_models)
            self._update_model_list()
            self._update_details()

    def select_previous(self) -> None:
        """Select the previous model."""
        if self._filtered_models:
            self._selected_index = (self._selected_index - 1) % len(self._filtered_models)
            self._update_model_list()
            self._update_details()

    def get_selected_model(self) -> Optional[str]:
        """Get the currently selected model name."""
        if self._filtered_models and 0 <= self._selected_index < len(self._filtered_models):
            return self._filtered_models[self._selected_index].name
        return None

    def _on_select_pressed(self) -> None:
        """Handle select button press."""
        model = self.get_selected_model()
        if model and self._on_select_callback:
            self._on_select_callback(model)
        self._app._navigate_to("chat") if self._app else None

    def _on_refresh_pressed(self) -> None:
        """Handle refresh button press."""
        self.load_models()

    def _on_back_pressed(self) -> None:
        """Handle back button press."""
        if self._app:
            self._app._navigate_to("chat")

    def refresh(self) -> None:
        """Refresh the screen."""
        self.load_models()
        self._update_model_list()
        self._update_details()


class AgentManagementScreen(BaseScreen):
    """Screen for managing agents.

    Features:
    - List of available agents with status indicators
    - Create new agents
    - Delete existing agents
    - Visual status (running, idle, etc.)
    """

    def __init__(
        self,
        app: Optional["ThemedChatApp"] = None,
        theme_manager: Optional[ThemeManager] = None,
        on_select: Optional[Callable[[Agent], None]] = None,
    ) -> None:
        super().__init__(app, theme_manager)
        self._on_select_callback = on_select
        self._agents: list[Agent] = []
        self._selected_index: int = 0
        self._build_window()

    def _build_window(self) -> None:
        """Build the agent management window."""
        theme = self.get_current_theme()

        title = Label(f"[{theme.colors.accent} bold]Agent Management[/]")
        title.styles.fill = theme.colors.background

        self._agent_list = Container(
            Label(f"[{theme.colors.secondary}]No agents available[/]"),
        )

        self._agent_details = Container(
            Label(f"[{theme.colors.secondary}]Select an agent to see details[/]"),
        )

        button_row = Container(
            Button("[green]Create[/]", self._on_create_pressed),
            Button("[red]Delete[/]", self._on_delete_pressed),
            Button("[blue]Select[/]", self._on_select_pressed),
        )

        container = Container(
            title,
            Label(""),
            self._agent_list,
            Label(""),
            self._agent_details,
            Label(""),
            button_row,
        )

        self._window = Window(
            container,
            style=f"@{theme.colors.background}",
        )

    def _get_status_icon(self, state: AgentState) -> str:
        """Get status icon for agent state."""
        icons = {
            AgentState.IDLE: "[dim]○[/]",
            AgentState.RUNNING: "[green]◐[/]",
            AgentState.WAITING: "[yellow]◑[/]",
            AgentState.COMPLETED: "[green]●[/]",
            AgentState.FAILED: "[red]✕[/]",
            AgentState.TERMINATED: "[dim]⊘[/]",
        }
        return icons.get(state, "[dim]?[/]")

    def _get_type_icon(self, agent_type: AgentType) -> str:
        """Get icon for agent type."""
        icons = {
            AgentType.PRIMARY: "[cyan]🎯[/]",
            AgentType.SPECIALIZED: "[blue]🔧[/]",
            AgentType.WORKER: "[magenta]⚙️[/]",
            AgentType.RESEARCH: "[yellow]🔍[/]",
            AgentType.CODE: "[green]💻[/]",
        }
        return icons.get(agent_type, "[white]🤖[/]")

    def _update_agent_list(self) -> None:
        """Update the agent list display."""
        theme = self.get_current_theme()

        if not self._agents:
            self._agent_list.widgets = [Label(f"[{theme.colors.secondary}]No agents available[/]")]
            return

        widgets = []
        for i, agent in enumerate(self._agents):
            prefix = "[green]▶[/]" if i == self._selected_index else "  "
            status = self._get_status_icon(AgentState(agent.metadata.get("state", "idle")))
            type_icon = self._get_type_icon(AgentType(agent.agent_type.value))
            widgets.append(
                Label(f"{prefix} {type_icon} [{theme.colors.foreground}]{agent.name}[/] {status}")
            )

        self._agent_list.widgets = widgets

    def _update_agent_details(self) -> None:
        """Update the agent details panel."""
        theme = self.get_current_theme()

        if not self._agents or self._selected_index >= len(self._agents):
            self._agent_details.widgets = [
                Label(f"[{theme.colors.secondary}]Select an agent to see details[/]")
            ]
            return

        agent = self._agents[self._selected_index]
        state = AgentState(agent.metadata.get("state", "idle"))
        status_color = {
            AgentState.IDLE: "dim",
            AgentState.RUNNING: "green",
            AgentState.WAITING: "yellow",
            AgentState.COMPLETED: "green",
            AgentState.FAILED: "red",
            AgentState.TERMINATED: "dim",
        }.get(state, "white")

        details = [
            f"[{theme.colors.accent} bold underline]{agent.name}[/]",
            f"[{theme.colors.foreground}]Type:[/] {agent.agent_type.value}",
            f"[{theme.colors.foreground}]Mode:[/] {agent.mode.value}",
            f"[{theme.colors.foreground}]Model:[/] {agent.model}",
            f"[{status_color}]Status:[/] {state.value}",
            f"[{theme.colors.foreground}]Tools:[/] {', '.join(agent.tools) if agent.tools else 'none'}",
            f"[{theme.colors.foreground}]Created:[/] {agent.created_at.strftime('%Y-%m-%d %H:%M')}",
        ]

        if agent.swarm_id:
            details.append(f"[{theme.colors.foreground}]Swarm:[/] {agent.swarm_id}")

        self._agent_details.widgets = [Label(line) for line in details]

    def load_agents(self, agents: list[Agent]) -> None:
        """Load agents into the screen."""
        self._agents = agents
        self._selected_index = 0
        self._update_agent_list()
        self._update_agent_details()

    def select_next(self) -> None:
        """Select the next agent."""
        if self._agents:
            self._selected_index = (self._selected_index + 1) % len(self._agents)
            self._update_agent_list()
            self._update_agent_details()

    def select_previous(self) -> None:
        """Select the previous agent."""
        if self._agents:
            self._selected_index = (self._selected_index - 1) % len(self._agents)
            self._update_agent_list()
            self._update_agent_details()

    def get_selected_agent(self) -> Optional[Agent]:
        """Get the currently selected agent."""
        if self._agents and 0 <= self._selected_index < len(self._agents):
            return self._agents[self._selected_index]
        return None

    def _on_create_pressed(self) -> None:
        """Handle create button press."""
        pass

    def _on_delete_pressed(self) -> None:
        """Handle delete button press."""
        pass

    def _on_select_pressed(self) -> None:
        """Handle select button press."""
        agent = self.get_selected_agent()
        if agent and self._on_select_callback:
            self._on_select_callback(agent)

    def refresh(self) -> None:
        """Refresh the screen."""
        self._update_agent_list()
        self._update_agent_details()


class SettingsScreen(BaseScreen):
    """Screen for configuring application settings.

    Features:
    - Temperature slider
    - Top_p setting
    - Top_k setting
    - Theme selection
    - Permission mode
    - Context window size
    """

    def __init__(
        self,
        app: Optional["ThemedChatApp"] = None,
        theme_manager: Optional[ThemeManager] = None,
        on_settings_changed: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> None:
        super().__init__(app, theme_manager)
        self._on_settings_changed = on_settings_changed
        self._settings: dict[str, Any] = {
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "theme": "default",
            "permission_mode": "first-time",
            "context_window": 4096,
        }
        self._build_window()

    def _build_window(self) -> None:
        """Build the settings window."""
        theme = self.get_current_theme()

        title = Label(f"[{theme.colors.accent} bold]Settings[/]")
        title.styles.fill = theme.colors.background

        self._settings_container = Container()

        button_row = Container(
            Button("[green]Save[/]", self._on_save_pressed),
            Button("[yellow]Reset[/]", self._on_reset_pressed),
            Button("[blue]Back[/]", self._on_back_pressed),
        )

        container = Container(
            title,
            Label(""),
            self._settings_container,
            Label(""),
            button_row,
        )

        self._window = Window(
            container,
            style=f"@{theme.colors.background}",
        )

        self._update_settings_display()

    def _update_settings_display(self) -> None:
        """Update the settings display."""
        theme = self.get_current_theme()

        settings_widgets = [
            f"[{theme.colors.accent} bold underline]Model Parameters[/]",
            "",
            f"[{theme.colors.foreground}]Temperature:[/] {self._settings['temperature']}",
            f"[{theme.colors.secondary}](0.0 - 2.0, higher = more creative)[/]",
            "",
            f"[{theme.colors.foreground}]Top P:[/] {self._settings['top_p']}",
            f"[{theme.colors.secondary}](0.0 - 1.0, nucleus sampling)[/]",
            "",
            f"[{theme.colors.foreground}]Top K:[/] {self._settings['top_k']}",
            f"[{theme.colors.secondary}](1 - 100, vocabulary sampling)[/]",
            "",
            f"[{theme.colors.foreground}]Context Window:[/] {self._settings['context_window']}",
            f"[{theme.colors.secondary}](2048 - 128000 tokens)[/]",
            "",
            f"[{theme.colors.accent} bold underline]Appearance[/]",
            "",
            f"[{theme.colors.foreground}]Theme:[/] {self._settings['theme']}",
            "",
            f"[{theme.colors.accent} bold underline]Permissions[/]",
            "",
            f"[{theme.colors.foreground}]Permission Mode:[/] {self._settings['permission_mode']}",
            f"[{theme.colors.secondary}](first-time/every-time/allow-all/deny-all)[/]",
        ]

        self._settings_container.widgets = [Label(line) for line in settings_widgets]

    def get_settings(self) -> dict[str, Any]:
        """Get current settings."""
        return self._settings.copy()

    def set_settings(self, settings: dict[str, Any]) -> None:
        """Set settings."""
        self._settings.update(settings)
        self._update_settings_display()

    def update_setting(self, key: str, value: Any) -> None:
        """Update a single setting."""
        self._settings[key] = value
        self._update_settings_display()

    def _on_save_pressed(self) -> None:
        """Handle save button press."""
        if self._on_settings_changed:
            self._on_settings_changed(self._settings)

        theme_name = self._settings.get("theme")
        if theme_name:
            self.theme_manager.set_theme(theme_name)
            self.theme_manager.apply_theme()

    def _on_reset_pressed(self) -> None:
        """Handle reset button press."""
        self._settings = {
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "theme": "default",
            "permission_mode": "first-time",
            "context_window": 4096,
        }
        self._update_settings_display()

    def _on_back_pressed(self) -> None:
        """Handle back button press."""
        if self._app:
            self._app._navigate_to("chat")

    def refresh(self) -> None:
        """Refresh the screen."""
        self._update_settings_display()


class HelpScreen(BaseScreen):
    """Screen showing keyboard shortcuts and usage tips.

    Features:
    - Keyboard shortcuts
    - Command reference
    - Usage tips
    """

    def __init__(
        self,
        app: Optional["ThemedChatApp"] = None,
        theme_manager: Optional[ThemeManager] = None,
    ) -> None:
        super().__init__(app, theme_manager)
        self._build_window()

    def _build_window(self) -> None:
        """Build the help window."""
        theme = self.get_current_theme()

        title = Label(f"[{theme.colors.accent} bold]Help[/]")
        title.styles.fill = theme.colors.background

        help_content = self._get_help_content()

        content_container = Container(
            *[Label(line) for line in help_content],
        )

        button_row = Container(
            Button("[blue]Back[/]", self._on_back_pressed),
        )

        container = Container(
            title,
            Label(""),
            content_container,
            Label(""),
            button_row,
        )

        self._window = Window(
            container,
            style=f"@{theme.colors.background}",
        )

    def _get_help_content(self) -> list[str]:
        """Get the help content."""
        theme = self.get_current_theme()

        return [
            f"[{theme.colors.accent} bold]Keyboard Shortcuts[/]",
            f"[{theme.colors.border}]" + "─" * 50 + "[/]",
            "",
            f"[{theme.colors.foreground}]General:[/]",
            f"  [{theme.colors.accent}]Ctrl+C[/]     Quit the application",
            f"  [{theme.colors.accent}]Ctrl+L[/]     Clear screen/chat",
            f"  [{theme.colors.accent}]Ctrl+Q[/]     Quit (alternative)",
            f"  [{theme.colors.accent}]Tab[/]        Navigate",
            "",
            f"[{theme.colors.foreground}]Chat:[/]",
            f"  [{theme.colors.accent}]Enter[/]      Send message",
            f"  [{theme.colors.accent}]Ctrl+N[/]     New chat session",
            f"  [{theme.colors.accent}]Ctrl+T[/]     Toggle token count",
            "",
            f"[{theme.colors.foreground}]Navigation:[/]",
            f"  [{theme.colors.accent}]Ctrl+G[/]     Go to Chat",
            f"  [{theme.colors.accent}]Ctrl+M[/]     Go to Models",
            f"  [{theme.colors.accent}]Ctrl+A[/]     Go to Agents",
            f"  [{theme.colors.accent}]Ctrl+S[/]     Go to Settings",
            f"  [{theme.colors.accent}]Ctrl+H[/]     Show Help",
            f"  [{theme.colors.accent}]Esc[/]        Return to chat view",
            "",
            f"[{theme.colors.accent} bold]Commands[/]",
            f"[{theme.colors.border}]" + "─" * 50 + "[/]",
            "",
            f"  [{theme.colors.accent}]/quit, /exit[/]  Exit the application",
            f"  [{theme.colors.accent}]/clear[/]         Clear chat history",
            f"  [{theme.colors.accent}]/model <name>[/]  Switch model",
            f"  [{theme.colors.accent}]/agent <name>[/]  Switch agent",
            f"  [{theme.colors.accent}]/swarm[/]         Manage swarms",
            f"  [{theme.colors.accent}]/help[/]          Show this help",
            "",
            f"[{theme.colors.accent} bold]Tips[/]",
            f"[{theme.colors.border}]" + "─" * 50 + "[/]",
            "",
            f"[{theme.colors.secondary}]• Use Ctrl+T to cycle through themes",
            f"[{theme.colors.secondary}]• Models with larger context windows use more memory",
            f"[{theme.colors.secondary}]• Lower temperature = more focused, higher = more creative",
            f"[{theme.colors.secondary}]• Use swarms for parallel task execution",
            f"[{theme.colors.secondary}]• Permission mode 'allow-all' bypasses tool restrictions",
        ]

    def _on_back_pressed(self) -> None:
        """Handle back button press."""
        if self._app:
            self._app._navigate_to("chat")

    def refresh(self) -> None:
        """Refresh the screen."""
        self._build_window()


class SwarmManagementScreen(BaseScreen):
    """Screen for creating and managing agent swarms.

    Features:
    - List of existing swarms
    - Create new swarms
    - Configure swarm mode (parallel, sequential, pipeline, adaptive)
    - Add/remove agents from swarms
    - Visual swarm status
    """

    def __init__(
        self,
        app: Optional["ThemedChatApp"] = None,
        theme_manager: Optional[ThemeManager] = None,
        on_swarm_select: Optional[Callable[[Swarm], None]] = None,
    ) -> None:
        super().__init__(app, theme_manager)
        self._on_swarm_select = on_swarm_select
        self._swarms: list[Swarm] = []
        self._selected_index: int = 0
        self._build_window()

    def _build_window(self) -> None:
        """Build the swarm management window."""
        theme = self.get_current_theme()

        title = Label(f"[{theme.colors.accent} bold]Swarm Management[/]")
        title.styles.fill = theme.colors.background

        self._swarm_list = Container(
            Label(f"[{theme.colors.secondary}]No swarms available[/]"),
        )

        self._swarm_details = Container(
            Label(f"[{theme.colors.secondary}]Select a swarm to see details[/]"),
        )

        button_row = Container(
            Button("[green]Create[/]", self._on_create_pressed),
            Button("[red]Delete[/]", self._on_delete_pressed),
            Button("[blue]Manage[/]", self._on_manage_pressed),
        )

        container = Container(
            title,
            Label(""),
            f"[{theme.colors.accent}]Swarms:[/]",
            self._swarm_list,
            Label(""),
            self._swarm_details,
            Label(""),
            button_row,
        )

        self._window = Window(
            container,
            style=f"@{theme.colors.background}",
        )

    def _get_mode_icon(self, mode: SwarmMode) -> str:
        """Get icon for swarm mode."""
        icons = {
            SwarmMode.PARALLEL: "[cyan]⫴[/]",
            SwarmMode.SEQUENTIAL: "[green]→[/]",
            SwarmMode.PIPELINE: "[magenta]⟫[/]",
            SwarmMode.ADAPTIVE: "[yellow]⚡[/]",
        }
        return icons.get(mode, "[white]?[/]")

    def _update_swarm_list(self) -> None:
        """Update the swarm list display."""
        theme = self.get_current_theme()

        if not self._swarms:
            self._swarm_list.widgets = [Label(f"[{theme.colors.secondary}]No swarms available[/]")]
            return

        widgets = []
        for i, swarm in enumerate(self._swarms):
            prefix = "[green]▶[/]" if i == self._selected_index else "  "
            mode_icon = self._get_mode_icon(swarm.mode)
            agent_count = len(swarm.agents)
            widgets.append(
                Label(
                    f"{prefix} {mode_icon} [{theme.colors.foreground}]{swarm.name}[/] ({agent_count} agents)"
                )
            )

        self._swarm_list.widgets = widgets

    def _update_swarm_details(self) -> None:
        """Update the swarm details panel."""
        theme = self.get_current_theme()

        if not self._swarms or self._selected_index >= len(self._swarms):
            self._swarm_details.widgets = [
                Label(f"[{theme.colors.secondary}]Select a swarm to see details[/]")
            ]
            return

        swarm = self._swarms[self._selected_index]
        mode_icon = self._get_mode_icon(swarm.mode)

        details = [
            f"[{theme.colors.accent} bold underline]{swarm.name}[/]",
            f"[{theme.colors.foreground}]ID:[/] {swarm.id[:8]}...",
            f"[{theme.colors.foreground}]Mode:[/] {mode_icon} {swarm.mode.value}",
            f"[{theme.colors.foreground}]Agents:[/] {len(swarm.agents)}",
            f"[{theme.colors.foreground}]Coordinator:[/] {swarm.coordinator_id[:8]}...",
            f"[{theme.colors.foreground}]Created:[/] {swarm.created_at.strftime('%Y-%m-%d %H:%M')}",
            "",
            f"[{theme.colors.accent}]Agent List:[/]",
        ]

        for agent in swarm.agents:
            details.append(f"  • {agent.name} ({agent.agent_type.value})")

        if not swarm.agents:
            details.append(f"  [{theme.colors.secondary}](no agents)[/]")

        self._swarm_details.widgets = [Label(line) for line in details]

    def load_swarms(self, swarms: list[Swarm]) -> None:
        """Load swarms into the screen."""
        self._swarms = swarms
        self._selected_index = 0
        self._update_swarm_list()
        self._update_swarm_details()

    def select_next(self) -> None:
        """Select the next swarm."""
        if self._swarms:
            self._selected_index = (self._selected_index + 1) % len(self._swarms)
            self._update_swarm_list()
            self._update_swarm_details()

    def select_previous(self) -> None:
        """Select the previous swarm."""
        if self._swarms:
            self._selected_index = (self._selected_index - 1) % len(self._swarms)
            self._update_swarm_list()
            self._update_swarm_details()

    def get_selected_swarm(self) -> Optional[Swarm]:
        """Get the currently selected swarm."""
        if self._swarms and 0 <= self._selected_index < len(self._swarms):
            return self._swarms[self._selected_index]
        return None

    def _on_create_pressed(self) -> None:
        """Handle create button press."""
        pass

    def _on_delete_pressed(self) -> None:
        """Handle delete button press."""
        pass

    def _on_manage_pressed(self) -> None:
        """Handle manage button press."""
        swarm = self.get_selected_swarm()
        if swarm and self._on_swarm_select:
            self._on_swarm_select(swarm)

    def refresh(self) -> None:
        """Refresh the screen."""
        self._update_swarm_list()
        self._update_swarm_details()


class ThemedChatApp:
    """Main application controller for integrating the screens.

    This class provides the integration point between all screens and
    the pytermgui-based TUI framework.
    """

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        theme_manager: Optional[ThemeManager] = None,
    ) -> None:
        self._client = ollama_client or OllamaClient()
        self._theme_manager = theme_manager

        self._model_screen: Optional[ModelSelectionScreen] = None
        self._agent_screen: Optional[AgentManagementScreen] = None
        self._settings_screen: Optional[SettingsScreen] = None
        self._help_screen: Optional[HelpScreen] = None
        self._swarm_screen: Optional[SwarmManagementScreen] = None

        self._current_view: str = "chat"
        self._models: list[ModelInfo] = []
        self._current_model: str = "llama2"
        self._settings: dict[str, Any] = {}

    @property
    def theme_manager(self) -> ThemeManager:
        """Get the theme manager."""
        if self._theme_manager is None:
            from model_constellation.ui.theme import get_theme_manager

            self._theme_manager = get_theme_manager()
        return self._theme_manager

    def get_model_screen(self) -> ModelSelectionScreen:
        """Get the model selection screen."""
        if self._model_screen is None:
            self._model_screen = ModelSelectionScreen(
                ollama_client=self._client,
                app=self,
                theme_manager=self.theme_manager,
                on_select=self._on_model_selected,
            )
        return self._model_screen

    def get_agent_screen(self) -> AgentManagementScreen:
        """Get the agent management screen."""
        if self._agent_screen is None:
            self._agent_screen = AgentManagementScreen(
                app=self,
                theme_manager=self.theme_manager,
            )
        return self._agent_screen

    def get_settings_screen(self) -> SettingsScreen:
        """Get the settings screen."""
        if self._settings_screen is None:
            self._settings_screen = SettingsScreen(
                app=self,
                theme_manager=self.theme_manager,
            )
        return self._settings_screen

    def get_help_screen(self) -> HelpScreen:
        """Get the help screen."""
        if self._help_screen is None:
            self._help_screen = HelpScreen(
                app=self,
                theme_manager=self.theme_manager,
            )
        return self._help_screen

    def get_swarm_screen(self) -> SwarmManagementScreen:
        """Get the swarm management screen."""
        if self._swarm_screen is None:
            self._swarm_screen = SwarmManagementScreen(
                app=self,
                theme_manager=self.theme_manager,
            )
        return self._swarm_screen

    def _on_model_selected(self, model_name: str) -> None:
        """Handle model selection."""
        self._current_model = model_name

    def _navigate_to(self, view: str) -> None:
        """Navigate to a specific view."""
        self._current_view = view

    def refresh_models(self) -> None:
        """Refresh the model list."""
        self.get_model_screen().load_models()

    def refresh_agents(self) -> None:
        """Refresh the agent list."""
        pass

    def refresh_swarms(self) -> None:
        """Refresh the swarm list."""
        pass


def create_screens(
    ollama_client: Optional[OllamaClient] = None,
    theme_manager: Optional[ThemeManager] = None,
) -> dict[str, BaseScreen]:
    """Create and return all screens.

    Args:
        ollama_client: Optional Ollama client instance.
        theme_manager: Optional theme manager instance.

    Returns:
        Dictionary mapping screen names to screen instances.
    """
    app = ThemedChatApp(ollama_client=ollama_client, theme_manager=theme_manager)

    return {
        "models": app.get_model_screen(),
        "agents": app.get_agent_screen(),
        "settings": app.get_settings_screen(),
        "help": app.get_help_screen(),
        "swarms": app.get_swarm_screen(),
    }
