# 7. Backend for use elsewhere — SDK + HTTP API

There are two supported ways to embed model-constellation in other software:

1. **Python SDK** — import the engine directly.
2. **HTTP API** — run a server and call it from any language/machine.

Both are thin layers over the *same* `AgentRuntime`; nothing is duplicated.

---

## A. Python SDK

The public API is exported from the top-level package (lazily, so plain
`import model_constellation` stays cheap):

```python
from model_constellation import AgentRuntime, OllamaClient, PermissionMode

client  = OllamaClient(base_url="http://localhost:11434")
runtime = AgentRuntime(client, model="llama3.1", permission_mode="allow-all")

# One-shot agentic run (tools + permission gating + loop)
result = runtime.run("List the Python files in this repo and count them")
print(result.content)
for ex in result.tool_executions:
    print(ex["tool"], ex["success"])

# Multi-/cross-model swarm
swarm = runtime.run_swarm(
    "Summarize the project",
    [{"name": "a", "model": "llama3.1"},
     {"name": "b", "model": "qwen2.5", "base_url": "http://other-ollama-host:11434"}],
    mode="parallel",
)
print(swarm.status, [r.get("result") for r in swarm.task_results])

runtime.close()   # release the event loop when done (optional for one-shots)
```

Exported names (see `model_constellation/__init__.py`): `AgentRuntime`, `RuntimeResult`,
`OllamaClient`, `ChatResponse`, `ChatMessage`, `ModelParameters`, `OllamaConnectionError`,
`OllamaModelError`, `ConfigManager`, `load_config`, `ModelConstellationConfig`,
`PermissionManager`, `PermissionMode`, `ToolRegistry`, `ToolExecutor`,
`get_all_builtin_tools`, `register_builtin_tools`, `PrimaryAgent`, `AgentSwarm`,
`SwarmMode`, plus `create_app`/`APISettings` for the server.

### Sync vs async

- `runtime.run(...)` / `runtime.run_swarm(...)` are **synchronous** wrappers (they drive
  a persistent event loop internally) — use these from normal code.
- `await runtime.arun(...)` / `await runtime._arun_swarm(...)` are the **async** cores —
  use these when you're already inside an event loop (the HTTP server does this).

---

## B. HTTP API (FastAPI)

Install the extra and start the server:

```bash
pip install "model-constellation[api]"

# Via the CLI:
model-constellation serve --host 0.0.0.0 --port 8000
# ...or directly:
uvicorn model_constellation.api:app          # configured via MC_* env vars
python -m model_constellation.api
```

### Safety model (important)

A network service that can run `bash`/`write` is dangerous, so the server is
**safe by default**:

- **Tools are OFF** unless you pass `--allow-tools` (or `MC_ALLOW_TOOLS=1`). Without it,
  `/v1/run` still works but executes no tools.
- **No interactive prompts over the wire.** Only the policy modes `allow-all` and
  `deny-all` are accepted; `first-time` / `every-time` return `400` (they need a
  terminal). Default is `deny-all`.
- **Optional API key.** Set `--api-key` / `MC_API_KEY` to require `X-API-Key:` or
  `Authorization: Bearer <key>` on every data endpoint.

### Configuration (env vars)

| Var | Default | Meaning |
|---|---|---|
| `MC_OLLAMA_URL` | `http://localhost:11434` | Ollama server the engine talks to |
| `MC_DEFAULT_MODEL` | `llama3.1` | Model used when a request omits one |
| `MC_ALLOW_TOOLS` | `0` | Master switch for tool execution |
| `MC_PERMISSION_MODE` | `deny-all` | Default policy (`allow-all`/`deny-all`) |
| `MC_API_KEY` | (none) | If set, required on requests |
| `MC_API_HOST` / `MC_API_PORT` | `127.0.0.1` / `8000` | Bind address (for `python -m`) |

### Endpoints

| Method & path | Purpose |
|---|---|
| `GET /health` | Liveness check |
| `GET /version` | Name + version |
| `GET /v1/models` | List models on the Ollama server |
| `GET /v1/tools` | List built-in tool schemas + whether tools are enabled |
| `POST /v1/chat` | Plain chat (no tools) |
| `POST /v1/chat/stream` | Streaming chat (Server-Sent Events) |
| `POST /v1/run` | Agentic run with tools + permission gating |
| `POST /v1/swarm` | Run a task across a multi-/cross-model swarm |

### Examples

```bash
# Plain chat
curl -s localhost:8000/v1/chat \
  -d '{"prompt":"Say hello in 3 words","model":"llama3.1"}'

# Agentic run with tools (server must be started with --allow-tools)
curl -s localhost:8000/v1/run \
  -d '{"prompt":"List the .py files here and count them",
       "tools":["ls","glob"], "permission_mode":"allow-all"}'

# Cross-model swarm
curl -s localhost:8000/v1/swarm \
  -d '{"task":"Brainstorm a project name","mode":"pipeline","permission_mode":"deny-all",
       "agents":[{"name":"ideator","model":"llama3.1"},
                 {"name":"critic","model":"qwen2.5","base_url":"http://other-ollama-host:11434"}]}'

# Streaming chat (SSE)
curl -N localhost:8000/v1/chat/stream -d '{"prompt":"Count to five"}'
```

`/v1/run` response shape:

```json
{
  "content": "...final answer...",
  "model": "llama3.1",
  "iterations": 2,
  "tools_enabled": true,
  "tool_executions": [
    {"tool": "ls", "arguments": {"path": "."}, "success": true, "output": "..."}
  ]
}
```

### Tests

The server is covered by `tests/test_api.py` using FastAPI's `TestClient` and a fake
Ollama client — run with `pytest` (no server or Ollama required).

---

Back to the index: **[README.md](README.md)**.
