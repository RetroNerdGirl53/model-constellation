# model-constellation — Developer Docs (Start Here)

Welcome! These docs are written for someone who knows a little Python and wants to
understand **how this project actually works** — not just what it does.

Read them in order:

1. **[01-overview.md](01-overview.md)** — What this project is, in plain English. The
   mental model you need before reading any code.
2. **[02-architecture.md](02-architecture.md)** — A map of every folder and file, and a
   *very important* warning about which code actually runs vs. which is "built but not
   plugged in yet."
3. **[03-code-walkthrough.md](03-code-walkthrough.md)** — We follow one real command
   (`model-constellation run "hello"`) line by line, from your keyboard to the screen.
4. **[04-python-concepts.md](04-python-concepts.md)** — The Python features this code
   uses that a beginner may not have seen yet (decorators, dataclasses, Pydantic,
   generators, `async`, etc.), each explained with examples *from this codebase*.
5. **[05-glossary.md](05-glossary.md)** — Quick definitions of every term and acronym.
6. **[06-agent-runtime.md](06-agent-runtime.md)** — How the agent, tools, and permission
   frameworks are wired together via `runtime.py`, and how `run` / `interactive` /
   `swarm run` use them (tool calling, permission prompts, cross-model swarms).
7. **[07-backend-api.md](07-backend-api.md)** — Using model-constellation as a backend
   elsewhere: the Python SDK surface and the HTTP API server (FastAPI).

## The 30-second summary

`model-constellation` is a **command-line program** (you type commands in a terminal)
that talks to **[Ollama](https://ollama.com/)** — a tool that runs AI language models on
your own computer. It lets you:

- Chat with a local AI model.
- Save "agents" (named AI configurations) and "swarms" (groups of agents).
- Let the AI run tools (read files, run shell commands) with a permission system.
- Use a colorful terminal UI with themes.

## How to run it (once Ollama is installed and running)

```bash
# Install the project in "editable" mode from the repo root
pip install -e .

# Ask one question
model-constellation run "What is the capital of France?"

# Start a back-and-forth chat
model-constellation interactive
```

If you don't have Ollama, install it from https://ollama.com, then run `ollama serve`
in one terminal and `ollama pull llama2` to download a model.

## A note on honesty

This codebase used to have **two layers**: a smaller part that really ran, and a larger,
advanced `agent/` + `tools/` + `permissions/` framework that was written but **not
connected**. That framework is now **wired in** through a standardized runtime
(`runtime.py`) — `run`, `interactive`, and `swarm run` use it so the model can call
tools (with permission gating) and swarms can span multiple models/servers. See
[06-agent-runtime.md](06-agent-runtime.md) for how it fits together, and
[02-architecture.md](02-architecture.md) for the full file map.
