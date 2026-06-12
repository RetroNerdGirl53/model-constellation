"""Tests for the canonical hybrid tool-call parsing/schema module."""

from model_constellation.agent.toolcalling import (
    ToolCall,
    coerce_result_text,
    extract_tool_calls,
    tool_to_schema,
)


def test_extract_native_tool_calls_preferred():
    native = [{"function": {"name": "ls", "arguments": {"path": "."}}}]
    calls = extract_tool_calls("ignored text", native)
    assert calls == [ToolCall(name="ls", arguments={"path": "."})]


def test_extract_text_marker_line_format():
    content = "Let me look.\n[TOOL_CALL]\nbash\ncommand: echo hi"
    calls = extract_tool_calls(content, None)
    assert len(calls) == 1
    assert calls[0].name == "bash"
    assert calls[0].arguments == {"command": "echo hi"}


def test_extract_text_marker_json_format():
    content = '[TOOL_CALL] {"name": "read", "arguments": {"path": "x.txt"}}'
    calls = extract_tool_calls(content, None)
    assert calls[0].name == "read"
    assert calls[0].arguments == {"path": "x.txt"}


def test_extract_returns_empty_when_no_calls():
    assert extract_tool_calls("just a normal answer", None) == []
    assert extract_tool_calls("", []) == []


def test_native_takes_precedence_over_markers():
    native = [{"function": {"name": "ls", "arguments": {}}}]
    content = "[TOOL_CALL]\nbash\ncommand: rm -rf /"
    calls = extract_tool_calls(content, native)
    assert [c.name for c in calls] == ["ls"]


def test_coerce_tool_result_success_and_failure():
    class Result:
        def __init__(self, success, output="", error=None):
            self.success = success
            self.output = output
            self.error = error

    assert coerce_result_text(Result(True, output="hello")) == "hello"
    assert "boom" in coerce_result_text(Result(False, error="boom"))
    assert coerce_result_text("plain") == "plain"
    assert coerce_result_text(None) == ""


def test_tool_to_schema_duck_types():
    class FakeTool:
        name = "demo"
        description = "demo tool"

        def get_parameters_schema(self):
            return {"type": "object", "properties": {"x": {"type": "string"}}}

    schema = tool_to_schema(FakeTool())
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "demo"
    assert schema["function"]["parameters"]["properties"]["x"]["type"] == "string"
