# 1. Overview — What is this, really?

## The big picture

Imagine you have an AI chatbot running on your own laptop (that's **Ollama**).
`model-constellation` is a **friendly front door** to that chatbot. Instead of writing
code to talk to the AI, you type simple commands in your terminal.

```
   You (in a terminal)
        │
        │  type:  model-constellation run "Tell me a joke"
        ▼
┌──────────────────────────┐
│   model-constellation    │   ← this project (Python)
│  (parses your command,   │
│   formats the request)   │
└──────────────────────────┘
        │
        │  sends the question over HTTP
        ▼
┌──────────────────────────┐
│         Ollama           │   ← separate program, runs the AI model
│  (runs e.g. "llama2")    │
└──────────────────────────┘
        │
        │  AI's answer comes back
        ▼
   Printed nicely in your terminal
```

The project **does not contain an AI model itself**. It is a *client* — a program that
sends requests to Ollama and displays the responses. Ollama does the heavy AI work.

## What can it do?

| Feature | What it means | Command example |
|---|---|---|
| **Run a query** | Ask the AI one question, get one answer | `model-constellation run "..."` |
| **Interactive chat** | A back-and-forth conversation that remembers context | `model-constellation interactive` |
| **Agents** | Save a named AI setup (which model, which personality) | `model-constellation agent create coder` |
| **Swarms** | A group of agents that tackle a task together | `model-constellation swarm run team "..."` |
| **Models** | List / download AI models through Ollama | `model-constellation model pull mistral` |
| **Config** | Settings stored in a YAML file | `model-constellation config show` |
| **TUI** | A full-screen colorful terminal interface with themes | `model-constellation tui` |

## Key vocabulary (just enough to start)

- **CLI** = *Command-Line Interface*. A program you control by typing text commands,
  as opposed to clicking buttons. This whole project is a CLI.
- **Ollama** = the separate program that actually runs AI models locally. We talk to it.
- **Model** = a specific AI brain, e.g. `llama2`, `mistral`, `codellama`. You pick which one.
- **Agent** = a saved configuration: "use model X, with personality Y, allowed to use
  tools Z." In this project, an agent is literally just a **JSON file on disk**.
- **Swarm** = several agents grouped together to work on the same task (in parallel,
  one after another, or in a chain).
- **Tool** = an action the AI can take in the real world — read a file, run a shell
  command, search the web. Tools are guarded by a **permission system**.
- **Prompt** = the text you send to the AI. A **system prompt** is a hidden instruction
  that sets the AI's behavior ("You are a helpful coding assistant").

## Where does it store things?

When you use it, the program creates a hidden folder in your home directory:

```
~/.model-constellation/
├── config.yaml        ← your settings
├── agents/            ← one JSON file per agent you create
├── swarms/            ← one JSON file per swarm
├── sessions/          ← saved chat histories
└── logs/              ← log files
```

`~` means "your home folder" (e.g. `/home/yourname` on Linux). A folder starting with
`.` is "hidden" — it won't show up in a normal file listing unless you ask for hidden files.

## The mental model to keep

> **model-constellation is a translator and organizer.** You speak in simple commands;
> it translates them into properly-formatted requests for Ollama, manages your saved
> agents/swarms/settings as files on disk, and prints the results back nicely.

Next: **[02-architecture.md](02-architecture.md)** — the map of the code itself.
