"""Tests for the HTTP backend (FastAPI), driven by a fake Ollama client."""

from typing import Any, Dict, List, Optional

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from model_constellation.api.server import APISettings, create_app  # noqa: E402
from model_constellation.ollama_client import ChatMessage, ChatResponse, ModelInfo  # noqa: E402


class FakeAPIClient:
    """Async fake supporting the methods the API uses."""

    default_model = "fake-model"

    def __init__(self, script: Optional[List] = None):
        # script entries: (content, tool_calls)
        self.script = script or [("hello from fake", None)]
        self.calls = 0

    async def async_chat(self, model, messages, stream=False, tools=None, **kwargs):
        idx = min(self.calls, len(self.script) - 1)
        self.calls += 1
        content, tool_calls = self.script[idx]
        if stream:
            async def gen():
                for piece in content.split():
                    yield ChatResponse(
                        model=model,
                        message=ChatMessage("assistant", piece + " "),
                        done=False,
                    )
            return gen()
        return ChatResponse(
            model=model, message=ChatMessage("assistant", content), done=True,
            tool_calls=tool_calls,
        )

    async def async_list_models(self):
        return [ModelInfo(name="fake-model", model="fake-model", size=123)]

    def check_connection(self):
        return True


def make_client(script=None, **settings_kwargs) -> TestClient:
    settings = APISettings(default_model="fake-model", **settings_kwargs)
    app = create_app(settings, client=FakeAPIClient(script))
    return TestClient(app)


def test_health_and_version():
    c = make_client()
    assert c.get("/health").json() == {"status": "ok"}
    body = c.get("/version").json()
    assert body["name"] == "model-constellation"


def test_list_models():
    c = make_client()
    body = c.get("/v1/models").json()
    assert body["models"][0]["name"] == "fake-model"


def test_chat_with_prompt():
    c = make_client([("the answer is here", None)])
    r = c.post("/v1/chat", json={"prompt": "hi"})
    assert r.status_code == 200
    assert r.json()["content"] == "the answer is here"


def test_chat_requires_prompt_or_messages():
    c = make_client()
    r = c.post("/v1/chat", json={})
    assert r.status_code == 400


def test_run_tools_disabled_by_default():
    c = make_client([("no tools used", None)])
    r = c.post("/v1/run", json={"prompt": "do it", "permission_mode": "allow-all"})
    assert r.status_code == 200
    body = r.json()
    assert body["tools_enabled"] is False
    assert body["tool_executions"] == []


def test_run_tools_enabled_executes_tool(tmp_path):
    # Model asks for ls, then answers.
    script = [
        ("", [{"function": {"name": "ls", "arguments": {"path": str(tmp_path)}}}]),
        ("listed the directory", None),
    ]
    (tmp_path / "a.txt").write_text("x")
    c = make_client(script, allow_tools=True)
    r = c.post(
        "/v1/run",
        json={"prompt": "list", "tools": ["ls"], "permission_mode": "allow-all"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tools_enabled"] is True
    assert body["tool_executions"][0]["tool"] == "ls"
    assert body["tool_executions"][0]["success"] is True


def test_run_rejects_interactive_permission_mode():
    c = make_client(allow_tools=True)
    r = c.post("/v1/run", json={"prompt": "x", "permission_mode": "first-time"})
    assert r.status_code == 400


def test_swarm_endpoint():
    c = make_client([("agent answer", None)])
    r = c.post(
        "/v1/swarm",
        json={
            "task": "summarize",
            "mode": "parallel",
            "permission_mode": "deny-all",
            "agents": [{"name": "a1"}, {"name": "a2"}],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert len(body["results"]) == 2


def test_api_key_auth():
    c = make_client(api_key="secret")
    assert c.get("/v1/models").status_code == 401
    assert c.get("/v1/models", headers={"X-API-Key": "secret"}).status_code == 200
    assert c.get("/v1/models", headers={"Authorization": "Bearer secret"}).status_code == 200


def test_tools_listing():
    c = make_client(allow_tools=True)
    body = c.get("/v1/tools").json()
    assert body["tools_enabled"] is True
    names = [t["function"]["name"] for t in body["tools"]]
    assert "ls" in names and "bash" in names
