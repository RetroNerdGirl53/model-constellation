# 5. Glossary

Quick definitions for terms used in this project and its docs. Alphabetical.

### Agent
A saved AI configuration (which model, personality/system prompt, allowed tools). Saved
agents are JSON files in `~/.model-constellation/agents/`; at runtime an agent is a Python
object in `agent/` driven by the `AgentRuntime` (see [chapter 6](06-agent-runtime.md)).

### async / await
A Python style for code that can pause and let other work happen while waiting (e.g. on the
network). The `agent/` framework and HTTP API are async; the CLI is synchronous and bridges
to the async engine via `AgentRuntime` (see [chapter 6](06-agent-runtime.md)).

### AgentRuntime
The standardized engine (`runtime.py`) that wires the agent, tools, and permission systems
together and bridges async↔sync. The CLI, SDK, and HTTP API all run through it. See
[chapter 6](06-agent-runtime.md).

### CLI (Command-Line Interface)
A program you operate by typing text commands in a terminal. This entire project is a CLI.

### Click
The Python library that turns functions into terminal commands. The `@cli.command()` and
`@click.option()` decorators in `core.py` are Click.

### Config (configuration)
Your settings, stored in `~/.model-constellation/config.yaml`. Loaded/validated by
`config.py` using Pydantic models from `models.py`.

### Context manager
A `with ... as ...:` block that auto-handles setup and cleanup (closing files, stopping
spinners). See [chapter 4](04-python-concepts.md).

### Dataclass
A class with auto-generated boilerplate (`@dataclass`), used for simple data-holding objects
like `ChatMessage` and `ModelParameters`.

### Decorator
A `@name` line above a function that adds behavior to it. See [chapter 4](04-python-concepts.md).

### Enum
A fixed set of named choices (e.g. `SwarmMode.PARALLEL`). Prevents invalid values.

### Exa
A third-party web search/API used by the web tools in `tools/web_extras.py` (search, fetch,
code search).

### Generator
A function using `yield` to produce values one at a time (streaming). Used for streaming AI
output and download progress.

### HTTP API
The optional FastAPI server (`model_constellation/api/`) that exposes the engine over HTTP
for use by other apps/languages. Safe-by-default (tools opt-in). See
[chapter 7](07-backend-api.md).

### Model
A specific AI "brain" run by Ollama, e.g. `llama2`, `mistral`, `codellama`. You choose which
one with `--model` or in config.

### ModelParameters
The knobs that control AI output: `temperature` (creativity), `top_p`/`top_k` (word-choice
limits), `repeat_penalty`, context size, etc. Defined in `ollama_client.py` (and again as a
Pydantic version in `models.py`).

### Ollama
The **separate program** that actually runs AI models on your machine. This project is a
*client* that sends requests to it (default address `http://localhost:11434`). Not included —
install it from https://ollama.com.

### Permission system
The mechanism (in `permissions/`) that decides whether the AI may run a given tool/command,
flagging dangerous ones like `rm -rf` or `sudo`. The single authority for tool gating,
enforced by the tool executor. Modes: first-time / every-time / allow-all / deny-all.

### Prompt
The text sent to the AI. A **system prompt** is a hidden instruction that shapes the AI's
behavior ("You are a helpful coding assistant").

### Pydantic
A library for data classes **with validation**. Used for configuration so bad settings are
caught early. See [chapter 4](04-python-concepts.md).

### Rich
The Python library that makes terminal output colorful and formatted (tables, spinners,
Markdown). The `console.print("[red]...[/red]")` calls are Rich.

### Session
A saved conversation history, stored as JSON in `~/.model-constellation/sessions/`. Lets you
resume a chat with `--session`.

### Streaming
Receiving the AI's answer (or a download's progress) piece by piece as it's produced, rather
than all at once. Implemented with generators / `yield`.

### Swarm
A group of agents working on the same task. Modes: **parallel** (all at once — though in the
live code it's actually a simple loop), **sequential** (one after another), **pipeline**
(each agent's output feeds the next), **adaptive** (chooses a strategy). Stored as JSON;
executed in `core.py`'s `swarm_run`.

### System prompt
See **Prompt**.

### TARS
The project's **old name**. You'll see it in `tars_cli.py` and the `TARS_DIR` alias in
`constants.py`. It's kept only for backward compatibility — same program.

### Token
A word-piece — the unit AI models read and generate text in. `response.eval_count` reports
how many tokens were generated.

### Tool
An action the AI can take in the real world: read/write files, run shell commands, search
the web. Defined in `tools/`; gated by `permissions/`; offered to the model by the
`AgentRuntime`. Tool calling is hybrid (native Ollama tools + `[TOOL_CALL]` text fallback).

### TUI (Terminal User Interface)
A full-screen, interactive interface inside the terminal (with themes, panels), as opposed to
typing one command at a time. Launched with `model-constellation tui`; built on **pytermgui**.

### Type hint
An annotation like `x: str` or `-> bool` describing expected types. Documentation for humans
and tools; not enforced at runtime. See [chapter 4](04-python-concepts.md).

### SDK
The public Python API exported from the top-level package
(`from model_constellation import AgentRuntime, OllamaClient, ...`) for embedding the engine
in other code. See [chapter 7](07-backend-api.md).

### YAML
A human-friendly config file format (used for `config.yaml`). Like JSON but with less
punctuation and support for comments.
