"""model-constellation UI package — themed terminal interface.

The active TUI is launched via :func:`start_themed_tui` (used by the ``tui`` CLI
command), which runs the chat app in :mod:`model_constellation.ui.rich_tui` with
themes from :mod:`model_constellation.ui.theme`.

Usage:
    from model_constellation.ui import start_themed_tui
    start_themed_tui(theme="ocean")
"""

from model_constellation.ui.theme import (
    ThemeManager,
    get_themes,
    get_current_theme,
    apply_theme,
    init_theme,
    ThemePreview,
)
from model_constellation.ui.rich_tui import ThemedChatApp
from model_constellation.ui.cli_integration import start_themed_tui

__all__ = [
    # Theme
    "ThemeManager",
    "get_themes",
    "get_current_theme",
    "apply_theme",
    "init_theme",
    "ThemePreview",
    # Chat app
    "ThemedChatApp",
    # CLI integration
    "start_themed_tui",
]

__version__ = "1.1.0"
