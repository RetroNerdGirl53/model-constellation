"""Dangerous tool detection module.

Provides detection and risk assessment for potentially dangerous tool operations.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DangerLevel(Enum):
    """Risk level for tool operations.

    Attributes:
        SAFE: No significant risk.
        LOW: Minor risk, proceed with caution.
        MEDIUM: Moderate risk, user should be informed.
        HIGH: High risk, requires explicit confirmation.
        CRITICAL: Critical risk, potentially destructive.
    """

    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __str__(self) -> str:
        return self.value

    def __ge__(self, other: "DangerLevel") -> bool:
        order = [
            DangerLevel.SAFE,
            DangerLevel.LOW,
            DangerLevel.MEDIUM,
            DangerLevel.HIGH,
            DangerLevel.CRITICAL,
        ]
        return order.index(self) >= order.index(other)

    def __gt__(self, other: "DangerLevel") -> bool:
        order = [
            DangerLevel.SAFE,
            DangerLevel.LOW,
            DangerLevel.MEDIUM,
            DangerLevel.HIGH,
            DangerLevel.CRITICAL,
        ]
        return order.index(self) > order.index(other)

    def __le__(self, other: "DangerLevel") -> bool:
        order = [
            DangerLevel.SAFE,
            DangerLevel.LOW,
            DangerLevel.MEDIUM,
            DangerLevel.HIGH,
            DangerLevel.CRITICAL,
        ]
        return order.index(self) <= order.index(other)

    def __lt__(self, other: "DangerLevel") -> bool:
        order = [
            DangerLevel.SAFE,
            DangerLevel.LOW,
            DangerLevel.MEDIUM,
            DangerLevel.HIGH,
            DangerLevel.CRITICAL,
        ]
        return order.index(self) < order.index(other)


@dataclass
class DangerPattern:
    """A pattern that indicates potential danger.

    Attributes:
        pattern: Regex pattern to match.
        danger_level: The danger level if pattern matches.
        description: Human-readable description of the risk.
        category: Category of the danger (file, system, network).
    """

    pattern: str
    danger_level: DangerLevel
    description: str
    category: str = "general"


@dataclass
class DangerWarning:
    """A warning about dangerous tool usage.

    Attributes:
        level: The danger level.
        description: Human-readable warning message.
        category: Category of the danger.
        pattern_matched: The pattern that triggered this warning.
    """

    level: DangerLevel
    description: str
    category: str
    pattern_matched: str = ""

    def format_warning(self) -> str:
        """Format the warning as a string.

        Returns:
            Formatted warning message.
        """
        icon = self._get_icon()
        return f"{icon} {self.description}"

    def _get_icon(self) -> str:
        """Get icon for danger level.

        Returns:
            Icon string.
        """
        icons = {
            DangerLevel.SAFE: "",
            DangerLevel.LOW: "⚠",
            DangerLevel.MEDIUM: "⚠️",
            DangerLevel.HIGH: "🔶",
            DangerLevel.CRITICAL: "🔴",
        }
        return icons.get(self.level, "")


class DangerDetector:
    """Detects potentially dangerous operations in tool parameters.

    Provides pattern-based detection for dangerous commands, file operations,
    network requests, and system modifications.
    """

    def __init__(self):
        """Initialize the danger detector with default patterns."""
        self._file_patterns = self._init_file_patterns()
        self._system_patterns = self._init_system_patterns()
        self._network_patterns = self._init_network_patterns()

    def _init_file_patterns(self) -> List[DangerPattern]:
        """Initialize dangerous file operation patterns.

        Returns:
            List of danger patterns for file operations.
        """
        return [
            DangerPattern(
                pattern=r"rm\s+-rf\s+/?",
                danger_level=DangerLevel.CRITICAL,
                description="Recursive force delete - will permanently remove files",
                category="file",
            ),
            DangerPattern(
                pattern=r"rmdir?\s+",
                danger_level=DangerLevel.HIGH,
                description="Directory deletion",
                category="file",
            ),
            DangerPattern(
                pattern=r"del\s+[/\:]",
                danger_level=DangerLevel.CRITICAL,
                description="Windows delete command - may be destructive",
                category="file",
            ),
            DangerPattern(
                pattern=r"format\s+[a-z]:?",
                danger_level=DangerLevel.CRITICAL,
                description="Drive format - will erase all data",
                category="file",
            ),
            DangerPattern(
                pattern=r"shred\s+",
                danger_level=DangerLevel.CRITICAL,
                description="Secure file deletion - files cannot be recovered",
                category="file",
            ),
            DangerPattern(
                pattern=r"dd\s+.*of=/dev/",
                danger_level=DangerLevel.CRITICAL,
                description="Direct device write - can destroy filesystem",
                category="file",
            ),
            DangerPattern(
                pattern=r">\s*/dev/sd",
                danger_level=DangerLevel.CRITICAL,
                description="Writing to block device - data loss risk",
                category="file",
            ),
            DangerPattern(
                pattern=r"mkfs\.?",
                danger_level=DangerLevel.CRITICAL,
                description="Filesystem creation - will erase partition",
                category="file",
            ),
            DangerPattern(
                pattern=r"chmod\s+-R\s+777",
                danger_level=DangerLevel.MEDIUM,
                description="World-writable permissions - security risk",
                category="file",
            ),
            DangerPattern(
                pattern=r"chown\s+-R",
                danger_level=DangerLevel.MEDIUM,
                description="Recursive ownership change",
                category="file",
            ),
            DangerPattern(
                pattern=r"mv\s+.*\s+/dev/null",
                danger_level=DangerLevel.HIGH,
                description="Moving file to null - permanent data loss",
                category="file",
            ),
            DangerPattern(
                pattern=r">\s*~/.bashrc",
                danger_level=DangerLevel.MEDIUM,
                description="Overwriting shell configuration",
                category="file",
            ),
            DangerPattern(
                pattern=r">\s*~/.bash_profile",
                danger_level=DangerLevel.MEDIUM,
                description="Overwriting shell login configuration",
                category="file",
            ),
            DangerPattern(
                pattern=r"tee\s+.*>",
                danger_level=DangerLevel.MEDIUM,
                description="Writing to file with tee",
                category="file",
            ),
        ]

    def _init_system_patterns(self) -> List[DangerPattern]:
        """Initialize dangerous system command patterns.

        Returns:
            List of danger patterns for system operations.
        """
        return [
            DangerPattern(
                pattern=r"sudo\s+",
                danger_level=DangerLevel.HIGH,
                description="Elevated privileges - executes with root access",
                category="system",
            ),
            DangerPattern(
                pattern=r"su\s+",
                danger_level=DangerLevel.HIGH,
                description="Switch user - may gain elevated access",
                category="system",
            ),
            DangerPattern(
                pattern=r"systemctl\s+(stop|restart|disable|enable)",
                danger_level=DangerLevel.HIGH,
                description="Systemd service manipulation",
                category="system",
            ),
            DangerPattern(
                pattern=r"service\s+(stop|restart)",
                danger_level=DangerLevel.HIGH,
                description="Service management - may disrupt system",
                category="system",
            ),
            DangerPattern(
                pattern=r"kill\s+-9",
                danger_level=DangerLevel.MEDIUM,
                description="Force kill - may cause data loss",
                category="system",
            ),
            DangerPattern(
                pattern=r"killall",
                danger_level=DangerLevel.MEDIUM,
                description="Kill all processes - may disrupt system",
                category="system",
            ),
            DangerPattern(
                pattern=r"reboot",
                danger_level=DangerLevel.HIGH,
                description="System reboot",
                category="system",
            ),
            DangerPattern(
                pattern=r"shutdown",
                danger_level=DangerLevel.HIGH,
                description="System shutdown",
                category="system",
            ),
            DangerPattern(
                pattern=r"crontab\s+-r",
                danger_level=DangerLevel.MEDIUM,
                description="Remove crontab - scheduled jobs will be lost",
                category="system",
            ),
            DangerPattern(
                pattern=r"iptables",
                danger_level=DangerLevel.HIGH,
                description="Firewall manipulation",
                category="system",
            ),
            DangerPattern(
                pattern=r"ufw\s+(delete|remove|disable)",
                danger_level=DangerLevel.HIGH,
                description="Disabling firewall - security risk",
                category="system",
            ),
            DangerPattern(
                pattern=r"eval\s+",
                danger_level=DangerLevel.HIGH,
                description="Eval command - potential code injection",
                category="system",
            ),
            DangerPattern(
                pattern=r"source\s+/dev/",
                danger_level=DangerLevel.HIGH,
                description="Sourcing from device - unexpected behavior",
                category="system",
            ),
            DangerPattern(
                pattern=r"echo\s+.*>\s*/proc/",
                danger_level=DangerLevel.HIGH,
                description="Writing to procfs - system modification",
                category="system",
            ),
        ]

    def _init_network_patterns(self) -> List[DangerPattern]:
        """Initialize dangerous network operation patterns.

        Returns:
            List of danger patterns for network operations.
        """
        return [
            DangerPattern(
                pattern=r"curl.*\|.*sh",
                danger_level=DangerLevel.CRITICAL,
                description="Piping remote script to shell - severe security risk",
                category="network",
            ),
            DangerPattern(
                pattern=r"wget.*\|.*sh",
                danger_level=DangerLevel.CRITICAL,
                description="Piping remote script to shell - severe security risk",
                category="network",
            ),
            DangerPattern(
                pattern=r"nc\s+(-e|--exec)",
                danger_level=DangerLevel.CRITICAL,
                description="Netcat with exec - potential backdoor",
                category="network",
            ),
            DangerPattern(
                pattern=r"nc\s+(-l|--listen)",
                danger_level=DangerLevel.MEDIUM,
                description="Netcat listener - potential backdoor risk",
                category="network",
            ),
            DangerPattern(
                pattern=r"ssh\s+.*-o\s+StrictHostKeyChecking=no",
                danger_level=DangerLevel.MEDIUM,
                description="SSH skip host key - MITM risk",
                category="network",
            ),
            DangerPattern(
                pattern=r"scp\s+.*-r",
                danger_level=DangerLevel.LOW,
                description="Recursive copy - may transfer sensitive files",
                category="network",
            ),
            DangerPattern(
                pattern=r"rsync\s+.*--delete",
                danger_level=DangerLevel.HIGH,
                description="Rsync with delete - files may be removed",
                category="network",
            ),
            DangerPattern(
                pattern=r":\(\)\{",
                danger_level=DangerLevel.CRITICAL,
                description="Fork bomb - can crash the system",
                category="network",
            ),
            DangerPattern(
                pattern=r"curl\s+.*-X\s+(POST|PUT|DELETE)",
                danger_level=DangerLevel.MEDIUM,
                description="HTTP method modification",
                category="network",
            ),
            DangerPattern(
                pattern=r"openssl\s+s_client",
                danger_level=DangerLevel.LOW,
                description="OpenSSL client - testing SSL connections",
                category="network",
            ),
        ]

    def detect(
        self, tool_name: str, parameters: Dict[str, Any]
    ) -> Tuple[DangerLevel, List[DangerWarning]]:
        """Detect dangerous operations in tool parameters.

        Args:
            tool_name: Name of the tool.
            parameters: Parameters passed to the tool.

        Returns:
            Tuple of (maximum danger level, list of warnings).
        """
        warnings: List[DangerWarning] = []

        if tool_name == "bash":
            command = parameters.get("command", "")
            warnings.extend(self._check_bash_command(command))

        elif tool_name in ("read", "write", "glob", "grep"):
            path = parameters.get("path", "")
            warnings.extend(self._check_file_path(path))

        elif tool_name in ("webfetch", "websearch"):
            url_or_query = parameters.get("url", "") or parameters.get("query", "")
            warnings.extend(self._check_network_request(url_or_query))

        max_level = DangerLevel.SAFE
        for warning in warnings:
            if warning.level > max_level:
                max_level = warning.level

        return max_level, warnings

    def _check_bash_command(self, command: str) -> List[DangerWarning]:
        """Check a bash command for dangerous patterns.

        Args:
            command: The command to check.

        Returns:
            List of danger warnings found.
        """
        warnings: List[DangerWarning] = []

        if not command:
            return warnings

        for pattern in self._system_patterns + self._file_patterns:
            if re.search(pattern.pattern, command, re.IGNORECASE):
                warnings.append(
                    DangerWarning(
                        level=pattern.danger_level,
                        description=pattern.description,
                        category=pattern.category,
                        pattern_matched=pattern.pattern,
                    )
                )

        for pattern in self._network_patterns:
            if re.search(pattern.pattern, command, re.IGNORECASE):
                warnings.append(
                    DangerWarning(
                        level=pattern.danger_level,
                        description=pattern.description,
                        category=pattern.category,
                        pattern_matched=pattern.pattern,
                    )
                )

        return warnings

    def _check_file_path(self, path: str) -> List[DangerWarning]:
        """Check a file path for dangerous patterns.

        Args:
            path: The file path to check.

        Returns:
            List of danger warnings found.
        """
        warnings: List[DangerWarning] = []

        if not path:
            return warnings

        dangerous_paths = [
            (r"^/etc/passwd", DangerLevel.HIGH, "System password file"),
            (r"^/etc/shadow", DangerLevel.CRITICAL, "System shadow file"),
            (r"^/etc/ssh/", DangerLevel.HIGH, "SSH configuration directory"),
            (r"^/usr/bin/", DangerLevel.MEDIUM, "System binaries directory"),
            (r"^/usr/sbin/", DangerLevel.MEDIUM, "System binaries directory"),
            (r"^/bin/", DangerLevel.MEDIUM, "System binaries directory"),
            (r"^/sbin/", DangerLevel.MEDIUM, "System binaries directory"),
            (r"^/boot/", DangerLevel.HIGH, "Boot directory"),
            (r"^/sys/", DangerLevel.HIGH, "Sysfs directory"),
            (r"^/proc/", DangerLevel.HIGH, "Procfs directory"),
            (r"\.ssh/", DangerLevel.HIGH, "SSH keys directory"),
            (r"\.aws/", DangerLevel.HIGH, "AWS credentials directory"),
            (r"\.gnupg/", DangerLevel.HIGH, "GPG keys directory"),
        ]

        for pattern, level, description in dangerous_paths:
            if re.search(pattern, path):
                warnings.append(
                    DangerWarning(
                        level=level,
                        description=f"Access to {description}",
                        category="file",
                        pattern_matched=pattern,
                    )
                )

        return warnings

    def _check_network_request(self, request: str) -> List[DangerWarning]:
        """Check a network request for dangerous patterns.

        Args:
            request: The URL or query to check.

        Returns:
            List of danger warnings found.
        """
        warnings: List[DangerWarning] = []

        if not request:
            return warnings

        dangerous_patterns = [
            (r"file://", DangerLevel.MEDIUM, "Local file access via URL"),
            (r"gopher://", DangerLevel.MEDIUM, "Gopher protocol - obsolete"),
            (r"javascript:", DangerLevel.HIGH, "JavaScript injection"),
            (r"data:text/html", DangerLevel.HIGH, "HTML data URL - XSS risk"),
        ]

        for pattern, level, description in dangerous_patterns:
            if re.search(pattern, request, re.IGNORECASE):
                warnings.append(
                    DangerWarning(
                        level=level,
                        description=description,
                        category="network",
                        pattern_matched=pattern,
                    )
                )

        return warnings

    def get_risk_assessment(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get a comprehensive risk assessment for a tool execution.

        Args:
            tool_name: Name of the tool.
            parameters: Parameters for the tool.

        Returns:
            Dictionary containing risk assessment details.
        """
        danger_level, warnings = self.detect(tool_name, parameters)

        return {
            "tool_name": tool_name,
            "danger_level": danger_level.value,
            "warnings": [w.format_warning() for w in warnings],
            "requires_confirmation": danger_level >= DangerLevel.HIGH,
            "summary": self._get_summary(tool_name, danger_level, warnings),
        }

    def _get_summary(
        self, tool_name: str, level: DangerLevel, warnings: List[DangerWarning]
    ) -> str:
        """Get a summary string for the risk assessment.

        Args:
            tool_name: Name of the tool.
            level: The danger level.
            warnings: List of warnings.

        Returns:
            Summary string.
        """
        if level == DangerLevel.SAFE:
            return f"Tool '{tool_name}' appears safe to execute."
        elif level == DangerLevel.LOW:
            return f"Tool '{tool_name}' has low risk. {len(warnings)} warning(s)."
        elif level == DangerLevel.MEDIUM:
            return f"Tool '{tool_name}' has medium risk. User should be informed."
        elif level == DangerLevel.HIGH:
            return f"Tool '{tool_name}' has high risk. Explicit confirmation recommended."
        else:
            return (
                f"Tool '{tool_name}' has critical risk. Do not execute without full understanding."
            )
