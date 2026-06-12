# 4. Python Concepts Used in This Project

This codebase uses several intermediate Python features. Here's each one explained simply,
with a real example **from this project**. If a piece of code ever looks like magic, find
it here.

---

## 1. Decorators (`@something`)

A decorator is a line starting with `@` placed above a function. It **wraps** the function
to add behavior — you don't call it yourself; the library does.

```python
@cli.command()
@click.argument("query", required=False)
@click.option("--model", "-m", type=str)
def run(ctx, query, model):
    ...
```

Here, **Click** uses decorators to register `run` as a terminal sub-command and to declare
its arguments/options. You never call `run()` directly; Click calls it when the user types
`run`. **Mental model:** "decorators attach metadata or behavior to the function below them."

Other decorators you'll see:
- `@dataclass` — auto-generates boilerplate for a data-holding class (see below).
- `@property` — makes a method callable like an attribute (`obj.size_formatted` instead of
  `obj.size_formatted()`).
- `@classmethod` / `@staticmethod` — methods that don't need a specific instance.
- `@abstractmethod` — marks a method that subclasses *must* implement.

---

## 2. Dataclasses (`@dataclass`)

A normal class needs a verbose `__init__`. A **dataclass** writes it for you. From
`ollama_client.py`:

```python
from dataclasses import dataclass

@dataclass
class ChatMessage:
    role: str
    content: str
    images: Optional[List[str]] = None
```

This automatically lets you write `ChatMessage(role="user", content="hi")`. Without
`@dataclass` you'd hand-write an `__init__` storing each field. Dataclasses are used all
over this project for simple "bag of fields" objects (`ModelParameters`, `ChatResponse`,
`ModelInfo`, etc.).

---

## 3. Pydantic models (validation)

Pydantic is like dataclasses **plus automatic validation and type-checking**. The config
system uses it (`models.py`):

```python
from pydantic import BaseModel, Field

class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    default_model: str = "llama2"
    timeout: int = 120000
```

If you load a config file where `timeout` is the text `"abc"`, Pydantic raises a clear
error instead of letting a bad value sneak through. `Field(default_factory=...)` provides a
fresh default each time (important for lists/dicts). This is why `config.py` can trust the
data after `ModelConstellationConfig(**data)` succeeds.

**Dataclass vs Pydantic:** dataclass = lightweight, no validation; Pydantic = heavier,
validates types and values. This project uses dataclasses for internal plumbing and
Pydantic for user-facing config.

---

## 4. Type hints (`: str`, `-> bool`, `Optional`, `List`, `Dict`)

These annotations describe what type a value should be. They **don't change behavior** —
Python doesn't enforce them at runtime — but they document intent and help tools catch bugs.

```python
def chat(self, model: Optional[str], messages: List[Dict[str, str]]) -> ChatResponse:
```

Read it as: "`model` is a string *or* `None`; `messages` is a list of dicts mapping
str→str; this function returns a `ChatResponse`." Common ones:
- `Optional[str]` = "a string, or `None`."
- `List[X]`, `Dict[K, V]` = a list of X, a dict from K to V.
- `Union[A, B]` = "either an A or a B."

---

## 5. Context managers (`with ... as ...`)

A `with` block guarantees setup and cleanup happen, even if an error occurs.

```python
with Progress(SpinnerColumn(), ...) as progress:
    task = progress.add_task("Generating...", total=None)
    response = client.chat(...)
# spinner is automatically stopped/cleaned up here, no matter what
```

Also used for files:

```python
with open(agent_file) as f:
    agent = json.load(f)
# file is automatically closed here
```

**Mental model:** "open something, use it, and it auto-closes when the block ends."

---

## 6. Generators and `yield` (streaming)

A normal function `return`s once. A **generator** uses `yield` to produce a stream of
values lazily, one at a time. This is how streaming AI responses and download progress work
(`ollama_client.py`):

```python
def _stream_chat(self, model, messages, params):
    for response in self._client.chat(model=model, messages=messages, stream=True, ...):
        yield ChatResponse.from_ollama_response(response)
```

The caller loops over it: `for chunk in client.chat(..., stream=True):`. Each `yield`
hands back one chunk as it arrives, instead of waiting for the whole answer. The model-pull
progress bar in `core.py` consumes a generator the same way.

---

## 7. `async` / `await` (concurrency) — mostly in the advanced layer

`async def` defines a function that can pause (`await`) without blocking everything else —
useful for doing many things "at once" (like waiting on several network calls).

```python
async def async_chat(self, model, messages, ...):
    response = await self._async_client.chat(...)
    return ChatResponse.from_ollama_response(response)
```

**Important for this project:** the **live CLI is synchronous** (no `async`). The `async`
code lives mostly in the *unplugged* `agent/`, `tools/`, and `permissions/` folders. So
if you're learning the part that actually runs today, you can mostly skip `async` for now.
Just know: `await x()` means "start x, and pause here until it finishes, letting other
tasks run meanwhile."

---

## 8. `*args` and `**kwargs`

These let a function accept any number of extra positional / keyword arguments.

```python
def chat(self, model, messages, stream=False, parameters=None, **kwargs):
    params = (parameters or ModelParameters()).to_dict()
    params.update(kwargs)   # fold any extra keyword args into the options
```

`**kwargs` collects extra named arguments into a dict named `kwargs`. Here it lets callers
pass through additional Ollama options the wrapper didn't explicitly list.

---

## 9. Exceptions and custom error types

The project defines its **own** exception classes (`ollama_client.py`):

```python
class OllamaConnectionError(Exception):
    pass

class OllamaModelError(Exception):
    pass
```

Then it raises them and catches them specifically:

```python
try:
    response = client.chat(...)
except OllamaConnectionError as e:
    console.print("[red]Connection Error:[/red] ...")
except OllamaModelError as e:
    console.print("[red]Model Error:[/red] ...")
```

Custom exceptions let different failures get different, helpful messages. The
`raise NewError(...) from e` pattern keeps the original error chained for debugging.

---

## 10. Enums (fixed sets of choices)

An `Enum` defines a fixed list of allowed values, so typos become errors (`models.py`):

```python
from enum import Enum

class SwarmMode(str, Enum):
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    PIPELINE = "pipeline"
    ADAPTIVE = "adaptive"
```

`(str, Enum)` means each member is also a real string, so `SwarmMode.PARALLEL == "parallel"`.
This prevents bugs where someone passes `"paralel"` by mistake.

---

## 11. `pathlib.Path` (modern file paths)

Instead of gluing strings with `/`, this project uses `Path` objects (`constants.py`):

```python
from pathlib import Path

MODEL_CONSTELLATION_DIR = Path.home() / ".model-constellation"
DEFAULT_CONFIG_PATH = MODEL_CONSTELLATION_DIR / "config.yaml"
```

The `/` operator joins path parts in a cross-platform way. `Path.home()` is your home
folder. Handy methods: `.exists()`, `.mkdir(parents=True, exist_ok=True)`, `.glob("*.json")`,
`.unlink()` (delete).

---

## 12. JSON files as a database

This project stores agents/swarms/sessions as JSON files (no real database). The pattern
(`core.py`):

```python
# Save
with open(agent_file, "w") as f:
    json.dump(agent_data, f, indent=2)

# Load
with open(agent_file) as f:
    agent = json.load(f)

# Find all
for agent_file in agents_dir.glob("*.json"):
    ...
```

`json.dump` writes a Python dict to a file as text; `json.load` reads it back. `indent=2`
makes the file human-readable.

---

## Where to practice

Open `ollama_client.py` and `core.py` side by side with this guide. Almost every concept
above appears in those two files. Once they make sense, the rest of the codebase will feel
familiar.

Next: **[05-glossary.md](05-glossary.md)** — quick definitions.
