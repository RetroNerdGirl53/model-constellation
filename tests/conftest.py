"""Shared test fixtures.

These tests never touch a real Ollama server: a scripted fake client returns
predetermined responses so the standardized agent/tools/permission wiring can be
verified deterministically.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pytest

from model_constellation.ollama_client import ChatMessage, ChatResponse


class ScriptedClient:
    """A fake Ollama client that replays a script of responses.

    Each script entry is ``(content, tool_calls)`` where ``tool_calls`` is either
    None or a list of native tool-call dicts. The last entry is repeated if the
    agent loops more times than the script provides.
    """

    default_model = "fake-model"

    def __init__(self, script: List[Tuple[str, Optional[List[Dict[str, Any]]]]]):
        self.script = script
        self.calls: List[Dict[str, Any]] = []

    def _next(self) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
        index = min(len(self.calls) - 1, len(self.script) - 1)
        return self.script[index]

    async def async_chat(self, model, messages, stream=False, tools=None, **kwargs):
        self.calls.append({"model": model, "messages": messages, "tools": tools})
        content, tool_calls = self._next()
        return ChatResponse(
            model=model,
            message=ChatMessage(role="assistant", content=content),
            done=True,
            tool_calls=tool_calls,
        )

    def check_connection(self) -> bool:
        return True


def native_call(name: str, **arguments: Any) -> Dict[str, Any]:
    """Build a native tool-call dict for use in scripts."""
    return {"function": {"name": name, "arguments": arguments}}


@pytest.fixture
def scripted_client():
    """Factory fixture: ``scripted_client([(content, tool_calls), ...])``."""
    return ScriptedClient
