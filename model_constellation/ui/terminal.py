"""Terminal UI manager for model-constellation."""

import asyncio
import sys
from typing import Any, Callable, Optional
from dataclasses import dataclass, field

import pytermgui
from pytermgui import tim

from model_constellation.models import Agent, Message, Swarm, PermissionMode, ModelParameters, OllamaConfig
from model_constellation.ui.screens import (
    ChatScreen,
    AgentSelectionScreen,
    ModelSelectionScreen,
    SettingsScreen,
    HelpScreen,
    SwarmScreen,
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
    PermissionDialog,
    ModelSelectionDialog,
    AgentSelectionDialog,
    SettingsDialog,
)
from model_constellation.ui.widgets import (
    MessageBubble,
    AgentStatusIndicator,
    ModelInfoDisplay,
    ToolCallDisplay,
    StatusBar,
    HeaderWidget,
)


@dataclass
class TUIConfig:
    """Configuration for the Terminal UI."""

    theme: str = "default"
    color: bool = True
    show_tokens: bool = False
    streaming: bool = True
    confirm_quit: bool = True


class TerminalUI:
    """Main Terminal UI manager for model-constellation."""

    def __init__(
        self,
        config: Optional[TUIConfig] = None,
        ollama_config: Optional[OllamaConfig] = None,
    ) -> None:
        self.config = config or TUIConfig()
        self.ollama_config = ollama_config or OllamaConfig()

        self._current_screen: str = "chat"
        self._screens: dict[str, Any] = {}
        self._callbacks: dict[str, Callable] = {}

        self._chat_screen = ChatScreen(
            model=self.ollama_config.default_model,
            show_tokens=self.config.show_tokens,
        )
        self._agent_screen = AgentSelectionScreen()
        self._model_screen = ModelSelectionScreen()
        self._settings_screen = SettingsScreen()
        self._help_screen = HelpScreen()
        self._swarm_screen = SwarmScreen()

        self._is_running = False

    def initialize(self) -> None:
        """Initialize the UI."""
        self._setup_theme()
        self._setup_screens()
        self._is_running = True

    def _setup_theme(self) -> None:
        """Set up the UI theme and color scheme."""
        if not self.config.color:
            pytermgui.USE_COLOR = False
        else:
            pytermgui.USE_COLOR = True

    def _setup_screens(self) -> None:
        """Set up all screens."""
        self._screens = {
            "chat": self._chat_screen,
            "agents": self._agent_screen,
            "models": self._model_screen,
            "settings": self._settings_screen,
            "help": self._help_screen,
            "swarms": self._swarm_screen,
        }

    def run(self) -> None:
        """Run the TUI main loop."""
        self.initialize()

        try:
            while self._is_running:
                self._process_input()
        except KeyboardInterrupt:
            self.handle_quit()

    def _process_input(self) -> None:
        """Process user input."""
        pass

    def handle_quit(self) -> None:
        """Handle application quit."""
        if self.config.confirm_quit:
            response = input("Are you sure you want to quit? (y/n): ").strip().lower()
            if response not in ("y", "yes"):
                return
        self._is_running = False

    def stop(self) -> None:
        """Stop the TUI."""
        self._is_running = False

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the chat."""
        message = Message(
            id=kwargs.get("id", ""),
            role=role,
            content=content,
            tool_calls=kwargs.get("tool_calls"),
            tool_result=kwargs.get("tool_result"),
            metadata=kwargs.get("metadata", {}),
        )
        self._chat_screen.add_message(message)

    def add_user_message(self, content: str) -> None:
        """Add a user message to the chat."""
        self.add_message(role="user", content=content)

    def add_assistant_message(self, content: str, **kwargs: Any) -> None:
        """Add an assistant message to the chat."""
        self.add_message(role="assistant", content=content, **kwargs)

    def update_agent_list(self, agents: list[Agent]) -> None:
        """Update the agent list."""
        self._agent_screen.agents = agents

    def update_model_list(self, models: list[str], current: Optional[str] = None) -> None:
        """Update the model list."""
        self._model_screen.models = models
        if current:
            self._model_screen.current_model = current

    def update_swarm_list(self, swarms: list[Swarm]) -> None:
        """Update the swarm list."""
        self._swarm_screen.swarms = swarms

    def update_settings(self, settings: dict[str, Any]) -> None:
        """Update settings."""
        self._settings_screen.settings = settings

    def switch_screen(self, screen_name: str) -> None:
        """Switch to a different screen."""
        if screen_name in self._screens:
            self._current_screen = screen_name

    def show_chat(self) -> None:
        """Show chat screen."""
        self.switch_screen("chat")

    def show_agents(self) -> None:
        """Show agent selection screen."""
        self.switch_screen("agents")

    def show_models(self) -> None:
        """Show model selection screen."""
        self.switch_screen("models")

    def show_settings(self) -> None:
        """Show settings screen."""
        self.switch_screen("settings")

    def show_help(self) -> None:
        """Show help screen."""
        self.switch_screen("help")

    def show_swarms(self) -> None:
        """Show swarm management screen."""
        self.switch_screen("swarms")

    def get_current_screen(self) -> str:
        """Get current screen name."""
        return self._current_screen

    def request_permission(
        self,
        tool_name: str,
        command: str,
        description: str,
        risk_level: str = "medium",
        callback: Optional[Callable[[bool, bool], None]] = None,
    ) -> bool:
        """Request permission for tool execution."""
        dialog = PermissionDialog(
            tool_name=tool_name,
            command=command,
            description=description,
            risk_level=risk_level,
            callback=callback,
        )
        result = dialog.show()
        dialog.close()
        return result[0] if result else False

    def show_confirmation(
        self,
        title: str,
        message: str,
        callback: Optional[Callable[[bool], None]] = None,
    ) -> None:
        """Show a confirmation dialog."""
        dialog = ConfirmationDialog(
            title=title,
            message=message,
            callback=callback,
        )
        dialog.show()

    def show_input(
        self,
        title: str,
        prompt: str,
        default_value: str = "",
        callback: Optional[Callable[[Optional[str]], None]] = None,
    ) -> None:
        """Show an input dialog."""
        dialog = InputDialog(
            title=title,
            prompt=prompt,
            default_value=default_value,
            callback=callback,
        )
        dialog.show()

    def show_selection(
        self,
        title: str,
        message: str,
        options: list[str],
        callback: Optional[Callable[[Optional[int]], None]] = None,
    ) -> None:
        """Show a selection dialog."""
        dialog = SelectionDialog(
            title=title,
            message=message,
            options=options,
            callback=callback,
        )
        dialog.show()

    def show_model_selection(
        self,
        models: list[str],
        current: str,
        callback: Optional[Callable[[Optional[str]], None]] = None,
    ) -> None:
        """Show model selection dialog."""
        dialog = ModelSelectionDialog(
            models=models,
            current_model=current,
            callback=callback,
        )
        dialog.show()

    def show_agent_selection(
        self,
        agents: list[tuple[str, str]],
        callback: Optional[Callable[[Optional[str]], None]] = None,
    ) -> None:
        """Show agent selection dialog."""
        dialog = AgentSelectionDialog(
            agents=agents,
            callback=callback,
        )
        dialog.show()

    def show_settings_dialog(
        self,
        settings: dict[str, Any],
        callback: Optional[Callable[[Optional[dict[str, Any]]], None]] = None,
    ) -> None:
        """Show settings dialog."""
        dialog = SettingsDialog(
            settings=settings,
            callback=callback,
        )
        dialog.show()

    def register_callback(self, event: str, callback: Callable) -> None:
        """Register a callback for an event."""
        self._callbacks[event] = callback

    def trigger_callback(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Trigger a callback."""
        if event in self._callbacks:
            self._callbacks[event](*args, **kwargs)

    def print(self, message: str, style: Optional[str] = None) -> None:
        """Print a message to the terminal."""
        if style:
            tim.print(message)
        else:
            print(message)

    def print_error(self, message: str) -> None:
        """Print an error message."""
        tim.print(f"[red]Error:[/] {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        tim.print(f"[yellow]Warning:[/] {message}")

    def print_success(self, message: str) -> None:
        """Print a success message."""
        tim.print(f"[green]Success:[/] {message}")

    def print_info(self, message: str) -> None:
        """Print an info message."""
        tim.print(f"[cyan]Info:[/] {message}")

    def clear_screen(self) -> None:
        """Clear the terminal screen."""
        print("\033[2J\033[H", end="")

    def set_status(self, message: str) -> None:
        """Set the status bar message."""
        pass

    @property
    def chat_screen(self) -> ChatScreen:
        """Get the chat screen."""
        return self._chat_screen

    @property
    def agent_screen(self) -> AgentSelectionScreen:
        """Get the agent selection screen."""
        return self._agent_screen

    @property
    def model_screen(self) -> ModelSelectionScreen:
        """Get the model selection screen."""
        return self._model_screen

    @property
    def settings_screen(self) -> SettingsScreen:
        """Get the settings screen."""
        return self._settings_screen

    @property
    def help_screen(self) -> HelpScreen:
        """Get the help screen."""
        return self._help_screen

    @property
    def swarm_screen(self) -> SwarmScreen:
        """Get the swarm screen."""
        return self._swarm_screen


class InteractiveChat:
    """Interactive chat interface for model-constellation."""

    def __init__(self, terminal: TerminalUI) -> None:
        self.terminal = terminal
        self._running = False

    def start(self) -> None:
        """Start the interactive chat."""
        self._running = True

        self._print_welcome()
        self._main_loop()

    def _print_welcome(self) -> None:
        """Print welcome message."""
        tim.print("""
[bold cyan]╔══════════════════════════════════════════╗
║     🤖 Welcome to model-constellation Chat!                  ║
║     Ollama-powered AI Agent Framework        ║
╚══════════════════════════════════════════╝[/]

Type your message and press Enter to send.
Commands:
  /help   - Show keyboard shortcuts
  /clear  - Clear chat history
  /model  - Switch model
  /quit   - Exit

""")

    def _main_loop(self) -> None:
        """Main chat loop."""
        while self._running:
            try:
                user_input = input(tim.parse("[cyan]>[/] ")).strip()

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    self._handle_command(user_input)
                else:
                    self._handle_message(user_input)

            except KeyboardInterrupt:
                tim.print("\n[yellow]Use /quit to exit[/]")
            except EOFError:
                break

        self._print_goodbye()

    def _handle_command(self, command: str) -> None:
        """Handle a command."""
        cmd = command.lower().split()[0]

        if cmd == "/help":
            self._print_help()
        elif cmd == "/clear":
            self.terminal.chat_screen.messages.clear()
            self.terminal.clear_screen()
        elif cmd == "/quit" or cmd == "/exit":
            self._running = False
        elif cmd == "/model":
            self._handle_model_command(command)
        elif cmd == "/agent":
            self._handle_agent_command(command)
        else:
            self.terminal.print_warning(f"Unknown command: {cmd}")

    def _handle_message(self, message: str) -> None:
        """Handle a chat message."""
        self.terminal.add_user_message(message)
        self.trigger_callback("message", message)

    def _handle_model_command(self, command: str) -> None:
        """Handle model command."""
        parts = command.split(maxsplit=1)
        if len(parts) > 1:
            model = parts[1]
            self.terminal._chat_screen.model = model
            self.terminal.print_info(f"Switched to model: {model}")
        else:
            self.terminal.print_info("Available models: llama2, codellama, mistral, etc.")

    def _handle_agent_command(self, command: str) -> None:
        """Handle agent command."""
        parts = command.split(maxsplit=1)
        if len(parts) > 1:
            agent_name = parts[1]
            self.terminal._chat_screen.agent_name = agent_name
            self.terminal.print_info(f"Switched to agent: {agent_name}")
        else:
            self.terminal.print_info("Available agents: primary, code, research, etc.")

    def _print_help(self) -> None:
        """Print help information."""
        tim.print("""
[bold]Keyboard Shortcuts:[/]
  /help   - Show this help
  /clear  - Clear chat history  
  /model  - Switch model (use: /model <name>)
  /agent  - Switch agent (use: /agent <name>)
  /quit   - Exit the chat

[bold]Chat:[/]
  Type your message and press Enter to send.
  Messages are processed by the AI agent.
""")

    def _print_goodbye(self) -> None:
        """Print goodbye message."""
        tim.print("\n[bold cyan]Goodbye! 👋[/]\n")

    def stop(self) -> None:
        """Stop the chat."""
        self._running = False

    def trigger_callback(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Trigger a callback."""
        self.terminal.trigger_callback(event, *args, **kwargs)


def create_terminal_ui(
    config: Optional[TUIConfig] = None,
    ollama_config: Optional[OllamaConfig] = None,
) -> TerminalUI:
    """Create a TerminalUI instance."""
    return TerminalUI(config=config, ollama_config=ollama_config)


def start_interactive_chat(
    terminal: Optional[TerminalUI] = None,
    config: Optional[TUIConfig] = None,
    ollama_config: Optional[OllamaConfig] = None,
) -> None:
    """Start an interactive chat session."""
    if terminal is None:
        terminal = create_terminal_ui(config=config, ollama_config=ollama_config)

    chat = InteractiveChat(terminal)
    chat.start()
