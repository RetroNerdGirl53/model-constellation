"""Permission system core - Core classes and permission manager."""

from __future__ import annotations

import json
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PermissionMode(Enum):
    """Permission modes for tool execution.

    Attributes:
        FIRST_TIME: Ask permission once per unique tool, remember for session.
        EVERY_TIME: Always ask permission before each tool execution.
        ALLOW_ALL: Execute all tools without prompting.
        DENY_ALL: Block all tool executions.
    """

    FIRST_TIME = "first-time"
    EVERY_TIME = "every-time"
    ALLOW_ALL = "allow-all"
    DENY_ALL = "deny-all"

    def __str__(self) -> str:
        return self.value


@dataclass
class PermissionRequest:
    """Represents a tool permission request.

    Attributes:
        tool_name: Name of the tool being requested.
        parameters: Parameters passed to the tool.
        category: Tool category (file, system, network, agent).
        session_id: Current session identifier.
        context: Additional context about the request.
    """

    tool_name: str
    parameters: Dict[str, Any]
    category: str = "general"
    session_id: str = "default"
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def get_cache_key(self) -> str:
        """Generate a unique cache key for this request.

        Returns:
            A hashed cache key based on tool name and relevant parameters.
        """
        key_parts = [self.tool_name]

        if self.tool_name == "bash":
            key_parts.append(str(self.parameters.get("command", "")))
        elif self.tool_name in ("read", "write", "glob", "grep"):
            key_parts.append(str(self.parameters.get("path", "")))

        cache_string = "|".join(key_parts)
        return hashlib.sha256(cache_string.encode()).hexdigest()[:16]


@dataclass
class PermissionResult:
    """Result of a permission check.

    Attributes:
        allowed: Whether the tool execution is allowed.
        remember: Whether to remember this decision for future requests.
        reason: Human-readable reason for the decision.
        expires_at: When this decision expires (for caching).
    """

    allowed: bool
    remember: bool = False
    reason: str = ""
    expires_at: Optional[datetime] = None

    @classmethod
    def allow(cls, remember: bool = False, reason: str = "") -> PermissionResult:
        """Create an allow result.

        Args:
            remember: Whether to remember this decision.
            reason: Human-readable reason.

        Returns:
            PermissionResult with allowed=True.
        """
        return cls(allowed=True, remember=remember, reason=reason)

    @classmethod
    def deny(cls, reason: str = "") -> PermissionResult:
        """Create a deny result.

        Args:
            reason: Human-readable reason for denial.

        Returns:
            PermissionResult with allowed=False.
        """
        return cls(allowed=False, reason=reason)


@dataclass
class PermissionCache:
    """Cached permission decision.

    Attributes:
        tool_name: Name of the tool.
        action: "allow" or "deny".
        timestamp: When the decision was made.
        expires_in: Seconds until the decision expires.
        session_id: Session the decision applies to.
    """

    tool_name: str
    action: str
    timestamp: datetime
    expires_in: int
    session_id: str

    def is_expired(self) -> bool:
        """Check if the cached decision has expired.

        Returns:
            True if expired, False otherwise.
        """
        expiry_time = self.timestamp + timedelta(seconds=self.expires_in)
        return datetime.now() > expiry_time


class PermissionStorage:
    """Handles persistent storage of permission decisions.

    Stores permission history and cached decisions to a JSON file.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize the permission storage.

        Args:
            storage_path: Path to the storage file. Defaults to ~/.model-constellation/permissions.json
        """
        if storage_path is None:
            home = Path.home()
            tars_dir = home / ".model-constellation"
            tars_dir.mkdir(exist_ok=True)
            storage_path = tars_dir / "permissions.json"

        self.storage_path = storage_path
        self._ensure_storage_exists()

    def _ensure_storage_exists(self) -> None:
        """Create storage file if it doesn't exist."""
        if not self.storage_path.exists():
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_data({"decisions": [], "history": []})

    def _load_data(self) -> Dict[str, Any]:
        """Load data from storage file.

        Returns:
            Dictionary containing permission data.
        """
        try:
            with open(self.storage_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"decisions": [], "history": []}

    def _save_data(self, data: Dict[str, Any]) -> None:
        """Save data to storage file.

        Args:
            data: Dictionary to save.
        """
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def get_cached_decision(
        self, tool_name: str, cache_key: str, session_id: str
    ) -> Optional[PermissionCache]:
        """Get a cached permission decision.

        Args:
            tool_name: Name of the tool.
            cache_key: Specific cache key for the request.
            session_id: Current session ID.

        Returns:
            PermissionCache if found and not expired, None otherwise.
        """
        data = self._load_data()
        for decision in data.get("decisions", []):
            if (
                decision.get("tool_name") == tool_name
                and decision.get("cache_key") == cache_key
                and decision.get("session_id") == session_id
            ):
                timestamp = datetime.fromisoformat(decision["timestamp"])
                cache = PermissionCache(
                    tool_name=decision["tool_name"],
                    action=decision["action"],
                    timestamp=timestamp,
                    expires_in=decision.get("expires_in", 3600),
                    session_id=decision["session_id"],
                )
                if not cache.is_expired():
                    return cache
        return None

    def cache_decision(
        self,
        tool_name: str,
        cache_key: str,
        action: str,
        session_id: str,
        expires_in: int = 3600,
    ) -> None:
        """Cache a permission decision.

        Args:
            tool_name: Name of the tool.
            cache_key: Specific cache key for the request.
            action: "allow" or "deny".
            session_id: Current session ID.
            expires_in: Seconds until the decision expires.
        """
        data = self._load_data()

        existing = [
            i
            for i, d in enumerate(data.get("decisions", []))
            if d.get("tool_name") == tool_name
            and d.get("cache_key") == cache_key
            and d.get("session_id") == session_id
        ]

        decision = {
            "tool_name": tool_name,
            "cache_key": cache_key,
            "action": action,
            "timestamp": datetime.now().isoformat(),
            "expires_in": expires_in,
            "session_id": session_id,
        }

        if existing:
            data["decisions"][existing[0]] = decision
        else:
            data["decisions"].append(decision)

        self._save_data(data)

    def add_history(self, tool_name: str, action: str, parameters: Dict[str, Any]) -> None:
        """Add an entry to permission history.

        Args:
            tool_name: Name of the tool.
            action: "allow" or "deny".
            parameters: Parameters passed to the tool.
        """
        data = self._load_data()

        entry = {
            "tool_name": tool_name,
            "action": action,
            "timestamp": datetime.now().isoformat(),
            "parameters": parameters,
        }

        data["history"].append(entry)

        data["history"] = data["history"][-1000:]

        self._save_data(data)

    def get_history(self, limit: int = 100) -> list:
        """Get permission history.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of history entries.
        """
        data = self._load_data()
        return data.get("history", [])[-limit:]

    def clear_cache(self, session_id: Optional[str] = None) -> None:
        """Clear cached permissions.

        Args:
            session_id: If provided, only clear decisions for this session.
        """
        data = self._load_data()

        if session_id:
            data["decisions"] = [d for d in data["decisions"] if d.get("session_id") != session_id]
        else:
            data["decisions"] = []

        self._save_data(data)


class PermissionManager:
    """Manages tool execution permissions.

    Handles permission checks based on configured mode, caches decisions,
    and coordinates with the danger detector.
    """

    def __init__(
        self,
        mode: PermissionMode = PermissionMode.FIRST_TIME,
        cache_ttl: int = 3600,
        storage: Optional[PermissionStorage] = None,
    ):
        """Initialize the permission manager.

        Args:
            mode: Permission mode to use.
            cache_ttl: Time-to-live for cached decisions in seconds.
            storage: Optional custom storage handler.
        """
        self.mode = mode
        self.cache_ttl = cache_ttl
        self.storage = storage or PermissionStorage()
        self._session_cache: Dict[str, PermissionCache] = {}
        self._prompt_callback: Optional[callable] = None

    @property
    def mode(self) -> PermissionMode:
        """Get current permission mode."""
        return self._mode

    @mode.setter
    def mode(self, value: PermissionMode | str) -> None:
        """Set permission mode.

        Args:
            value: Permission mode as enum or string.
        """
        if isinstance(value, str):
            value = PermissionMode(value)
        self._mode = value

    def set_prompt_callback(self, callback: callable) -> None:
        """Set the callback function for prompting the user.

        Args:
            callback: Function that takes PermissionRequest and returns PermissionResult.
        """
        self._prompt_callback = callback

    def check_permission(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        category: str = "general",
        session_id: str = "default",
    ) -> PermissionResult:
        """Check if tool execution is allowed.

        Args:
            tool_name: Name of the tool to execute.
            parameters: Parameters for the tool.
            category: Tool category.
            session_id: Current session ID.

        Returns:
            PermissionResult indicating whether execution is allowed.
        """
        request = PermissionRequest(
            tool_name=tool_name,
            parameters=parameters,
            category=category,
            session_id=session_id,
        )

        if self.mode == PermissionMode.ALLOW_ALL:
            logger.info(f"Permission ALLOW_ALL: allowing {tool_name}")
            return PermissionResult.allow(reason="Allow all mode")

        if self.mode == PermissionMode.DENY_ALL:
            logger.info(f"Permission DENY_ALL: denying {tool_name}")
            return PermissionResult.deny(reason="Deny all mode")

        if self.mode == PermissionMode.EVERY_TIME:
            return self._prompt_user(request)

        if self.mode == PermissionMode.FIRST_TIME:
            return self._check_first_time(request)

        return PermissionResult.deny(reason="Unknown permission mode")

    def _check_first_time(self, request: PermissionRequest) -> PermissionResult:
        """Check permission in first-time mode.

        Args:
            request: The permission request.

        Returns:
            PermissionResult with the decision.
        """
        cache_key = request.get_cache_key()

        cached = self.storage.get_cached_decision(request.tool_name, cache_key, request.session_id)

        if cached:
            logger.info(f"Permission cache hit for {request.tool_name}: {cached.action}")
            return PermissionResult(
                allowed=cached.action == "allow",
                reason="Cached decision",
            )

        return self._prompt_user(request)

    def _prompt_user(self, request: PermissionRequest) -> PermissionResult:
        """Prompt the user for permission.

        Args:
            request: The permission request.

        Returns:
            PermissionResult with the user's decision.
        """
        if self._prompt_callback:
            return self._prompt_callback(request)

        logger.warning(f"No prompt callback set, defaulting to deny for {request.tool_name}")
        return PermissionResult.deny(reason="No prompt callback configured")

    def cache_decision(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        allowed: bool,
        session_id: str = "default",
    ) -> None:
        """Cache a permission decision.

        Args:
            tool_name: Name of the tool.
            parameters: Parameters for the tool.
            allowed: Whether the tool was allowed.
            session_id: Current session ID.
        """
        request = PermissionRequest(
            tool_name=tool_name,
            parameters=parameters,
            session_id=session_id,
        )

        cache_key = request.get_cache_key()
        action = "allow" if allowed else "deny"

        self.storage.cache_decision(
            tool_name=tool_name,
            cache_key=cache_key,
            action=action,
            session_id=session_id,
            expires_in=self.cache_ttl,
        )

        self.storage.add_history(tool_name, action, parameters)

    def clear_cache(self, session_id: Optional[str] = None) -> None:
        """Clear cached permission decisions.

        Args:
            session_id: If provided, only clear for this session.
        """
        self.storage.clear_cache(session_id)
        self._session_cache.clear()

    def get_history(self, limit: int = 100) -> list:
        """Get permission history.

        Args:
            limit: Maximum number of entries.

        Returns:
            List of history entries.
        """
        return self.storage.get_history(limit)

    def get_mode(self) -> str:
        """Get current permission mode as string.

        Returns:
            String representation of the permission mode.
        """
        return self.mode.value

    def set_mode(self, mode: PermissionMode | str) -> None:
        """Set permission mode.

        Args:
            mode: Permission mode as enum or string.
        """
        self.mode = mode
        logger.info(f"Permission mode set to {mode}")
