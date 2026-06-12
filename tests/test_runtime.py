"""Tests for the standardized AgentRuntime (the integration layer)."""

import pytest

from model_constellation.permissions import PermissionManager, PermissionMode
from model_constellation.runtime import AgentRuntime, TerminalPermissionPrompter

from tests.conftest import ScriptedClient, native_call


def make_runtime(client, mode=PermissionMode.ALLOW_ALL, **kwargs):
    pm = PermissionManager(mode=mode)
    return AgentRuntime(
        client,
        model="fake-model",
        permission_manager=pm,
        session_id="test",
        **kwargs,
    )


def test_plain_answer_no_tools_requested():
    client = ScriptedClient([("The answer is 42.", None)])
    rt = make_runtime(client, tool_names=["ls"])
    result = rt.run("what is the answer?")
    assert result.content == "The answer is 42."
    assert result.tool_executions == []
    assert result.iterations == 1


def test_native_tool_call_then_final_answer():
    client = ScriptedClient(
        [
            ("", [native_call("ls", path=".")]),
            ("Here are the files.", None),
        ]
    )
    rt = make_runtime(client, tool_names=["ls"])
    result = rt.run("list files")
    assert result.content == "Here are the files."
    assert result.iterations == 2
    assert result.tool_executions[0]["tool"] == "ls"
    assert result.tool_executions[0]["success"] is True
    # The model must have been offered the native schema for ls.
    assert client.calls[0]["tools"]
    assert client.calls[0]["tools"][0]["function"]["name"] == "ls"


def test_deny_all_blocks_tool_but_loop_continues():
    client = ScriptedClient(
        [
            ("", [native_call("ls", path=".")]),
            ("Could not list, permission denied.", None),
        ]
    )
    rt = make_runtime(client, mode=PermissionMode.DENY_ALL, tool_names=["ls"])
    result = rt.run("list files")
    assert result.tool_executions[0]["success"] is False
    assert "deny" in result.tool_executions[0]["output"].lower()


def test_unknown_requested_tool_is_filtered_out():
    client = ScriptedClient([("hi", None)])
    rt = make_runtime(client, tool_names=["ls", "does_not_exist"])
    assert "ls" in rt.tool_names
    assert "does_not_exist" not in rt.tool_names


def test_enable_tools_false_offers_no_tools():
    client = ScriptedClient([("hi", None)])
    rt = make_runtime(client, tool_names=["ls"], enable_tools=False)
    assert rt.tool_names == []
    rt.run("hi")
    assert client.calls[0]["tools"] is None


def test_agent_unavailable_tool_reports_clearly():
    # Model asks for a tool the agent doesn't have access to.
    client = ScriptedClient(
        [
            ("", [native_call("write", path="x", content="y")]),
            ("done", None),
        ]
    )
    rt = make_runtime(client, tool_names=["ls"])  # write not granted
    result = rt.run("write a file")
    assert "not available" in result.tool_executions[0]["output"].lower()


def test_runtime_reusable_across_multiple_calls():
    # Reusing one runtime for several calls must not break the event loop
    # (regression: httpx async client binds to the first loop).
    client = ScriptedClient([("answer", None)])
    rt = make_runtime(client, tool_names=[])
    first = rt.run("one")
    loop_after_first = rt._loop
    second = rt.run("two")
    assert first.content == "answer"
    assert second.content == "answer"
    assert rt._loop is loop_after_first
    assert not rt._loop.is_closed()
    # run_swarm on the same runtime must also reuse the loop.
    swarm_result = rt.run_swarm("t", [{"name": "a"}], mode="parallel")
    assert swarm_result.status == "completed"
    rt.close()
    assert rt._loop is None


def test_terminal_prompter_remember_caches_allow(monkeypatch):
    pm = PermissionManager(mode=PermissionMode.FIRST_TIME)
    prompter = TerminalPermissionPrompter(pm)
    pm.set_prompt_callback(prompter)

    inputs = iter(["a"])  # "always"
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(inputs))

    rt = AgentRuntime(
        ScriptedClient([("", [native_call("ls", path=".")]), ("done", None)]),
        model="fake-model",
        permission_manager=pm,
        tool_names=["ls"],
        session_id="sess-remember",
    )
    result = rt.run("list")
    assert result.tool_executions[0]["success"] is True
    # Second, separate check should now hit the cache (no input needed).
    decision = pm.check_permission("ls", {"path": "."}, category="file", session_id="sess-remember")
    assert decision.allowed is True
