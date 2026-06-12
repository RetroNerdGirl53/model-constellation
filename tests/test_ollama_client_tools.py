"""Tests for native tool-call surfacing in the Ollama client wrapper."""

from model_constellation.ollama_client import ChatResponse, _normalize_tool_calls


class _Func:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _Call:
    def __init__(self, name, arguments):
        self.function = _Func(name, arguments)


class _Msg:
    role = "assistant"
    content = "hi"

    def __init__(self, tool_calls=None):
        self.tool_calls = tool_calls


class _Resp:
    model = "m"
    done = True

    def __init__(self, tool_calls=None):
        self.message = _Msg(tool_calls)


def test_normalize_handles_objects():
    out = _normalize_tool_calls([_Call("ls", {"path": "."})])
    assert out == [{"function": {"name": "ls", "arguments": {"path": "."}}}]


def test_normalize_handles_dicts_and_bad_args():
    out = _normalize_tool_calls([{"function": {"name": "x", "arguments": "not-a-dict"}}])
    assert out == [{"function": {"name": "x", "arguments": {}}}]


def test_normalize_empty():
    assert _normalize_tool_calls(None) is None
    assert _normalize_tool_calls([]) is None


def test_from_ollama_response_object_with_tool_calls():
    resp = ChatResponse.from_ollama_response(_Resp([_Call("read", {"path": "a"})]))
    assert resp.message.content == "hi"
    assert resp.tool_calls == [{"function": {"name": "read", "arguments": {"path": "a"}}}]


def test_from_ollama_response_dict_without_tool_calls():
    resp = ChatResponse.from_ollama_response(
        {"model": "m", "message": {"role": "assistant", "content": "yo"}, "done": True}
    )
    assert resp.tool_calls is None
    assert resp.message.content == "yo"
