"""Permission prompts module.

Handles user interaction for permission requests with dangerous tool warnings.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from model_constellation.permissions.core import PermissionRequest, PermissionResult
from model_constellation.permissions.detector import DangerDetector, DangerLevel, DangerWarning

logger = logging.getLogger(__name__)


class PermissionPrompter:
    """Handles permission request UI and user interaction.

    Creates permission prompts with tool details, risk assessments,
    and handles user decisions.
    """

    def __init__(self, danger_detector: Optional[DangerDetector] = None):
        """Initialize the permission prompter.

        Args:
            danger_detector: Optional custom danger detector.
        """
        self.danger_detector = danger_detector or DangerDetector()
        self._input_handler: Optional[callable] = None

    def set_input_handler(self, handler: callable) -> None:
        """Set the input handler function.

        Args:
            handler: Function that handles user input (returns selected option).
        """
        self._input_handler = handler

    def create_prompt(self, request: PermissionRequest) -> Dict[str, Any]:
        """Create a permission prompt with full details.

        Args:
            request: The permission request.

        Returns:
            Dictionary containing prompt details.
        """
        risk = self.danger_detector.get_risk_assessment(request.tool_name, request.parameters)

        prompt = {
            "tool_name": request.tool_name,
            "parameters": self._format_parameters(request.parameters),
            "category": request.category,
            "danger_level": risk["danger_level"],
            "warnings": risk["warnings"],
            "summary": risk["summary"],
            "requires_confirmation": risk["requires_confirmation"],
            "options": self._get_options(risk["danger_level"]),
        }

        return prompt

    def _format_parameters(self, parameters: Dict[str, Any]) -> str:
        """Format parameters for display.

        Args:
            parameters: Parameters dictionary.

        Returns:
            Formatted parameter string.
        """
        if not parameters:
            return "(no parameters)"

        formatted = []
        for key, value in parameters.items():
            if key == "command":
                cmd = str(value)
                if len(cmd) > 100:
                    cmd = cmd[:100] + "..."
                formatted.append(f"command: {cmd}")
            elif key == "path":
                formatted.append(f"path: {value}")
            elif key == "content" and len(str(value)) > 50:
                formatted.append(f"{key}: (content length: {len(str(value))} chars)")
            elif key == "pattern":
                formatted.append(f"pattern: {value}")
            elif key == "url":
                formatted.append(f"url: {value}")
            elif key == "query":
                formatted.append(f"query: {value}")
            else:
                formatted.append(f"{key}: {value}")

        return "\n".join(formatted)

    def _get_options(self, danger_level: str) -> list:
        """Get available options based on danger level.

        Args:
            danger_level: The danger level string.

        Returns:
            List of available option tuples (key, label).
        """
        base_options = [("allow", "Allow"), ("deny", "Deny")]

        if danger_level in ("high", "critical"):
            base_options.append(("view", "View Context"))
        else:
            base_options.append(("remember", "Remember for Session"))

        return base_options

    def prompt(
        self,
        request: PermissionRequest,
        show_prompt: bool = True,
    ) -> PermissionResult:
        """Prompt the user for permission.

        Args:
            request: The permission request.
            show_prompt: Whether to show the interactive prompt.

        Returns:
            PermissionResult with the user's decision.
        """
        prompt_data = self.create_prompt(request)

        if not show_prompt:
            if prompt_data["requires_confirmation"]:
                return PermissionResult.deny(reason="Requires confirmation")
            return PermissionResult.allow(reason="Auto-allowed")

        if self._input_handler:
            return self._handle_input(prompt_data)

        return self._default_prompt(prompt_data)

    def _handle_input(self, prompt_data: Dict[str, Any]) -> PermissionResult:
        """Handle user input for the prompt.

        Args:
            prompt_data: The prompt data.

        Returns:
            PermissionResult based on user input.
        """
        try:
            choice = self._input_handler(prompt_data)

            if choice == "allow":
                return PermissionResult.allow(remember=False, reason="User allowed")
            elif choice == "deny":
                return PermissionResult.deny(reason="User denied")
            elif choice == "remember":
                return PermissionResult.allow(remember=True, reason="User allowed (remember)")
            elif choice == "view":
                return PermissionResult.deny(reason="User requested context view")
            else:
                return PermissionResult.deny(reason="Invalid choice")

        except Exception as e:
            logger.error(f"Error handling permission prompt: {e}")
            return PermissionResult.deny(reason="Error in prompt handling")

    def _default_prompt(self, prompt_data: Dict[str, Any]) -> PermissionResult:
        """Default prompt implementation (for non-interactive use).

        Args:
            prompt_data: The prompt data.

        Returns:
            PermissionResult (defaults to deny in non-interactive mode).
        """
        if prompt_data["requires_confirmation"]:
            return PermissionResult.deny(reason="Requires confirmation in non-interactive mode")
        return PermissionResult.deny(reason="Non-interactive mode")

    def format_warning_box(self, warnings: list) -> str:
        """Format warnings as a warning box.

        Args:
            warnings: List of warning strings.

        Returns:
            Formatted warning box string.
        """
        if not warnings:
            return ""

        lines = ["┌─────────────────────────────────────────────────────────┐"]
        lines.append("│  ⚠️  DANGER WARNINGS                                  │")
        lines.append("├─────────────────────────────────────────────────────────┤")

        for warning in warnings[:5]:
            lines.append(f"│  {warning:<53} │")

        if len(warnings) > 5:
            lines.append(f"│  ... and {len(warnings) - 5} more warnings                        │")

        lines.append("└─────────────────────────────────────────────────────────┘")

        return "\n".join(lines)

    def format_permission_request(self, request: PermissionRequest) -> str:
        """Format a complete permission request as a string.

        Args:
            request: The permission request.

        Returns:
            Formatted permission request string.
        """
        prompt_data = self.create_prompt(request)

        lines = ["┌─────────────────────────────────────────────────────────┐"]
        lines.append("│  ⚠️  Tool Execution Request                            │")
        lines.append("├─────────────────────────────────────────────────────────┤")
        lines.append(f"│  Tool: {prompt_data['tool_name']:<45} │")
        lines.append("├─────────────────────────────────────────────────────────┤")
        lines.append("│  Parameters:                                          │")

        param_lines = prompt_data["parameters"].split("\n")
        for param_line in param_lines[:10]:
            lines.append(f"│    {param_line:<50} │")

        lines.append("├─────────────────────────────────────────────────────────┤")
        lines.append(f"│  Risk Level: {prompt_data['danger_level']:<41} │")
        lines.append(f"│  {prompt_data['summary']:<51} │")

        if prompt_data["warnings"]:
            lines.append("├─────────────────────────────────────────────────────────┤")
            for warning in prompt_data["warnings"][:3]:
                lines.append(f"│  {warning:<53} │")

        lines.append("└─────────────────────────────────────────────────────────┘")

        options_text = " / ".join([f"[{k}] {v}" for k, v in prompt_data["options"]])
        lines.append(f"\nOptions: {options_text}")

        return "\n".join(lines)


@dataclass
class PromptOption:
    """Represents a prompt option.

    Attributes:
        key: Option key (e.g., 'allow', 'deny').
        label: Display label.
        description: Help text for the option.
        is_dangerous: Whether this option is dangerous.
    """

    key: str
    label: str
    description: str = ""
    is_dangerous: bool = False


class InteractivePrompter(PermissionPrompter):
    """Interactive permission prompter with full UI support.

    Extends PermissionPrompter with interactive terminal UI capabilities.
    """

    def __init__(self, danger_detector: Optional[DangerDetector] = None):
        """Initialize the interactive prompter.

        Args:
            danger_detector: Optional custom danger detector.
        """
        super().__init__(danger_detector)
        self._color_output = True

    def set_color_output(self, enabled: bool) -> None:
        """Enable or disable color output.

        Args:
            enabled: Whether to use colors.
        """
        self._color_output = enabled

    def prompt_interactive(
        self,
        request: PermissionRequest,
    ) -> PermissionResult:
        """Show an interactive permission prompt.

        Args:
            request: The permission request.

        Returns:
            PermissionResult with the user's decision.
        """
        prompt_data = self.create_prompt(request)

        self._print_header(prompt_data)
        self._print_parameters(prompt_data)
        self._print_warnings(prompt_data)
        self._print_options(prompt_data)

        while True:
            try:
                choice = input("\nEnter your choice: ").strip().lower()

                if choice in ("a", "allow", "y", "yes"):
                    remember = self._ask_remember()
                    return PermissionResult.allow(remember=remember, reason="User allowed")
                elif choice in ("d", "deny", "n", "no"):
                    return PermissionResult.deny(reason="User denied")
                elif choice in ("r", "remember"):
                    return PermissionResult.allow(
                        remember=True, reason="User allowed (remember for session)"
                    )
                elif choice in ("v", "view", "c", "context"):
                    self._show_context(request)
                elif choice in ("q", "quit", "exit"):
                    return PermissionResult.deny(reason="User quit")
                else:
                    print("Invalid choice. Please try again.")

            except (KeyboardInterrupt, EOFError):
                return PermissionResult.deny(reason="Interrupted")

    def _print_header(self, prompt_data: Dict[str, Any]) -> None:
        """Print the prompt header.

        Args:
            prompt_data: The prompt data.
        """
        danger = prompt_data["danger_level"]
        border_char = "─" if danger in ("safe", "low", "medium") else "⚠"

        if self._color_output:
            color = self._get_danger_color(danger)
            print(f"\n{color}┌{'─' * 53}┐{self._reset()}")
            print(f"{color}│  ⚠️  Tool Execution Request{' ' * 26}│{self._reset()}")
            print(f"{color}├{'─' * 53}┤{self._reset()}")
            print(f"{color}│  Tool: {prompt_data['tool_name']:<45}│{self._reset()}")
        else:
            print(f"\n┌{'─' * 53}┐")
            print(f"│  ⚠️  Tool Execution Request{' ' * 26}│")
            print(f"├{'─' * 53}┤")
            print(f"│  Tool: {prompt_data['tool_name']:<45}│")

    def _print_parameters(self, prompt_data: Dict[str, Any]) -> None:
        """Print the parameters.

        Args:
            prompt_data: The prompt data.
        """
        if self._color_output:
            print(
                f"{self._get_danger_color(prompt_data['danger_level'])}├{'─' * 53}┤{self._reset()}"
            )
            print("│  Parameters:                                          │")
            for line in prompt_data["parameters"].split("\n")[:8]:
                print(f"│    {line:<50}│")
        else:
            print(f"├{'─' * 53}┤")
            print("│  Parameters:                                          │")
            for line in prompt_data["parameters"].split("\n")[:8]:
                print(f"│    {line:<50}│")

    def _print_warnings(self, prompt_data: Dict[str, Any]) -> None:
        """Print warnings.

        Args:
            prompt_data: The prompt data.
        """
        if not prompt_data["warnings"]:
            return

        if self._color_output:
            print(
                f"{self._get_danger_color(prompt_data['danger_level'])}├{'─' * 53}┤{self._reset()}"
            )
            for warning in prompt_data["warnings"][:4]:
                print(
                    f"{self._get_danger_color(prompt_data['danger_level'])}│  {warning:<51}{self._reset()}│"
                )
            print(
                f"{self._get_danger_color(prompt_data['danger_level'])}└{'─' * 53}┘{self._reset()}"
            )
        else:
            print(f"├{'─' * 53}┤")
            for warning in prompt_data["warnings"][:4]:
                print(f"│  {warning:<51}│")
            print(f"└{'─' * 53}┘")

    def _print_options(self, prompt_data: Dict[str, Any]) -> None:
        """Print available options.

        Args:
            prompt_data: The prompt data.
        """
        options_str = " / ".join([f"[{k}] {v}" for k, v in prompt_data["options"]])
        print(f"\nOptions: {options_str}")

    def _ask_remember(self) -> bool:
        """Ask if the user wants to remember the decision.

        Returns:
            True if user wants to remember, False otherwise.
        """
        try:
            response = input("Remember this decision for the session? [y/N]: ").strip().lower()
            return response in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            return False

    def _show_context(self, request: PermissionRequest) -> None:
        """Show additional context about the request.

        Args:
            request: The permission request.
        """
        print("\n" + "=" * 60)
        print("Tool Context:")
        print("=" * 60)
        print(f"Tool Name: {request.tool_name}")
        print(f"Category: {request.category}")
        print(f"Session: {request.session_id}")
        print(f"Timestamp: {request.timestamp}")
        print(f"Full Parameters: {request.parameters}")
        print("=" * 60 + "\n")

    def _get_danger_color(self, danger_level: str) -> str:
        """Get ANSI color code for danger level.

        Args:
            danger_level: The danger level string.

        Returns:
            ANSI color code string.
        """
        colors = {
            "safe": "\033[92m",
            "low": "\033[93m",
            "medium": "\033[93m",
            "high": "\033[91m",
            "critical": "\033[91m",
        }
        return colors.get(danger_level, "")

    def _reset(self) -> str:
        """Get ANSI reset code.

        Returns:
            ANSI reset code.
        """
        return "\033[0m"
