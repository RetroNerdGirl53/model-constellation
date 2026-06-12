# 5. Glossary

Quick definitions for terms used in this project and its docs. Alphabetical.

### Agent
A saved AI configuration (which model, personality/system prompt, allowed tools). In the
**live** part of this project, an agent is literally a JSON file in
`~/.model-constellation/agents/`. (In the advanced/unplugged layer, it's a Python object —
see `agent/`.)

### async / await
A Python style for code that can pause and let other work happen while waiting (e.g. on the
network). Used mostly in the *unplugged* parts of this project. The live CLI is synchronous.

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
code search). Part of the unplugged tools layer.

### Generator
A function using `yield` to produce values one at a time (streaming). Used for streaming AI
output and download progress.

### Live layer
Our nickname for the code that actually runs today: `core.py`, `ollama_client.py`,
`config.py`, `models.py`, `model_manager.py`, `constants.py`, and the active `ui/` files.

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
flagging dangerous ones like `rm -rf` or `sudo`. Part of the unplugged layer today.

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
the web. Defined in `tools/`; guarded by `permissions/`. Part of the unplugged layer today.

### TUI (Terminal User Interface)
A full-screen, interactive interface inside the terminal (with themes, panels), as opposed to
typing one command at a time. Launched with `model-constellation tui`; built on **pytermgui**.

### Type hint
An annotation like `x: str` or `-> bool` describing expected types. Documentation for humans
and tools; not enforced at runtime. See [chapter 4](04-python-concepts.md).

### Unplugged layer
Our nickname for the advanced, well-written, but **not-yet-connected** code:
`agent/`, `tools/`, `permissions/`. The CLI doesn't call it yet. It's the project's future.

### YAML
A human-friendly config file format (used for `config.yaml`). Like JSON but with less
punctuation and support for comments.
