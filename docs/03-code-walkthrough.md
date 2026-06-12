# 3. Code Walkthrough — One command, start to finish

Let's trace exactly what happens when you type:

```bash
model-constellation run "What is the capital of France?"
```

We'll follow the code in the order it actually executes. Open the mentioned files
alongside this guide. Line numbers are approximate — search for the function names.

---

## Step 0: How does typing `model-constellation` start Python?

When you ran `pip install -e .`, the project's `pyproject.toml` declared:

```toml
[project.scripts]
model-constellation = "model_constellation.core:main"
```

This tells pip: *"create a terminal command called `model-constellation`; when run, call
the `main` function inside `model_constellation/core.py`."* So your shell command becomes
a call to `core.main()`.

---

## Step 1: `core.py` → `main()` and `cli()`

At the bottom of `core.py`:

```python
def main() -> None:
    cli(obj={})
```

`cli` is a **Click command group**. Click is a library that reads `sys.argv` (the words
you typed) and figures out which sub-command to run. Here it sees the word `run`, so it
routes to the `run()` function.

First, though, the group function itself runs (it's decorated with `@click.group()`):

```python
@click.group()
@click.option("--debug", is_flag=True, ...)
@click.option("--config", ...)
@click.pass_context
def cli(ctx, debug, config):
    ctx.ensure_object(dict)
    ctx.obj["logger"] = setup_logging(...)
    ctx.obj["config_manager"] = ConfigManager(config) if config else get_config()
    ctx.obj["config"] = ctx.obj["config_manager"].load()   # ← loads config.yaml
```

**What's happening:**
- `ctx` (context) is a little box Click passes around so commands can share data.
- It sets up logging and **loads your configuration** from `~/.model-constellation/config.yaml`
  into `ctx.obj["config"]`. (See `config.py` — if the file doesn't exist, defaults are used.)
- `@click.pass_context` is what gives this function the `ctx` argument.

---

## Step 2: `core.py` → `run()`

Click now calls the `run` command, passing your query string:

```python
@cli.command()
@click.argument("query", required=False)
@click.option("--model", "-m", ...)
@click.option("--temperature", ...)
# ...more options...
@click.pass_context
def run(ctx, query, agent, model, temperature, top_p, swarm, parallel, timeout, no_tools, permission_mode):
    config = ctx.obj["config"]

    if not query:
        # No question given → drop into interactive chat instead
        _run_interactive(ctx)
        return
```

- Each `@click.option(...)` line defines a flag you *could* pass (like `--model llama2`).
  If you don't pass it, the value is `None`.
- `query` holds `"What is the capital of France?"`.

### Choosing the model and validating numbers

```python
    config_model = config.ollama.default_model if config else "llama2"
    use_model = model or config_model      # command-line --model wins, else config default

    if temperature is not None and not (0.0 <= temperature <= 2.0):
        console.print("[red]Error:[/red] temperature must be between 0.0 and 2.0")
        sys.exit(1)
```

- `model or config_model` is a common Python trick: if `model` is `None` (falsy), use
  `config_model` instead.
- `console.print("[red]...[/red]")` is **Rich** markup — the `[red]` tags become actual
  red text in your terminal.
- `sys.exit(1)` quits the program with an error code.

### Packaging the AI settings

```python
    params = ModelParameters(
        temperature=temperature if temperature is not None else config.parameters.temperature ...,
        top_p=top_p if top_p is not None else config.parameters.top_p ...,
    )
```

`ModelParameters` (from `ollama_client.py`) is a **dataclass** bundling the knobs that
control the AI's output (creativity, etc.). See [04-python-concepts.md](04-python-concepts.md)
for what a dataclass is.

---

## Step 3: Create the Ollama client and send the request

```python
    try:
        client = OllamaClient(
            base_url=config.ollama.base_url,
            default_model=use_model,
        )

        console.print(f"[cyan]Model:[/cyan] {use_model}")
        console.print(f"[cyan]Query:[/cyan] {query}")

        with Progress(SpinnerColumn(), TextColumn(...), console=console) as progress:
            task = progress.add_task("[cyan]Generating response...", total=None)

            response = client.chat(
                model=use_model,
                messages=[{"role": "user", "content": query}],
                parameters=params,
            )
            progress.update(task, completed=True)
```

**What's happening:**
- `OllamaClient(...)` (in `ollama_client.py`) is our wrapper around the `ollama` Python
  library. Creating it just stores the settings; no network call yet.
- `with Progress(...) as progress:` shows a **spinner** while we wait. The `with` block
  guarantees the spinner is cleaned up afterward (see context managers in chapter 4).
- `client.chat(...)` is the real network call. `messages` is a list of message
  dictionaries — the standard chat format: each has a `role` (`"user"`, `"assistant"`,
  or `"system"`) and `content`.

### Inside `ollama_client.py` → `chat()`

```python
def chat(self, model, messages, stream=False, parameters=None, **kwargs):
    model = self._ensure_model(model)
    params = (parameters or ModelParameters()).to_dict()   # knobs → plain dict

    formatted_messages = []
    for msg in messages:
        if isinstance(msg, dict):
            formatted_messages.append(msg)
        elif isinstance(msg, ChatMessage):
            formatted_messages.append(msg.to_dict())

    try:
        response = self._client.chat(           # ← the actual Ollama library call
            model=model, messages=formatted_messages, stream=False, options=params,
        )
        return ChatResponse.from_ollama_response(response)
    except Exception as e:
        if "not found" in str(e).lower():
            raise OllamaModelError(f"Model '{model}' not found") from e
        raise OllamaConnectionError(f"Failed to connect to Ollama: {e}") from e
```

**What's happening:**
- `self._client` is the real `ollama.Client` from the third-party `ollama` package. *Our*
  class wraps it so the rest of our code has a clean, consistent interface.
- `ChatResponse.from_ollama_response(response)` converts Ollama's reply into **our own**
  `ChatResponse` dataclass. This is a defensive pattern: Ollama might return a dict or a
  Pydantic object depending on version, so we normalize it into one predictable shape.
- The `except` block turns low-level errors into our own friendly exception types
  (`OllamaModelError`, `OllamaConnectionError`) so `core.py` can show helpful messages.
  `raise ... from e` keeps the original error attached for debugging.

---

## Step 4: Back in `run()` — print the answer

```python
        console.print()
        console.print("[bold green]Response:[/bold green]")
        console.print(response.message.content)        # ← the AI's actual answer

        if response.eval_count is not None:
            console.print(f"\n[dim]Tokens: {response.eval_count} | Model: {response.model}[/dim]")
```

- `response.message.content` is the text the AI produced.
- `response.eval_count` is how many tokens (word-pieces) it generated — printed dimly as
  a stats line.

### If something went wrong

```python
    except OllamaConnectionError as e:
        console.print(f"[red]Connection Error:[/red] {e}")
        console.print("[yellow]Make sure Ollama is running:[/yellow]")
        console.print("  ollama serve")
        sys.exit(1)
    except OllamaModelError as e:
        console.print(f"[red]Model Error:[/red] {e}")
        console.print("  model-constellation model list")
        sys.exit(1)
```

This is why those custom exception types matter: each gets a tailored, helpful message.
If Ollama isn't running, you're told to start it; if the model name is wrong, you're told
how to list available models.

---

## The whole journey on one page

```
shell: model-constellation run "..."
   │
   ▼
core.main()  →  Click parses argv
   │
   ▼
core.cli()   →  load config.yaml into ctx.obj["config"]
   │
   ▼
core.run()   →  pick model, validate options, build ModelParameters
   │
   ▼
OllamaClient.chat()  →  format messages, call the ollama library, POST to Ollama
   │                     normalize the reply into ChatResponse
   ▼
core.run()   →  console.print(response.message.content)   ← you see the answer
```

---

## Bonus: how `interactive` differs

`model-constellation interactive` (function `interactive` → `_run_interactive_loop` in
`core.py`) is the same idea in a **loop**:

1. Print a welcome panel.
2. `while True:` — read a line of your input.
3. If it starts with `/` (like `/help`, `/exit`), handle it as a command.
4. Otherwise append `{"role": "user", "content": your_text}` to a `history` list and
   call `client.chat(messages=history)`.
5. Append the AI's reply to `history` too — that's how it "remembers" the conversation:
   the *entire* history is re-sent every turn.

The AI itself is stateless; **the conversation memory is just a growing Python list** that
we re-send each time. That's a key insight into how all chat apps work.

Next: **[04-python-concepts.md](04-python-concepts.md)** — the Python features used here.
