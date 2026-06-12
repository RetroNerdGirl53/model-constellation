"""Theme system for pytermgui-based TUI."""

import os
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Any
from enum import Enum

import pytermgui
from pytermgui import tim, Color
from pytermgui import Color


class ThemeName(Enum):
    """Built-in theme names."""

    DEFAULT = "default"
    DARK = "dark"
    LIGHT = "light"
    OCEAN = "ocean"
    FOREST = "forest"
    SUNSET = "sunset"
    NEON = "neon"
    MONOKAI = "monokai"


@dataclass
class ThemeColors:
    """Color palette for a theme."""

    background: str = "#1a1a2e"
    foreground: str = "#eaeaea"
    accent: str = "#7b68ee"
    secondary: str = "#4a4a6a"
    success: str = "#50fa7b"
    warning: str = "#ffb86c"
    error: str = "#ff5555"
    user_message: str = "#8be9fd"
    assistant_message: str = "#50fa7b"
    border: str = "#6272a4"
    highlight: str = "#44475a"


@dataclass
class Theme:
    """A complete theme definition."""

    name: str
    display_name: str
    colors: ThemeColors = field(default_factory=ThemeColors)
    is_dark: bool = True
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert theme to dictionary."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "colors": asdict(self.colors),
            "is_dark": self.is_dark,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Theme":
        """Create theme from dictionary."""
        colors = ThemeColors(**data.get("colors", {}))
        return cls(
            name=data["name"],
            display_name=data.get("display_name", data["name"]),
            colors=colors,
            is_dark=data.get("is_dark", True),
            description=data.get("description", ""),
        )


BUILTIN_THEMES: dict[str, Theme] = {
    ThemeName.DEFAULT.value: Theme(
        name="default",
        display_name="Default (Dark Purple)",
        colors=ThemeColors(
            background="#1a1a2e",
            foreground="#eaeaea",
            accent="#7b68ee",
            secondary="#4a4a6a",
            success="#50fa7b",
            warning="#ffb86c",
            error="#ff5555",
            user_message="#8be9fd",
            assistant_message="#50fa7b",
            border="#6272a4",
            highlight="#44475a",
        ),
        is_dark=True,
        description="Default dark theme with purple accents",
    ),
    ThemeName.DARK.value: Theme(
        name="dark",
        display_name="Classic Dark",
        colors=ThemeColors(
            background="#1e1e1e",
            foreground="#d4d4d4",
            accent="#569cd6",
            secondary="#3c3c3c",
            success="#4ec9b0",
            warning="#dcdcaa",
            error="#f14c4c",
            user_message="#9cdcfe",
            assistant_message="#4ec9b0",
            border="#404040",
            highlight="#2d2d2d",
        ),
        is_dark=True,
        description="Classic dark theme inspired by VS Code",
    ),
    ThemeName.LIGHT.value: Theme(
        name="light",
        display_name="Light",
        colors=ThemeColors(
            background="#ffffff",
            foreground="#1e1e1e",
            accent="#0066cc",
            secondary="#e0e0e0",
            success="#22863a",
            warning="#735c0f",
            error="#cb2431",
            user_message="#005cc5",
            assistant_message="#22863a",
            border="#d4d4d4",
            highlight="#f3f3f3",
        ),
        is_dark=False,
        description="Clean light theme",
    ),
    ThemeName.OCEAN.value: Theme(
        name="ocean",
        display_name="Ocean",
        colors=ThemeColors(
            background="#0f172a",
            foreground="#94a3b8",
            accent="#06b6d4",
            secondary="#1e293b",
            success="#22d3ee",
            warning="#fbbf24",
            error="#f87171",
            user_message="#38bdf8",
            assistant_message="#22d3ee",
            border="#334155",
            highlight="#1e293b",
        ),
        is_dark=True,
        description="Deep ocean blue theme",
    ),
    ThemeName.FOREST.value: Theme(
        name="forest",
        display_name="Forest",
        colors=ThemeColors(
            background="#1a2118",
            foreground="#c5d1c2",
            accent="#4ade80",
            secondary="#2a3527",
            success="#22c55e",
            warning="#eab308",
            error="#ef4444",
            user_message="#86efac",
            assistant_message="#22c55e",
            border="#3f4f3a",
            highlight="#2a3527",
        ),
        is_dark=True,
        description="Earthy forest green theme",
    ),
    ThemeName.SUNSET.value: Theme(
        name="sunset",
        display_name="Sunset",
        colors=ThemeColors(
            background="#1f1520",
            foreground="#e8d5c4",
            accent="#f472b6",
            secondary="#3d2a3d",
            success="#a3e635",
            warning="#fb923c",
            error="#fb7185",
            user_message="#fb7185",
            assistant_message="#a3e635",
            border="#5c3d4e",
            highlight="#3d2a3d",
        ),
        is_dark=True,
        description="Warm sunset colors",
    ),
    ThemeName.NEON.value: Theme(
        name="neon",
        display_name="Neon",
        colors=ThemeColors(
            background="#0a0a0f",
            foreground="#f0f0f0",
            accent="#ff00ff",
            secondary="#1a1a2a",
            success="#00ff00",
            warning="#ffff00",
            error="#ff0000",
            user_message="#00ffff",
            assistant_message="#00ff00",
            border="#2a2a4a",
            highlight="#1a1a2a",
        ),
        is_dark=True,
        description="High-contrast neon cyberpunk theme",
    ),
    ThemeName.MONOKAI.value: Theme(
        name="monokai",
        display_name="Monokai",
        colors=ThemeColors(
            background="#272822",
            foreground="#f8f8f2",
            accent="#f92672",
            secondary="#3e3d32",
            success="#a6e22e",
            warning="#e6db74",
            error="#f92672",
            user_message="#66d9ef",
            assistant_message="#a6e22e",
            border="#49483e",
            highlight="#3e3d32",
        ),
        is_dark=True,
        description="Monokai Pro color scheme",
    ),
}


class ThemeManager:
    """Manager for loading and applying themes."""

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        default_theme: str = "default",
    ) -> None:
        self._themes: dict[str, Theme] = {}
        self._current_theme: Optional[Theme] = None
        self._config_dir = config_dir or self._get_default_config_dir()
        self._config_file = self._config_dir / "theme.json"
        self._default_theme = default_theme

        self._load_builtin_themes()
        self._load_saved_theme()

    @staticmethod
    def _get_default_config_dir() -> Path:
        """Get default config directory."""
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", ""))
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / "model_constellation"

    def _load_builtin_themes(self) -> None:
        """Load all built-in themes."""
        self._themes = BUILTIN_THEMES.copy()

    def _load_saved_theme(self) -> None:
        """Load saved theme from config file."""
        if self._config_file.exists():
            try:
                with open(self._config_file, "r") as f:
                    data = json.load(f)
                theme_name = data.get("theme", self._default_theme)
                if theme_name in self._themes:
                    self._current_theme = self._themes[theme_name]
                else:
                    self._current_theme = self._themes.get(
                        self._default_theme, BUILTIN_THEMES["default"]
                    )
            except (json.JSONDecodeError, IOError):
                self._current_theme = self._themes.get(
                    self._default_theme, BUILTIN_THEMES["default"]
                )
        else:
            self._current_theme = self._themes.get(self._default_theme, BUILTIN_THEMES["default"])

    def save_theme(self, theme_name: str) -> bool:
        """Save the current theme to config."""
        if theme_name not in self._themes:
            return False

        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            with open(self._config_file, "w") as f:
                json.dump({"theme": theme_name}, f)
            return True
        except IOError:
            return False

    def get_theme(self, name: str) -> Optional[Theme]:
        """Get a theme by name."""
        return self._themes.get(name)

    def list_themes(self) -> list[Theme]:
        """List all available themes."""
        return list(self._themes.values())

    def set_theme(self, name: str) -> bool:
        """Set the current theme by name."""
        theme = self._themes.get(name)
        if theme is None:
            return False
        self._current_theme = theme
        self.save_theme(name)
        return True

    def get_current_theme(self) -> Optional[Theme]:
        """Get the current theme."""
        return self._current_theme

    def add_custom_theme(self, theme: Theme) -> None:
        """Add a custom theme."""
        self._themes[theme.name] = theme

    def remove_custom_theme(self, name: str) -> bool:
        """Remove a custom theme."""
        if name in BUILTIN_THEMES:
            return False
        if name in self._themes:
            del self._themes[name]
            return True
        return False

    def export_theme(self, name: str, path: Path) -> bool:
        """Export a theme to a file."""
        theme = self._themes.get(name)
        if theme is None:
            return False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(theme.to_dict(), f, indent=2)
            return True
        except IOError:
            return False

    def import_theme(self, path: Path) -> Optional[Theme]:
        """Import a theme from a file."""
        try:
            with open(path, "r") as f:
                data = json.load(f)
            theme = Theme.from_dict(data)
            self.add_custom_theme(theme)
            return theme
        except (json.JSONDecodeError, IOError, KeyError):
            return None

    def apply_theme(self, theme: Optional[Theme] = None) -> None:
        """Apply a theme to pytermgui."""
        target_theme = theme or self._current_theme
        if target_theme is None:
            return

        colors = target_theme.colors

        pytermgui.USE_COLOR = True

        pytermgui.terminal.background = colors.background
        pytermgui.terminal.foreground = colors.foreground

        try:
            pytermgui.palettes.StripedL.PRIMARY = colors.accent
            pytermgui.palettes.StripedL.SECONDARY = colors.secondary
            pytermgui.palettes.StripedL.TERTIARY = colors.highlight
        except AttributeError:
            pass

    def get_color(self, color_name: str) -> str:
        """Get a specific color from the current theme."""
        if self._current_theme is None:
            return ""
        return getattr(self._current_theme.colors, color_name, "")

    def get_colored_text(self, text: str, color_name: str) -> str:
        """Get text with a theme color applied."""
        color = self.get_color(color_name)
        if not color:
            return text
        return f"[{color}]{text}[/]"


class ThemePreview:
    """Theme preview and selection UI."""

    def __init__(self, theme_manager: ThemeManager) -> None:
        self._manager = theme_manager

    def print_preview(self, theme: Optional[Theme] = None) -> None:
        """Print a preview of a theme."""
        target_theme = theme or self._manager.get_current_theme()
        if target_theme is None:
            return

        colors = target_theme.colors
        name = target_theme.display_name

        tim.print(f"\n[bold]{name} Theme Preview[/]\n")
        tim.print(f"  Background: [{colors.background}]▐▐ {colors.background}[/]")
        tim.print(f"  Foreground: [{colors.foreground}]▐▐ {colors.foreground}[/]")
        tim.print(f"  Accent:     [{colors.accent}]▐▐ {colors.accent}[/]")
        tim.print(f"  Secondary:  [{colors.secondary}]▐▐ {colors.secondary}[/]")
        tim.print(f"  Success:   [{colors.success}]▐▐ {colors.success}[/]")
        tim.print(f"  Warning:   [{colors.warning}]▐▐ {colors.warning}[/]")
        tim.print(f"  Error:     [{colors.error}]▐▐ {colors.error}[/]\n")

        tim.print("  [bold]Sample Elements:[/]")
        tim.print(
            f"  [{colors.accent}]Accent text[/] | "
            f"[{colors.success}]Success[/] | "
            f"[{colors.warning}]Warning[/] | "
            f"[{colors.error}]Error[/]"
        )
        tim.print(
            f"  [{colors.user_message}]User: Hello![/] | "
            f"[{colors.assistant_message}]Assistant: Hi![/]"
        )
        tim.print(
            f"  [{colors.border}]╭───╮[{colors.highlight}] Border [/][{colors.border}]│[/] Content []{colors.border}│[/]\n"
        )
        tim.print(f"  [{colors.border}]╰───╯[/]\n")

    def print_all_themes(self) -> None:
        """Print all available themes."""
        themes = self._manager.list_themes()
        current = self._manager.get_current_theme()

        tim.print("\n[bold]Available Themes:[/]\n")

        for i, theme in enumerate(themes, 1):
            is_current = current and theme.name == current.name
            marker = "→" if is_current else " "
            dark_indicator = "🌙" if theme.is_dark else "☀️"

            tim.print(
                f"  {marker} [{theme.colors.accent}]{i}[/] {theme.display_name} {dark_indicator}"
            )
            if theme.description:
                tim.print(f"      [{theme.colors.secondary}]{theme.description}[/]")

        print()

    def select_theme_interactive(self) -> Optional[str]:
        """Interactive theme selection."""
        themes = self._manager.list_themes()
        current = self._manager.get_current_theme()

        self.print_all_themes()

        tim.print("[bold]Enter theme number to preview/select, or 'q' to quit:[/]\n")

        while True:
            choice = input(tim.parse("[cyan]>[/] ")).strip()

            if choice.lower() in ("q", "quit", "exit"):
                return None

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(themes):
                    selected = themes[idx]
                    self.print_preview(selected)

                    confirm = input(tim.parse("[cyan]Apply this theme? (y/n):[/] ")).strip().lower()
                    if confirm in ("y", "yes"):
                        self._manager.set_theme(selected.name)
                        self._manager.apply_theme()
                        return selected.name
                else:
                    tim.print(f"[red]Invalid number. Choose 1-{len(themes)}[/]")
            except ValueError:
                tim.print("[red]Please enter a number[/]")


_global_theme_manager: Optional[ThemeManager] = None


def get_theme_manager(
    config_dir: Optional[Path] = None,
    default_theme: str = "default",
) -> ThemeManager:
    """Get or create the global theme manager."""
    global _global_theme_manager
    if _global_theme_manager is None:
        _global_theme_manager = ThemeManager(config_dir=config_dir, default_theme=default_theme)
    return _global_theme_manager


def init_theme(
    theme_name: str = "default",
    config_dir: Optional[Path] = None,
    apply: bool = True,
) -> ThemeManager:
    """Initialize the theme system."""
    manager = get_theme_manager(config_dir=config_dir, default_theme=theme_name)
    if apply:
        manager.apply_theme()
    return manager


def apply_theme(theme_name: str) -> bool:
    """Apply a theme by name."""
    manager = get_theme_manager()
    if manager.set_theme(theme_name):
        manager.apply_theme()
        return True
    return False


def get_current_theme() -> Optional[Theme]:
    """Get the current theme."""
    manager = get_theme_manager()
    return manager.get_current_theme()


def get_themes() -> list[Theme]:
    """Get all available themes."""
    manager = get_theme_manager()
    return manager.list_themes()
