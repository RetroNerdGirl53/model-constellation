"""model-constellation — Ollama-powered AI agent framework.

This package is usable two ways:

* **As a CLI** — ``model-constellation run ...`` (see :mod:`model_constellation.core`).
* **As a library / backend** — import the public API below and embed the engine in
  your own application:

      from model_constellation import AgentRuntime, OllamaClient

      runtime = AgentRuntime(OllamaClient(base_url="http://localhost:11434"),
                             model="llama3.1", permission_mode="allow-all")
      result = runtime.run("List the Python files here")
      print(result.content)

  An HTTP server (FastAPI) over the same engine lives in
  :mod:`model_constellation.api` (requires the ``api`` extra).

The heavy names below are imported lazily (PEP 562) so ``import model_constellation``
stays cheap; importing a name like ``AgentRuntime`` pulls in its module on first use.
"""

from typing import TYPE_CHECKING

from model_constellation.constants import (
    CONFIG_VERSION,
    DEFAULT_KEEP_ALIVE,
    DEFAULT_MODEL,
    DEFAULT_NUM_CTX,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_REPEAT_PENALTY,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
)

__version__ = "1.1.0"
__author__ = "model-constellation Team"
__description__ = "Ollama-powered AI agent framework with tools, permissions, and swarms"

# Public API name -> (submodule, attribute). Resolved lazily by __getattr__.
_LAZY_EXPORTS = {
    # Runtime (the standard backend entry point)
    "AgentRuntime": ("model_constellation.runtime", "AgentRuntime"),
    "RuntimeResult": ("model_constellation.runtime", "RuntimeResult"),
    # Ollama client
    "OllamaClient": ("model_constellation.ollama_client", "OllamaClient"),
    "ChatMessage": ("model_constellation.ollama_client", "ChatMessage"),
    "ChatResponse": ("model_constellation.ollama_client", "ChatResponse"),
    "ModelParameters": ("model_constellation.ollama_client", "ModelParameters"),
    "OllamaConnectionError": ("model_constellation.ollama_client", "OllamaConnectionError"),
    "OllamaModelError": ("model_constellation.ollama_client", "OllamaModelError"),
    # Configuration
    "ConfigManager": ("model_constellation.config", "ConfigManager"),
    "load_config": ("model_constellation.config", "load_config"),
    "ModelConstellationConfig": ("model_constellation.models", "ModelConstellationConfig"),
    # Permissions
    "PermissionManager": ("model_constellation.permissions", "PermissionManager"),
    "PermissionMode": ("model_constellation.permissions", "PermissionMode"),
    # Tools
    "ToolRegistry": ("model_constellation.tools", "ToolRegistry"),
    "ToolExecutor": ("model_constellation.tools", "ToolExecutor"),
    "get_all_builtin_tools": ("model_constellation.tools", "get_all_builtin_tools"),
    "register_builtin_tools": ("model_constellation.tools", "register_builtin_tools"),
    # Agents
    "PrimaryAgent": ("model_constellation.agent.primary", "PrimaryAgent"),
    "AgentSwarm": ("model_constellation.agent.swarm", "AgentSwarm"),
    "SwarmMode": ("model_constellation.agent.swarm", "SwarmMode"),
    # HTTP API (requires the `api` extra)
    "create_app": ("model_constellation.api.server", "create_app"),
    "APISettings": ("model_constellation.api.server", "APISettings"),
}

if TYPE_CHECKING:  # help type checkers / IDEs resolve the lazy names
    from model_constellation.agent.primary import PrimaryAgent
    from model_constellation.agent.swarm import AgentSwarm, SwarmMode
    from model_constellation.config import ConfigManager, load_config
    from model_constellation.models import ModelConstellationConfig
    from model_constellation.ollama_client import (
        ChatMessage,
        ChatResponse,
        ModelParameters,
        OllamaClient,
        OllamaConnectionError,
        OllamaModelError,
    )
    from model_constellation.permissions import PermissionManager, PermissionMode
    from model_constellation.runtime import AgentRuntime, RuntimeResult
    from model_constellation.tools import (
        ToolExecutor,
        ToolRegistry,
        get_all_builtin_tools,
        register_builtin_tools,
    )


def __getattr__(name: str):
    """Lazily import public API names (PEP 562)."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(target[0])
    return getattr(module, target[1])


def __dir__():
    return sorted(list(globals().keys()) + list(_LAZY_EXPORTS.keys()))


__all__ = [
    "__version__",
    # constants
    "CONFIG_VERSION",
    "DEFAULT_OLLAMA_BASE_URL",
    "DEFAULT_MODEL",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TOP_P",
    "DEFAULT_TOP_K",
    "DEFAULT_REPEAT_PENALTY",
    "DEFAULT_NUM_CTX",
    "DEFAULT_TIMEOUT",
    "DEFAULT_KEEP_ALIVE",
    *_LAZY_EXPORTS.keys(),
]
