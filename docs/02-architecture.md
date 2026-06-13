# 2. Architecture — The map of the code

This is the most important chapter. By the end you'll know **where everything lives**
and — crucially — **which code actually runs**.

## ⚠️ Read this first: two layers, now connected

This project grew in two stages:

1. **The "core" layer** — the synchronous Click + Rich CLI plumbing (`core.py`,
   `ollama_client.py`, `config.py`, `models.py`). Start here to understand command parsing.
2. **The agent framework** — the `async` `agent/` + `tools/` + `permissions/` subsystems.
   These were originally written but **not connected** to the CLI.

As of the standardization work, layer 2 is **wired into layer 1** through
`runtime.py` (the `AgentRuntime`). `run`, `interactive`, and `swarm run` now use it, so
the model can call tools with permission checks, and swarms run on the real framework.
See **[06-agent-runtime.md](06-agent-runtime.md)** for how that wiring works.

`core.py` reaches the framework lazily (inside the command functions) via
`from model_constellation.runtime import AgentRuntime`, which in turn assembles
`agent/`, `tools/`, and `permissions/`. If you're new, you can still read the core layer
first — but the advanced folders are no longer dead code.

## The folder map

```
model_constellation/            ← repo root
│
├── install.sh                  ← convenience installer script (optional)
│
├── pyproject.toml / setup.py   ← project metadata: name, version, dependencies,
│                                  and the "model-constellation" command definition.
│
├── README.md / SPEC.md / model-constellation.1   ← human docs (SPEC.md is the big design doc)
│
├── agent_tracking/    ← NOT part of the program. Scratch notes/logs (MD + JSON).
│                         Safe to ignore while learning.
│
└── model_constellation/        ← THE ACTUAL PYTHON PACKAGE
    │
    │  ===== THE LIVE LAYER (this is what runs) =====
    ├── core.py            ★ The heart. All CLI commands live here (run, interactive,
    │                        agent, swarm, model, config, tui, serve). ~2050 lines.
    ├── ollama_client.py   ★ The wrapper that actually talks to Ollama over HTTP.
    ├── config.py          ★ Loads/saves settings (config.yaml).
    ├── models.py          ★ Data shapes (Pydantic classes) for config & objects.
    ├── model_manager.py     Helper for model operations + parameter "presets".
    ├── constants.py         All the default values in one place.
    ├── runtime.py         ★ AgentRuntime: wires agent+tools+permissions together
    │                        and bridges async↔sync for the CLI. (NEW)
    ├── __init__.py          Marks the folder as a package; holds __version__.
    ├── __main__.py          Lets you run `python -m model_constellation`.
    │
    │  ===== THE TERMINAL UI =====
    └── ui/
        ├── cli_integration.py  ★ Bridge: the `tui` command calls start_themed_tui() here.
        ├── rich_tui.py         ★ The chat UI that actually launches (SimplifiedTUI).
        └── theme.py            ★ Color themes (8 of them), saved to disk.
    │
    │  ===== THE AGENT FRAMEWORK (wired in via runtime.py) =====
    ├── agent/             ★ Async agent framework (used by the runtime).
    │   ├── base.py            Base class all agents share.
    │   ├── primary.py         "Boss" agent that runs the think→act→observe loop.
    │   ├── sub.py             Worker agents (used by swarms).
    │   ├── swarm.py           Async swarm coordination (parallel/sequential/pipeline).
    │   ├── toolcalling.py     ★ Hybrid native/text-marker tool-call parser. (NEW)
    │   ├── communication.py   Message-passing between agents.
    │   └── registry.py        Keeps track of running agents.
    │
    ├── tools/             ★ Tools the AI can run (used by the runtime).
    │   ├── definitions.py     What a "tool" is (data shapes).
    │   ├── builtin.py         10 built-in tools (bash, read, write, grep, web search...).
    │   ├── registry.py        Catalog of available tools.
    │   ├── executor.py        Runs tools (permission-gated, with timeouts).
    │   └── web_extras.py      Web search/fetch via the Exa API.
    │
    ├── permissions/       ★ "Should the AI be allowed to run this?" (the gate).
    │   ├── core.py            Decision-maker + caching of past answers.
    │   ├── detector.py        Flags dangerous commands (rm -rf, sudo, ...).
    │   ├── rules.py           Allow/deny rules.
    │   └── prompter.py        Asks the user yes/no.
    │
    └── api/               ★ Optional HTTP backend (FastAPI) over the runtime. (NEW)
        ├── server.py          App factory + endpoints (/v1/chat, /v1/run, /v1/swarm…).
        └── __main__.py        `python -m model_constellation.api` launcher.
```

★ = read these first.  ⚠ = legacy; come back later.

## The "live" layer in detail

When you run `model-constellation run "hi"`, only a handful of files are involved:

```
your command
    │
    ▼
core.py          ← Click parses the command, decides "run the run() function"
    │
    ▼
config.py        ← load settings from ~/.model-constellation/config.yaml
    │
    ▼
ollama_client.py ← build the request, POST it to Ollama, parse the reply
    │
    ▼
core.py          ← print the answer with Rich (colors/formatting)
```

That's the whole story for a basic query. The next chapter walks it line by line.

### What `core.py` is built from (two libraries)

- **[Click](https://click.palletsprojects.com/)** — turns Python functions into terminal
  commands. The `@cli.command()` decorators you'll see are Click's way of saying "this
  function is a sub-command."
- **[Rich](https://rich.readthedocs.io/)** — makes terminal output pretty: colors,
  tables, spinners, progress bars, Markdown rendering.

### How agents & swarms are stored (simpler than you'd think)

There is **no clever in-memory object model** in the live path. An "agent" is just a
JSON file:

```
~/.model-constellation/agents/agent_ab12cd34ef56.json
```

```json
{
  "id": "agent_ab12cd34ef56",
  "name": "coder",
  "type": "code",
  "model": "llama2",
  "tools": [],
  "system_prompt": "You are a code generation and analysis assistant.",
  "history": []
}
```

- `agent create` → writes a JSON file.
- `agent list` → reads all JSON files in the folder and prints a table.
- `swarm run` → reads the swarm's JSON and hands the agents to `runtime.run_swarm(...)`,
  which drives the real `AgentSwarm` (`agent/swarm.py`). Parallel mode runs the agents
  concurrently via `asyncio.gather`; pipeline/sequential modes are also supported, and
  agents can target different models/hosts (cross-model swarms).

## How is it launched?

| How you'd trigger it | What happens |
|---|---|
| `model-constellation ...` (installed command) | Runs `core.py` `main()` — `pyproject.toml` points here. |
| `python -m model_constellation` | `__main__.py` → `core.main()`. |
| `model-constellation serve` / `python -m model_constellation.api` | Starts the HTTP API (FastAPI) over the same engine. |

**Takeaway:** no matter how it's launched, execution lands in `core.py` (or, for the
server, in `api/server.py`, which calls the same runtime).

## The TUI layer

`model-constellation tui` opens a full-screen interface. The path is:

```
core.py  →  ui/cli_integration.py : start_themed_tui()  →  ui/rich_tui.py : SimplifiedTUI
```

It's built on **pytermgui**, themed via `ui/theme.py`. (Earlier versions of the project
carried a second, unused generation of UI modules — `terminal.py`, `screens*.py`,
`widgets.py`, `dialogs.py` — which have since been removed.)

## So what is all that `agent/` `tools/` `permissions/` code for?

It's the system that lets the AI **act**: spin up agents, run tools (read files, execute
commands, search), and gate those actions behind permission checks. It is now connected to
the CLI through `runtime.py` — when you run `model-constellation run "..."` (without
`--no-tools`), this is the code that executes. Read
**[06-agent-runtime.md](06-agent-runtime.md)** for the guided tour.

The new glue files to know:

- `runtime.py` — `AgentRuntime`, the one place that assembles agent + tools + permissions
  and bridges async↔sync for the CLI.
- `agent/toolcalling.py` — the single hybrid tool-call parser/schema builder shared by all
  agents.

Next: **[03-code-walkthrough.md](03-code-walkthrough.md)** — one command, line by line.
