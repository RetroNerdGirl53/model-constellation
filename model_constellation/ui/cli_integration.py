"""CLI integration for the themed TUI.

This module provides the Click-based CLI commands for launching the themed
terminal user interface.
"""

import sys
import click
from typing import Optional

from model_constellation.ollama_client import OllamaClient, OllamaConnectionError

try:
    from model_constellation.ui.rich_tui import ThemedChatApp, create_app
except ImportError as e:
    ThemedChatApp = None
    create_app = None

try:
    from model_constellation.ui.theme import ThemeManager, get_theme_manager, ThemePreview
except ImportError as e:
    ThemeManager = None
    get_theme_manager = None
    ThemePreview = None


def start_themed_tui(
    theme: Optional[str] = None,
    model: Optional[str] = None,
    no_streaming: bool = False,
    permission_mode: Optional[str] = None,
    base_url: str = "http://localhost:11434",
) -> int:
    """Launch the ThemedChatApp TUI.

    Args:
        theme: Theme name to use (e.g., 'default', 'ocean', 'monokai').
        model: Ollama model to use for chat.
        no_streaming: Disable streaming responses.
        permission_mode: Permission mode (first-time, every-time, allow-all, deny-all).
        base_url: Ollama server URL.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    if get_theme_manager is None or create_app is None:
        click.echo("Error: TUI dependencies not available.", err=True)
        click.echo("Please ensure pytermgui is properly installed.", err=True)
        return 1

    theme_manager = None

    if theme:
        theme_manager = get_theme_manager(default_theme=theme)
        theme_manager.set_theme(theme)
        theme_manager.apply_theme()
    else:
        theme_manager = get_theme_manager()

    client = OllamaClient(base_url=base_url)

    if not client.check_connection():
        click.echo("Error: Cannot connect to Ollama server.", err=True)
        click.echo(f"Make sure Ollama is running at {base_url}", err=True)
        click.echo("You can start Ollama with: 'ollama serve'", err=True)
        return 1

    try:
        app = create_app(
            ollama_client=client,
            theme_manager=theme_manager,
        )

        if model:
            app._current_model = model

        app.run()
        return 0

    except OllamaConnectionError as e:
        click.echo(f"Error: Connection to Ollama failed: {e}", err=True)
        return 1
    except KeyboardInterrupt:
        click.echo("\nGoodbye!")
        return 0
    except Exception as e:
        click.echo(f"Error launching TUI: {e}", err=True)
        return 1


@click.group(name="tui")
def tui_group() -> None:
    """Themed Terminal User Interface commands."""
    pass


@tui_group.command(name="start")
@click.option(
    "--theme",
    "-t",
    type=str,
    help="Theme to use (default, dark, light, ocean, forest, sunset, neon, monokai)",
)
@click.option(
    "--model",
    "-m",
    type=str,
    help="Ollama model to use for chat",
)
@click.option(
    "--no-streaming",
    is_flag=True,
    help="Disable streaming responses",
)
@click.option(
    "--permission-mode",
    "-p",
    type=click.Choice(
        ["first-time", "every-time", "allow-all", "deny-all"],
        case_sensitive=False,
    ),
    help="Permission mode for tool execution",
)
@click.option(
    "--base-url",
    type=str,
    default="http://localhost:11434",
    help="Ollama server URL (default: http://localhost:11434)",
)
def tui_start(
    theme: Optional[str],
    model: Optional[str],
    no_streaming: bool,
    permission_mode: Optional[str],
    base_url: str,
) -> None:
    """Start the themed TUI chat interface."""
    available_themes = ["default", "dark", "light", "ocean", "forest", "sunset", "neon", "monokai"]

    if theme and theme not in available_themes:
        click.echo(f"Error: Unknown theme '{theme}'", err=True)
        click.echo(f"Available themes: {', '.join(available_themes)}", err=True)
        sys.exit(1)

    if model:
        client = OllamaClient(base_url=base_url)
        try:
            available_models = [m.name for m in client.list_models()]
            if model not in available_models:
                click.echo(f"Warning: Model '{model}' not found in available models.", err=True)
                click.echo(f"Available models: {', '.join(available_models)}", err=True)
        except OllamaConnectionError:
            pass

    exit_code = start_themed_tui(
        theme=theme,
        model=model,
        no_streaming=no_streaming,
        permission_mode=permission_mode,
        base_url=base_url,
    )
    sys.exit(exit_code)


@tui_group.command(name="themes")
def tui_themes() -> None:
    """List available themes."""
    if get_theme_manager is None or ThemePreview is None:
        click.echo("Error: TUI dependencies not available.", err=True)
        click.echo("Please ensure pytermgui is properly installed.", err=True)
        sys.exit(1)
    theme_manager = get_theme_manager()
    preview = ThemePreview(theme_manager)
    preview.print_all_themes()


@tui_group.command(name="preview")
@click.argument("theme_name")
def tui_preview(theme_name: str) -> None:
    """Preview a specific theme."""
    if get_theme_manager is None or ThemePreview is None:
        click.echo("Error: TUI dependencies not available.", err=True)
        click.echo("Please ensure pytermgui is properly installed.", err=True)
        sys.exit(1)
    theme_manager = get_theme_manager()
    theme = theme_manager.get_theme(theme_name)

    if theme is None:
        available = [t.name for t in theme_manager.list_themes()]
        click.echo(f"Error: Theme '{theme_name}' not found", err=True)
        click.echo(f"Available: {', '.join(available)}", err=True)
        sys.exit(1)

    preview = ThemePreview(theme_manager)
    preview.print_preview(theme)


@tui_group.command(name="set-theme")
@click.argument("theme_name")
def tui_set_theme(theme_name: str) -> None:
    """Set the default theme."""
    if get_theme_manager is None:
        click.echo("Error: TUI dependencies not available.", err=True)
        click.echo("Please ensure pytermgui is properly installed.", err=True)
        sys.exit(1)
    theme_manager = get_theme_manager()

    if not theme_manager.set_theme(theme_name):
        available = [t.name for t in theme_manager.list_themes()]
        click.echo(f"Error: Theme '{theme_name}' not found", err=True)
        click.echo(f"Available: {', '.join(available)}", err=True)
        sys.exit(1)

    theme_manager.apply_theme()
    current = theme_manager.get_current_theme()
    if current:
        click.echo(f"Theme set to: {current.display_name}")
    else:
        click.echo(f"Theme set to: {theme_name}")


def get_tui_command_group() -> click.Group:
    """Get the TUI command group for integration with main CLI."""
    return tui_group
