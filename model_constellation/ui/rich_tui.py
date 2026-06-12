"""Simplified Rich Terminal User Interface using pytermgui.

This module provides a simplified TUI for chatting with Ollama models.
"""

import asyncio
import logging
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from model_constellation.ollama_client import OllamaClient, OllamaConnectionError
from model_constellation.ui.theme import ThemeManager, get_theme_manager

logger = logging.getLogger(__name__)


@dataclass
class ChatMessageData:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


class SimplifiedTUI:
    """Simplified TUI application."""

    WELCOME_BANNER = """
 ██████╗ ███████╗██╗      █████╗ ██████╗ ██████╗  █████╗ ██████╗  ██████╗ █████╗ ██████╗ ███████╗
 ██╔══██╗██╔════╝██║     ██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔════╝
 ██████╔╝█████╗  ██║     ███████║██████╔╝██║  ██║███████║██████╔╝██║     ███████║██████╔╝█████╗  
 ██╔══██╗██╔══╝  ██║     ██╔══██║██╔══██╗██║  ██║██╔══██║██╔══██╗██║     ██╔══██║██╔══██╗██╔══╝  
 ██║  ██║███████╗███████╗██║  ██║██║  ██║██████╔╝██║  ██║██║  ██║╚██████╗██║  ██║██║  ██║███████╗
 ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝
"""

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        theme_manager: Optional[ThemeManager] = None,
    ):
        self._client = ollama_client or OllamaClient()
        self._theme_manager = theme_manager or get_theme_manager()
        self._theme_manager.apply_theme()

        self._theme_index = 0
        self._themes = self._theme_manager.list_themes()
        self._current_model = "llama2"
        self._messages: list[ChatMessageData] = []
        self._running = True

        # State object for cli_integration compatibility
        @dataclass
        class TUIState:
            current_model: str = "llama2"

        self._state = TUIState()
        self._state.current_model = self._current_model

        pass

    def _get_color(self, color_name: str) -> str:
        try:
            return self._theme_manager.get_color(color_name)
        except Exception:
            return "white"

    def _get_theme(self):
        try:
            return self._theme_manager.get_current_theme()
        except Exception:
            return None

    def _cycle_theme(self) -> None:
        if self._themes:
            self._theme_index = (self._theme_index + 1) % len(self._themes)
            theme_name = self._themes[self._theme_index].name
            self._theme_manager.set_theme(theme_name)
            self._theme_manager.apply_theme()

    def _show_welcome(self) -> None:
        theme = self._get_theme()
        fg = self._get_color("foreground")
        accent = self._get_color("accent")
        secondary = self._get_color("secondary")

        print("\n" + self.WELCOME_BANNER)
        print("\n[{0} bold]Welcome to model-constellation[/{0} bold]".format(accent))
        print("[{0}]Your AI Assistant".format(secondary))
        print("\n[{0}]Press Enter to start chatting".format(fg))
        print("[{0}]or type 'help' for commands".format(secondary))
        print()

    def _show_chat(self) -> None:
        theme = self._get_theme()
        fg = self._get_color("foreground")
        accent = self._get_color("accent")
        secondary = self._get_color("secondary")

        print("\n[{0} bold]=== Chat ===[/{0} bold]".format(accent))
        print("[{0}]Model: {1}[/{0}]".format(secondary, self._current_model))
        theme_name = self._themes[self._theme_index].display_name if self._themes else "default"
        print("[{0}]Theme: {1}[/{0}]".format(secondary, theme_name))
        print("[{0}]Type 'q' or 'quit' to exit[/{0}]".format(secondary))
        print("[{0}]Type 'theme' to cycle themes[/{0}]".format(secondary))
        print("[{0}]Type 'clear' to clear chat[/{0}]".format(secondary))
        print()

        for msg in self._messages:
            msg_color = (
                self._get_color("user_message")
                if msg.role == "user"
                else self._get_color("assistant_message")
            )
            role_label = "You" if msg.role == "user" else "Assistant"
            ts = msg.timestamp.strftime("%H:%M")
            print(
                "[{0}][{1}][/{0}] [{2}]{3}:[/{2}] {4}".format(
                    secondary, ts, msg_color, role_label, msg.content
                )
            )

    def _show_help(self) -> None:
        accent = self._get_color("accent")
        fg = self._get_color("foreground")
        secondary = self._get_color("secondary")

        help_text = """
[{0} bold}}=== Help ===[/{0} bold}}
[{1}]Commands:[/{1}]
  - Type a message and press Enter to chat
  - q, quit        - Exit the application
  - help           - Show this help message
  - theme          - Cycle through themes
  - clear          - Clear chat history
  - models         - List available models
  - model <name>   - Switch to a different model

[{2}]Press Ctrl+C to quit anytime[/{2}]
""".format(accent, fg, secondary)
        print(help_text)

    def _load_models(self) -> list[str]:
        try:
            models = self._client.list_models()
            return [m.name for m in models]
        except OllamaConnectionError:
            print(f"[red]Failed to connect to Ollama[red]")
            return [self._current_model]
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            return [self._current_model]

    def _add_message(self, role: str, content: str) -> None:
        self._messages.append(ChatMessageData(role=role, content=content))

    def _clear_chat(self) -> None:
        self._messages = []

    def _send_message(self, message: str) -> None:
        self._add_message("user", message)

        thinking = ChatMessageData(role="assistant", content="Thinking...")
        self._messages.append(thinking)

        def get_response():
            try:
                msgs = [{"role": m.role, "content": m.content} for m in self._messages[:-1]]
                response = self._client.chat(
                    model=self._current_model,
                    messages=msgs,
                    stream=False,
                )
                if response and response.message:
                    self._messages[-1].content = response.message.content
            except Exception as e:
                logger.error(f"Chat error: {e}")
                self._messages[-1].content = f"Error: {str(e)}"

        thread = threading.Thread(target=get_response, daemon=True)
        thread.start()
        thread.join(timeout=60)

    def _get_input(self) -> Optional[str]:
        theme = self._get_theme()
        accent = self._get_color("accent")

        try:
            prompt = f"[{accent}]>[/] "
            print(prompt, end="")
            return input()
        except (EOFError, KeyboardInterrupt):
            return None

    def run(self) -> None:
        self._show_welcome()

        while self._running:
            try:
                self._show_chat()

                try:
                    prompt = f"[{self._get_color('accent')}]>[/] "
                    print(prompt, end="")
                    message = input()
                except (EOFError, KeyboardInterrupt):
                    break

                if not message:
                    continue

                message = message.strip()

                if message.lower() in ("q", "quit", "exit"):
                    break
                elif message.lower() == "help":
                    self._show_help()
                elif message.lower() == "theme":
                    self._cycle_theme()
                    print(f"[green]Theme changed![/green]")
                elif message.lower() == "clear":
                    self._clear_chat()
                    print("[green]Chat cleared![/green]")
                elif message.lower() == "models":
                    models = self._load_models()
                    accent = self._get_color("accent")
                    print("\n[{0} bold}}Available Models:[/{0} bold}}]".format(accent))
                    for m in models:
                        marker = "→" if m == self._current_model else " "
                        print(f"  {marker} {m}")
                    print()
                elif message.lower().startswith("model "):
                    new_model = message[6:].strip()
                    self._current_model = new_model
                    print(f"[green]Switched to model: {new_model}[/green]")
                else:
                    self._send_message(message)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error: {e}")

        print("\n[yellow]Goodbye![/]")


def create_app(
    ollama_client: Optional[OllamaClient] = None,
    theme_manager: Optional[ThemeManager] = None,
) -> SimplifiedTUI:
    """Create and return a SimplifiedTUI instance."""
    return SimplifiedTUI(ollama_client=ollama_client, theme_manager=theme_manager)


ThemedChatApp = SimplifiedTUI


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    app.run()
