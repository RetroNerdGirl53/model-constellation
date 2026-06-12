"""model-constellation UI Package - Terminal User Interface for model-constellation.

This package provides the TUI (Terminal User Interface) components for the model-constellation
Ollama-powered AI agent CLI framework.

Modules:
    widgets: Custom widget components for displaying messages, agents, models, etc.
    dialogs: Dialog components for user interactions (confirmations, inputs, selections)
    screens: Main UI screens (chat, agent selection, model selection, settings, help)
    terminal: Terminal UI manager for initializing and running the TUI

Usage:
    from model_constellation.ui import TerminalUI, create_terminal_ui, start_interactive_chat

    # Create and configure the terminal UI
    terminal = create_terminal_ui()

    # Or start an interactive chat session directly
    start_interactive_chat()

Key Features:
    - Interactive message history with rich formatting
    - Agent/swarm status display
    - Real-time permission requests
    - Model selection
    - Custom widgets for messages, agents, and tools
    - Keyboard navigation support
"""

from model_constellation.ui.terminal import (
    TerminalUI,
    TUIConfig,
    InteractiveChat,
    create_terminal_ui,
    start_interactive_chat,
)
from model_constellation.ui.screens import (
    ChatScreen,
    AgentSelectionScreen,
    ModelSelectionScreen,
    SettingsScreen,
    HelpScreen,
    SwarmScreen,
    Screen,
    build_chat_display,
    build_agent_list_display,
    build_model_list_display,
    build_settings_display,
    build_help_display,
)
from model_constellation.ui.dialogs import (
    ConfirmationDialog,
    InputDialog,
    SelectionDialog,
    ProgressDialog,
    PermissionDialog,
    ModelSelectionDialog,
    AgentSelectionDialog,
    SettingsDialog,
    DialogResult,
)
from model_constellation.ui.widgets import (
    MessageBubble,
    AgentStatusIndicator,
    AgentListWidget,
    ModelInfoDisplay,
    ToolCallDisplay,
    SwarmStatusWidget,
    PermissionRequestDialog,
    ProgressIndicator,
    TokenCountDisplay,
    HeaderWidget,
    StatusBar,
)
from model_constellation.ui.theme import (
    ThemeManager,
    get_themes,
    get_current_theme,
    apply_theme,
    init_theme,
    ThemePreview,
)
from model_constellation.ui.rich_tui import ThemedChatApp
from model_constellation.ui.screens_v2 import (
    ModelSelectionScreen,
    AgentManagementScreen,
    SettingsScreen,
    HelpScreen,
    SwarmManagementScreen,
    create_screens,
)
from model_constellation.ui.cli_integration import start_themed_tui

__all__ = [
    # Terminal UI
    "TerminalUI",
    "TUIConfig",
    "InteractiveChat",
    "create_terminal_ui",
    "start_interactive_chat",
    # Screens
    "ChatScreen",
    "AgentSelectionScreen",
    "ModelSelectionScreen",
    "SettingsScreen",
    "HelpScreen",
    "SwarmScreen",
    "Screen",
    "build_chat_display",
    "build_agent_list_display",
    "build_model_list_display",
    "build_settings_display",
    "build_help_display",
    # Dialogs
    "ConfirmationDialog",
    "InputDialog",
    "SelectionDialog",
    "ProgressDialog",
    "PermissionDialog",
    "ModelSelectionDialog",
    "AgentSelectionDialog",
    "SettingsDialog",
    "DialogResult",
    # Widgets
    "MessageBubble",
    "AgentStatusIndicator",
    "AgentListWidget",
    "ModelInfoDisplay",
    "ToolCallDisplay",
    "SwarmStatusWidget",
    "PermissionRequestDialog",
    "ProgressIndicator",
    "TokenCountDisplay",
    "HeaderWidget",
    "StatusBar",
    # Theme
    "ThemeManager",
    "get_themes",
    "get_current_theme",
    "apply_theme",
    "init_theme",
    "ThemePreview",
    # Rich TUI
    "ThemedChatApp",
    # Screens V2
    "ModelSelectionScreen",
    "AgentManagementScreen",
    "SettingsScreen",
    "HelpScreen",
    "SwarmManagementScreen",
    "create_screens",
    # CLI Integration
    "start_themed_tui",
]

__version__ = "1.0.0"
