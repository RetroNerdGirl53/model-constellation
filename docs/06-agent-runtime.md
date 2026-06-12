# 6. The Agent Runtime (tools + permissions, wired in)

Earlier chapters warned that `agent/`, `tools/`, and `permissions/` were built but
**not connected** to the CLI. That's no longer true. This chapter explains the
**standardized runtime** that wires them together and how the CLI now uses it.

If any older notes describe `agent/`, `tools/`, or `permissions/` as "not connected,"
treat this chapter as the correction — they're wired in now.

## The one file that ties it together: `runtime.py`

`model_constellation/runtime.py` is the **standard assembly point**. Instead of every
command building agents, tools, and permissions by hand (and doing it slightly
differently each time), they all go through `AgentRuntime`.

```python
from model_constellation.runtime import AgentRuntime

runtime = AgentRuntime.from_config(config)        # build everything from config.yaml
result = runtime.run("List the .py files here")   # returns a RuntimeResult
print(result.content)
for ex in result.tool_executions:
    print(ex["tool"], ex["success"])
```

### What `AgentRuntime` assembles for you

```
AgentRuntime
├── ToolRegistry              ← all built-in tools registered (bash, read, ls, grep…)
├── PermissionManager         ← the SINGLE authority for "may this tool run?"
│     └── TerminalPermissionPrompter  ← asks you y/n/always, shows a danger rating
├── ToolExecutor              ← runs a tool, but only after the PermissionManager says ok
└── PrimaryAgent              ← the agent loop, wired to the Ollama client + executor
```

You get a consistent stack every time, plus three things that used to be missing or
inconsistent:

1. **One async/sync boundary.** The agent framework is `async`; the CLI is plain
   synchronous code. `runtime.run(...)` and `runtime.run_swarm(...)` call
   `asyncio.run(...)` for you, so commands never touch the event loop.
2. **One permission authority.** *All* tool gating happens inside the `ToolExecutor`'s
   `PermissionManager`. Agents no longer gate tools themselves, so there's no
   double-prompting and no way to bypass the check.
3. **Hybrid tool calling.** The runtime passes real JSON tool schemas to Ollama
   (native function calling). For models that don't support that, the agents fall back
   to parsing `[TOOL_CALL]` text markers. Both paths funnel through one parser in
   `agent/toolcalling.py`, so behavior is identical everywhere.

## The agent loop, step by step

When you call `runtime.run("list the files")`, here's what happens inside
`PrimaryAgent.process` (in `agent/primary.py`):

```
1. Add your message to the conversation.
2. Ask the model (async_chat), passing the tool schemas.
3. Did the model request any tools?  (native tool_calls, or [TOOL_CALL] markers)
      NO  → we're done; return the text.
      YES → for each requested tool:
              - ToolExecutor.execute(...)        ← permission check happens HERE
              - add the tool's result back into the conversation
            loop back to step 2 (so the model can use the result)
4. Stop when the model stops asking for tools (or max_iterations is hit).
```

This is the standard "agentic loop": think → act (tool) → observe (result) → repeat.

## How the CLI uses it

| Command | Behavior |
|---|---|
| `run "..."` | Goes through the runtime **with tools** by default. Add `--no-tools` for plain chat. |
| `run --no-tools "..."` | The old simple single-shot chat (no tools, no agent loop). |
| `interactive` | Tool-enabled chat loop by default (one persistent agent across turns). `--no-tools` for the classic loop. |
| `swarm run <id> "task"` | Runs through the real `AgentSwarm`. If the swarm has `shared_tools`, its agents use them. |

Useful flags on `run` / `interactive`:

- `--agent <name|id|type>` — use a saved agent's model / system prompt / tools.
- `--permission-mode first-time|every-time|allow-all|deny-all` — how tools are gated.
- `--model <name>` — pick the Ollama model.

### Permission modes

| Mode | What it does |
|---|---|
| `first-time` (default) | Ask once per unique tool+target, then remember for the session. |
| `every-time` | Ask before every single tool execution. |
| `allow-all` | Never ask (useful for trusted, non-interactive runs). |
| `deny-all` | Block every tool (the model still answers, just without tools). |

When a prompt appears, you'll see a **danger rating** (safe → critical) computed by
`permissions/detector.py`, which flags risky commands like `rm -rf`, `sudo`, or writes
to system paths. Answer `y` (yes, once), `n` (no), or `a` (always, remembered).

> ⚠️ **Tool calling needs a capable model.** Native function calling works well with
> models like `llama3.1`, `qwen2.5`, or `mistral`. Small or older models (including
> `llama2`) may not emit clean tool calls — the hybrid fallback helps, but for reliable
> tool use, pick a tool-trained model with `--model`.

## What changed in the framework code (for the curious)

Standardizing required fixing real mismatches between the three subsystems:

- **`ollama_client.py`** — `chat`/`async_chat` now accept `tools=` and surface
  `response.tool_calls` (normalized to plain dicts).
- **`agent/toolcalling.py`** (new) — the single hybrid parser + schema builder, used by
  both the primary agent and sub-agents (they previously parsed tool calls *differently*).
- **`agent/primary.py` / `agent/sub.py`** — now use the real **async** client and the
  real **synchronous** executor correctly (previously they `await`ed a sync executor and
  expected dict responses from a sync client — neither worked).
- **`agent/swarm.py`** — swarm agents now receive the Ollama client and tool executor.
  Previously the swarm called `execute_task(task, None, None)`, so swarm agents could
  **never reach the model at all** — a silent, total no-op. That bug is fixed.
- **`tools/executor.py`** — the SIGALRM timeout no longer crashes when run off the main
  thread; it degrades to "no hard timeout" instead.

## Testing it without Ollama

The suite in `tests/` uses a scripted fake client (`tests/conftest.py`) so the whole
loop — native calls, text-marker fallback, permission allow/deny, swarms, and real tool
execution — is verified without a running server:

```bash
pip install -e ".[dev]"
pytest
```

Next: back to **[02-architecture.md](02-architecture.md)** for the full file map.
