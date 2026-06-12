"""Tests for swarm wiring and real tool execution through the executor."""

from pathlib import Path

from model_constellation.permissions import PermissionManager, PermissionMode
from model_constellation.runtime import AgentRuntime
from model_constellation.tools import ToolExecutor, ToolRegistry, register_builtin_tools
from model_constellation.tools.executor import ExecutionContext

from tests.conftest import ScriptedClient


def make_runtime(client, **kwargs):
    return AgentRuntime(
        client,
        model="fake-model",
        permission_manager=PermissionManager(mode=PermissionMode.ALLOW_ALL),
        session_id="swarm-test",
        **kwargs,
    )


def test_swarm_parallel_reaches_every_agent():
    client = ScriptedClient([("agent done", None)])
    rt = make_runtime(client, tool_names=[])
    specs = [{"name": "a1"}, {"name": "a2"}, {"name": "a3"}]
    result = rt.run_swarm("do the thing", specs, mode="parallel")
    assert result.status == "completed"
    assert len(result.task_results) == 3
    assert all(r["status"] == "success" for r in result.task_results)


def test_swarm_pipeline_threads_output_forward():
    client = ScriptedClient([("step output", None)])
    rt = make_runtime(client, tool_names=[])
    specs = [{"name": "a1"}, {"name": "a2"}]
    result = rt.run_swarm("transform data", specs, mode="pipeline")
    assert result.status == "completed"
    # Second agent's prompt should contain the first agent's output.
    second_call_user = [m for m in client.calls[1]["messages"] if m["role"] == "user"][-1]
    assert "Previous output" in second_call_user["content"]


def test_real_tool_execution_ls(tmp_path: Path):
    (tmp_path / "hello.txt").write_text("hi")
    registry = ToolRegistry()
    register_builtin_tools(registry)
    executor = ToolExecutor(registry, PermissionManager(mode=PermissionMode.ALLOW_ALL))

    result = executor.execute(
        "ls",
        {"path": str(tmp_path)},
        context=ExecutionContext(session_id="t"),
    )
    assert result.success is True
    assert "hello.txt" in result.output


def test_real_tool_execution_denied():
    registry = ToolRegistry()
    register_builtin_tools(registry)
    executor = ToolExecutor(registry, PermissionManager(mode=PermissionMode.DENY_ALL))

    result = executor.execute("ls", {"path": "."}, context=ExecutionContext(session_id="t"))
    assert result.success is False
    assert result.error
