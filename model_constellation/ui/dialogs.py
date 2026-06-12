"""Dialog components for model-constellation TUI."""

from typing import Any, Callable, Optional
from dataclasses import dataclass


@dataclass
class DialogResult:
    """Result from a dialog interaction."""

    confirmed: bool
    value: Any = None


class ConfirmationDialog:
    """Confirmation dialog with Yes/No options."""

    def __init__(
        self,
        title: str,
        message: str,
        *,
        confirm_label: str = "Yes",
        cancel_label: str = "No",
        callback: Optional[Callable[[bool], None]] = None,
    ) -> None:
        self.callback = callback
        self.title = title
        self.message = message
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label
        self.result: Optional[bool] = None

    def show(self) -> Optional[bool]:
        """Show the dialog and return result."""
        print(f"\n[{self.title}]")
        print(self.message)
        print(f"[{self.confirm_label}] / [{self.cancel_label}]")

        while True:
            response = input("> ").strip().lower()
            if response in ("y", "yes", self.confirm_label.lower()):
                self.result = True
                if self.callback:
                    self.callback(True)
                return True
            elif response in ("n", "no", self.cancel_label.lower()):
                self.result = False
                if self.callback:
                    self.callback(False)
                return False

    def close(self) -> None:
        """Close the dialog."""
        pass


class InputDialog:
    """Input dialog for getting user text input."""

    def __init__(
        self,
        title: str,
        prompt: str,
        *,
        default_value: str = "",
        callback: Optional[Callable[[Optional[str]], None]] = None,
    ) -> None:
        self.callback = callback
        self.title = title
        self.prompt = prompt
        self.default_value = default_value
        self.result: Optional[str] = None

    def show(self) -> Optional[str]:
        """Show the dialog and return result."""
        print(f"\n[{self.title}]")
        response = input(f"{self.prompt} [{self.default_value}]: ").strip()

        if not response:
            response = self.default_value

        self.result = response
        if self.callback:
            self.callback(response)
        return response

    def close(self) -> None:
        """Close the dialog."""
        pass


class SelectionDialog:
    """Dialog for selecting from a list of options."""

    def __init__(
        self,
        title: str,
        message: str,
        options: list[str],
        *,
        callback: Optional[Callable[[Optional[int]], None]] = None,
    ) -> None:
        self.callback = callback
        self.title = title
        self.message = message
        self.options = options
        self.result: Optional[int] = None

    def show(self) -> Optional[int]:
        """Show the dialog and return result."""
        print(f"\n[{self.title}]")
        print(self.message)
        print()

        for i, option in enumerate(self.options):
            print(f"  {i + 1}. {option}")
        print()

        while True:
            try:
                response = input("Select option number: ").strip()
                idx = int(response) - 1
                if 0 <= idx < len(self.options):
                    self.result = idx
                    if self.callback:
                        self.callback(idx)
                    return idx
            except ValueError:
                pass
            print("Invalid option. Please try again.")

    def close(self) -> None:
        """Close the dialog."""
        pass


class ProgressDialog:
    """Dialog showing progress of an operation."""

    def __init__(
        self,
        title: str,
        message: str,
        *,
        total: int = 100,
    ) -> None:
        self.title = title
        self.message = message
        self.total = total
        self.current = 0

    def update(self, current: int, message: Optional[str] = None) -> None:
        """Update progress."""
        self.current = current
        if message:
            self.message = message

        percentage = (self.current / self.total) * 100 if self.total > 0 else 0
        bar_width = 30
        filled = int(bar_width * percentage / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        print(f"\r[{self.title}] {bar} {percentage:.1f}%", end="", flush=True)


class PermissionDialog:
    """Dialog for requesting tool execution permission."""

    def __init__(
        self,
        tool_name: str,
        command: str,
        description: str,
        *,
        risk_level: str = "medium",
        callback: Optional[Callable[[bool, bool], None]] = None,
    ) -> None:
        self.callback = callback
        self.tool_name = tool_name
        self.command = command
        self.description = description
        self.risk_level = risk_level
        self.result: tuple[bool, bool] = (False, False)

    def show(self) -> tuple[bool, bool]:
        """Show the dialog and return result."""
        risk_icons = {
            "low": "✓",
            "medium": "⚠",
            "high": "⚠⚠",
            "critical": "⛔",
        }

        icon = risk_icons.get(self.risk_level, "?")

        print(f"\n{icon} Tool Execution Request")
        print("-" * 40)
        print(f"Tool: {self.tool_name}")
        print(f"Command: {self.command}")
        print(f"\nThis tool will: {self.description}")
        print()
        print("[A]llow  [D]eny  [S] Allow All Session")

        while True:
            response = input("> ").strip().lower()
            if response in ("a", "allow"):
                self.result = (True, False)
                if self.callback:
                    self.callback(True, False)
                return self.result
            elif response in ("d", "deny"):
                self.result = (False, False)
                if self.callback:
                    self.callback(False, False)
                return self.result
            elif response in ("s", "allow all session"):
                self.result = (True, True)
                if self.callback:
                    self.callback(True, True)
                return self.result

    def close(self) -> None:
        """Close the dialog."""
        pass


class ModelSelectionDialog:
    """Dialog for selecting an Ollama model."""

    def __init__(
        self,
        models: list[str],
        current_model: str,
        *,
        callback: Optional[Callable[[Optional[str]], None]] = None,
    ) -> None:
        self.callback = callback
        self.models = models
        self.current_model = current_model
        self.result: Optional[str] = None

    def show(self) -> Optional[str]:
        """Show the dialog and return result."""
        print("\nSelect Model")
        print("-" * 40)
        print("Available Models:")

        for model in self.models:
            is_current = " (current)" if model == self.current_model else ""
            print(f"  {model}{is_current}")

        print()

        while True:
            response = input("Select model: ").strip()
            if response in self.models:
                self.result = response
                if self.callback:
                    self.callback(response)
                return response
            print("Invalid model. Please try again.")

    def close(self) -> None:
        """Close the dialog."""
        pass


class AgentSelectionDialog:
    """Dialog for selecting an agent."""

    def __init__(
        self,
        agents: list[tuple[str, str]],
        *,
        callback: Optional[Callable[[Optional[str]], None]] = None,
    ) -> None:
        self.callback = callback
        self.agents = agents
        self.result: Optional[str] = None

    def show(self) -> Optional[str]:
        """Show the dialog and return result."""
        print("\nSelect Agent")
        print("-" * 40)
        print("Available Agents:")

        for agent_id, agent_name in self.agents:
            print(f"  {agent_name} ({agent_id})")

        print()

        while True:
            response = input("Select agent: ").strip()
            for agent_id, agent_name in self.agents:
                if response == agent_name or response == agent_id:
                    self.result = agent_id
                    if self.callback:
                        self.callback(agent_id)
                    return agent_id
            print("Invalid agent. Please try again.")

    def close(self) -> None:
        """Close the dialog."""
        pass


class SettingsDialog:
    """Dialog for configuring settings."""

    def __init__(
        self,
        settings: dict[str, Any],
        *,
        callback: Optional[Callable[[Optional[dict[str, Any]]], None]] = None,
    ) -> None:
        self.callback = callback
        self.settings = settings.copy()
        self.input_fields: dict[str, str] = {k: str(v) for k, v in settings.items()}
        self.result: Optional[dict[str, Any]] = None

    def show(self) -> Optional[dict[str, Any]]:
        """Show the dialog and return result."""
        print("\nSettings")
        print("-" * 40)

        for key, value in self.input_fields.items():
            response = input(f"{key} [{value}]: ").strip()
            if response:
                self.input_fields[key] = response

        for key, field in self.input_fields.items():
            try:
                if field.isdigit():
                    self.settings[key] = int(field)
                elif field.replace(".", "", 1).isdigit():
                    self.settings[key] = float(field)
                elif field.lower() in ("true", "false"):
                    self.settings[key] = field.lower() == "true"
                else:
                    self.settings[key] = field
            except ValueError:
                self.settings[key] = field

        if self.callback:
            self.callback(self.settings)
        self.result = self.settings
        return self.result

    def close(self) -> None:
        """Close the dialog."""
        pass
