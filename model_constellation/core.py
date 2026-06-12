"""Core CLI functionality for model-constellation."""

import json
import logging
import os
import signal
import sys
import uuid
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING, cast
from typing import Dict, List, Optional, Union

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.panel import Panel
from rich import box

from model_constellation import constants
from model_constellation.config import ConfigManager, load_config
from model_constellation.model_manager import DEFAULT_PRESETS, ModelManager
from model_constellation.models import (
    AgentType,
    PermissionMode,
    SwarmMode,
)
from model_constellation.ollama_client import (
    ChatMessage,
    OllamaClient,
    OllamaConnectionError,
    OllamaModelError,
    ModelParameters,
)
from model_constellation.ui.cli_integration import (
    get_tui_command_group,
    start_themed_tui,
)

if TYPE_CHECKING:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.styles import Style

    PROMPTTOOLKIT_AVAILABLE = True
except ImportError:
    PROMPTTOOLKIT_AVAILABLE = False
    PromptSession = None
    FileHistory = None
    AutoSuggestFromHistory = None


console = Console()

SESSION_HISTORY_DIR = Path.home() / ".model-constellation" / "sessions"
SESSION_HISTORY_DIR.mkdir(parents=True, exist_ok=True)

AGENTS_DIR = Path.home() / ".model-constellation" / "agents"
SWARMS_DIR = Path.home() / ".model-constellation" / "swarms"


def _get_swarms_dir() -> Path:
    """Get or create the swarms directory."""
    SWARMS_DIR.mkdir(parents=True, exist_ok=True)
    return SWARMS_DIR


def _get_agents_dir() -> Path:
    """Get or create the agents directory."""
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    return AGENTS_DIR


def _generate_agent_id() -> str:
    """Generate a unique agent ID."""
    return f"agent_{uuid.uuid4().hex[:12]}"


_session_store: Dict[str, List[Dict[str, str]]] = {}


def setup_logging(level: str = "info") -> logging.Logger:
    """Setup logging for the application."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format=constants.DEFAULT_LOG_FORMAT,
    )
    return logging.getLogger("model_constellation")


def get_config() -> ConfigManager:
    """Get configuration manager instance."""
    return ConfigManager()


def get_ollama_client(config=None) -> OllamaClient:
    """Get Ollama client instance."""
    if config is None:
        config = get_config().load()
    return OllamaClient(
        base_url=config.ollama.base_url,
        default_model=config.ollama.default_model,
    )


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config file",
)
@click.pass_context
def cli(ctx: click.Context, debug: bool, config: Optional[Path]) -> None:
    """model-constellation - Ollama-powered CLI AI agent framework."""
    ctx.ensure_object(dict)
    log_level = "debug" if debug else "info"
    ctx.obj["logger"] = setup_logging(log_level)
    ctx.obj["config_manager"] = ConfigManager(config) if config else get_config()
    ctx.obj["config"] = ctx.obj["config_manager"].load()


@cli.command()
@click.argument("query", required=False)
@click.option("--agent", "-a", type=str, help="Agent type (primary, code, research)")
@click.option("--model", "-m", type=str, help="Ollama model to use")
@click.option("--temperature", type=float, help="Set temperature (0.0-2.0)")
@click.option("--top-p", type=float, help="Set top_p (0.0-1.0)")
@click.option("--swarm", type=str, help="Run with agent swarm")
@click.option("--parallel", is_flag=True, help="Enable parallel execution")
@click.option("--timeout", type=int, help="Request timeout in seconds")
@click.option("--no-tools", is_flag=True, help="Disable tool execution")
@click.option(
    "--permission-mode",
    type=click.Choice(constants.PERMISSION_MODES),
    help="Permission mode",
)
@click.pass_context
def run(
    ctx: click.Context,
    query: Optional[str],
    agent: Optional[str],
    model: Optional[str],
    temperature: Optional[float],
    top_p: Optional[float],
    swarm: Optional[str],
    parallel: bool,
    timeout: Optional[int],
    no_tools: bool,
    permission_mode: Optional[str],
) -> None:
    """Run a query with model-constellation agent."""
    config = ctx.obj["config"]

    if not query:
        console.print("[yellow]Enter interactive mode...[/yellow]")
        _run_interactive(ctx)
        return

    config_model = config.ollama.default_model if config else "llama2"
    use_model = model or config_model

    if temperature is not None and not (0.0 <= temperature <= 2.0):
        console.print("[red]Error:[/red] temperature must be between 0.0 and 2.0")
        sys.exit(1)

    if top_p is not None and not (0.0 <= top_p <= 1.0):
        console.print("[red]Error:[/red] top_p must be between 0.0 and 1.0")
        sys.exit(1)

    params = ModelParameters(
        temperature=temperature
        if temperature is not None
        else config.parameters.temperature
        if config
        else 0.7,
        top_p=top_p if top_p is not None else config.parameters.top_p if config else 0.9,
    )

    # When tools are enabled, route through the standardized agent runtime so the
    # model can read files, run commands, etc. with permission gating. The plain
    # chat path below is used for --no-tools.
    if not no_tools:
        _run_with_tools(
            config=config,
            query=query,
            use_model=use_model,
            agent=agent,
            permission_mode=permission_mode,
        )
        return

    try:
        client = OllamaClient(
            base_url=config.ollama.base_url,
            default_model=use_model,
        )

        console.print(f"[cyan]Model:[/cyan] {use_model}")
        console.print(f"[cyan]Query:[/cyan] {query}")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Generating response...", total=None)

            response = client.chat(
                model=use_model,
                messages=[{"role": "user", "content": query}],
                parameters=params,
            )

            progress.update(task, completed=True)

        console.print()
        console.print("[bold green]Response:[/bold green]")
        console.print(response.message.content)

        if response.eval_count is not None:
            console.print(f"\n[dim]Tokens: {response.eval_count} | Model: {response.model}[/dim]")

    except OllamaConnectionError as e:
        console.print(f"[red]Connection Error:[/red] {e}")
        console.print("[yellow]Make sure Ollama is running:[/yellow]")
        console.print("  ollama serve")
        sys.exit(1)
    except OllamaModelError as e:
        console.print(f"[red]Model Error:[/red] {e}")
        console.print(f"[yellow]Available models:[/yellow]")
        console.print("  model-constellation model list")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def _load_agent_overrides(agent_ref: Optional[str]) -> Dict[str, object]:
    """Resolve a saved agent (by name or ID) into runtime overrides.

    Args:
        agent_ref: Agent name/ID, or a bare agent *type* (primary/code/research...),
            or None.

    Returns:
        Dict of overrides (``model``, ``system_prompt``, ``tool_names``) to pass to
        the runtime. Empty when nothing matched.
    """
    if not agent_ref:
        return {}

    # Bare agent-type shortcut (e.g. --agent code) → just a system prompt.
    if agent_ref in constants.AGENT_TYPES:
        return {"system_prompt": _get_default_system_prompt(agent_ref)}

    agents_dir = _get_agents_dir()
    agent_file = agents_dir / f"{agent_ref}.json"
    if not agent_file.exists():
        agent_file = _find_agent_by_name(agents_dir, agent_ref)
    if not agent_file:
        console.print(f"[yellow]Warning:[/yellow] agent '{agent_ref}' not found; using defaults")
        return {}

    with open(agent_file) as f:
        data = json.load(f)

    overrides: Dict[str, object] = {}
    if data.get("model"):
        overrides["model"] = data["model"]
    if data.get("system_prompt"):
        overrides["system_prompt"] = data["system_prompt"]
    if data.get("tools"):
        overrides["tool_names"] = data["tools"]
    return overrides


def _run_with_tools(
    config,
    query: str,
    use_model: str,
    agent: Optional[str],
    permission_mode: Optional[str],
) -> None:
    """Run a query through the standardized agent runtime (tools + permissions)."""
    from model_constellation.runtime import AgentRuntime

    client = get_ollama_client(config)
    if not client.check_connection():
        console.print("[red]Error:[/red] Cannot connect to Ollama. Make sure Ollama is running:")
        console.print("  ollama serve")
        sys.exit(1)

    overrides: Dict[str, object] = {"model": use_model}
    overrides.update(_load_agent_overrides(agent))
    if permission_mode:
        overrides["permission_mode"] = permission_mode

    runtime = AgentRuntime.from_config(
        config,
        ollama_client=client,
        console=console,
        **overrides,
    )

    console.print(f"[cyan]Model:[/cyan] {runtime.model}")
    console.print(f"[cyan]Query:[/cyan] {query}")
    if runtime.tool_names:
        console.print(f"[dim]Tools: {', '.join(runtime.tool_names)}[/dim]")

    try:
        with console.status("[bold green]Working...", spinner="dots"):
            result = runtime.run(query)
    except OllamaConnectionError as e:
        console.print(f"[red]Connection Error:[/red] {e}")
        sys.exit(1)
    except OllamaModelError as e:
        console.print(f"[red]Model Error:[/red] {e}")
        console.print("  model-constellation model list")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if result.tool_executions:
        console.print()
        console.print("[bold cyan]Tools used:[/bold cyan]")
        for execution in result.tool_executions:
            status = "[green]ok[/green]" if execution["success"] else "[red]failed[/red]"
            console.print(f"  {status} {execution['tool']} {execution['arguments']}")

    console.print()
    console.print("[bold green]Response:[/bold green]")
    console.print(Markdown(result.content) if result.content else "[dim](no content)[/dim]")


def _run_interactive_tools_loop(
    config,
    client,
    use_model: str,
    agent_ref: Optional[str],
    permission_mode: Optional[str],
) -> None:
    """Interactive chat loop with tool execution via the standardized runtime.

    A single primary agent persists across turns so the conversation (and any
    tool results) carries forward.
    """
    from model_constellation.runtime import AgentRuntime

    overrides: Dict[str, object] = {"model": use_model}
    overrides.update(_load_agent_overrides(agent_ref))
    if permission_mode:
        overrides["permission_mode"] = permission_mode

    runtime = AgentRuntime.from_config(
        config, ollama_client=client, console=console, **overrides
    )
    primary = runtime.build_agent()

    console.print(
        Panel.fit(
            "[bold cyan]model-constellation Interactive Mode (tools enabled)[/bold cyan]\n"
            "Type your messages or /help for commands",
            border_style="cyan",
        )
    )
    console.print(f"[dim]Model: {runtime.model} | Permission: {runtime.permission_manager.get_mode()}[/dim]")
    if runtime.tool_names:
        console.print(f"[dim]Tools: {', '.join(runtime.tool_names)}[/dim]")
    console.print()

    try:
        _interactive_tools_inner(runtime, primary)
    finally:
        runtime.close()


def _interactive_tools_inner(runtime, primary) -> None:
    """Inner read/eval/print loop for tool-enabled interactive mode."""
    while True:
        try:
            user_input = input(">>> ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print()
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            cmd = user_input.split()[0].lower()
            if cmd in ("/exit", "/quit", "/q"):
                break
            if cmd == "/clear":
                primary.clear_history()
                console.clear()
                console.print("[dim]Conversation cleared.[/dim]")
                continue
            if cmd == "/tools":
                console.print(f"[cyan]Available tools:[/cyan] {', '.join(runtime.tool_names) or 'none'}")
                continue
            if cmd == "/help":
                console.print(
                    Panel.fit(
                        "[bold cyan]Commands:[/bold cyan]\n"
                        "  /exit, /quit, /q   Exit\n"
                        "  /clear             Clear conversation\n"
                        "  /tools             List available tools\n"
                        "  /help              Show this help",
                        border_style="cyan",
                    )
                )
                continue
            console.print(f"[yellow]Unknown command:[/yellow] {cmd}")
            continue

        try:
            with console.status("[bold green]Working...", spinner="dots"):
                result = runtime.run(user_input, agent=primary)
        except (OllamaConnectionError, OllamaModelError) as e:
            console.print(f"[red]Error:[/red] {e}")
            continue
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            continue

        for execution in result.tool_executions:
            status = "[green]ok[/green]" if execution["success"] else "[red]failed[/red]"
            console.print(f"[dim]  {status} {execution['tool']} {execution['arguments']}[/dim]")

        console.print()
        console.print(Markdown(result.content) if result.content else "[dim](no content)[/dim]")
        console.print()


def _run_interactive(ctx: click.Context) -> None:
    """Run interactive mode."""
    config = ctx.obj.get("config")
    model = config.ollama.default_model if config else "llama2"

    client = get_ollama_client(config)

    if not client.check_connection():
        console.print("[red]Error:[/red] Cannot connect to Ollama. Make sure Ollama is running:")
        console.print("  ollama serve")
        sys.exit(1)

    history: List[Dict[str, str]] = []

    try:
        _run_interactive_loop(client, model, history, None, False)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")


@cli.command("interactive")
@click.option("--session", type=str, help="Resume existing session")
@click.option("--new-session", type=str, help="Create new named session")
@click.option("--model", type=str, help="Ollama model")
@click.option("--preserve-history", is_flag=True, help="Keep history after exit")
@click.option("--agent", "-a", type=str, help="Agent (name/ID/type) to use for tools")
@click.option("--no-tools", is_flag=True, help="Disable tool execution")
@click.option(
    "--permission-mode",
    type=click.Choice(constants.PERMISSION_MODES),
    help="Permission mode",
)
@click.pass_context
def interactive(
    ctx: click.Context,
    session: Optional[str],
    new_session: Optional[str],
    model: Optional[str],
    preserve_history: bool,
    agent: Optional[str],
    no_tools: bool,
    permission_mode: Optional[str],
) -> None:
    """Start interactive session."""
    config = ctx.obj["config"]

    config_model = config.ollama.default_model if config else "llama2"
    use_model = model or config_model

    client = get_ollama_client(config)

    if not client.check_connection():
        console.print("[red]Error:[/red] Cannot connect to Ollama. Make sure Ollama is running:")
        console.print("  ollama serve")
        sys.exit(1)

    if not no_tools:
        _run_interactive_tools_loop(
            config=config,
            client=client,
            use_model=use_model,
            agent_ref=agent,
            permission_mode=permission_mode,
        )
        return

    history: List[Dict[str, str]] = []
    current_session_name: Optional[str] = None

    if session:
        if session in _session_store:
            history = _session_store[session]
            current_session_name = session
            console.print(f"[cyan]Resumed session:[/cyan] {session} ({len(history)} messages)")
        else:
            session_file = SESSION_HISTORY_DIR / f"{session}.json"
            if session_file.exists():
                try:
                    with open(session_file) as f:
                        history = json.load(f)
                    current_session_name = session
                    console.print(
                        f"[cyan]Loaded session:[/cyan] {session} ({len(history)} messages)"
                    )
                except Exception as e:
                    console.print(f"[yellow]Warning:[/yellow] Could not load session: {e}")
                    history = []
            else:
                console.print(
                    f"[yellow]Warning:[/yellow] Session '{session}' not found, starting fresh"
                )
                history = []
    elif new_session:
        current_session_name = new_session
        _session_store[new_session] = history
        console.print(f"[cyan]Created new session:[/cyan] {new_session}")

    try:
        _run_interactive_loop(client, use_model, history, current_session_name, preserve_history)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
    finally:
        if current_session_name and preserve_history:
            _session_store[current_session_name] = history
            try:
                session_file = SESSION_HISTORY_DIR / f"{current_session_name}.json"
                with open(session_file, "w") as f:
                    json.dump(history, f, indent=2)
                console.print(f"[dim]Session saved to {session_file}[/dim]")
            except Exception as e:
                console.print(f"[yellow]Warning:[/yellow] Could not save session: {e}")


def _run_interactive_loop(
    client: OllamaClient,
    model: str,
    history: List[Dict[str, str]],
    session_name: Optional[str],
    preserve_history: bool,
) -> None:
    """Run the interactive chat loop."""

    console.print(
        Panel.fit(
            "[bold cyan]model-constellation Interactive Mode[/bold cyan]\n"
            "Type your messages or /help for commands",
            border_style="cyan",
        )
    )
    console.print(f"[dim]Model: {model}[/dim]")
    if session_name:
        console.print(f"[dim]Session: {session_name}[/dim]")
    console.print()

    prompt_session = None
    if PROMPTTOOLKIT_AVAILABLE and PromptSession and FileHistory and AutoSuggestFromHistory:
        try:
            history_file = SESSION_HISTORY_DIR / ".history"
            prompt_session = PromptSession(  # type: ignore[misc]
                history=FileHistory(str(history_file)),  # type: ignore[misc]
                auto_suggest=AutoSuggestFromHistory(),  # type: ignore[misc]
            )
        except Exception:
            pass

    while True:
        try:
            if prompt_session is not None:
                user_input = prompt_session.prompt(">>> ")
            else:
                user_input = input(">>> ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print()
            break

        if not user_input.strip():
            continue

        if user_input.startswith("/"):
            should_exit = _handle_command(user_input, client, model, history, session_name)
            if should_exit:
                break
            continue

        history.append({"role": "user", "content": user_input})

        try:
            with console.status(f"[bold green]Thinking...", spinner="dots"):
                response = client.chat(
                    model=model,
                    messages=cast(List[Union[Dict[str, str], ChatMessage]], history),
                )

            assistant_message = response.message.content
            history.append({"role": "assistant", "content": assistant_message})

            console.print()
            md = Markdown(assistant_message)
            console.print(md)

            if response.eval_count:
                console.print(
                    f"\n[dim]Tokens: {response.eval_count} | Model: {response.model}[/dim]"
                )
            console.print()

        except OllamaConnectionError as e:
            console.print(f"[red]Connection Error:[/red] {e}")
            console.print("[yellow]Make sure Ollama is running:[/yellow]")
            console.print("  ollama serve")
            history.pop()
        except OllamaModelError as e:
            console.print(f"[red]Model Error:[/red] {e}")
            history.pop()
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            history.pop()


def _handle_command(
    command: str,
    client: OllamaClient,
    model: str,
    history: List[Dict[str, str]],
    session_name: Optional[str],
) -> bool:
    """Handle special commands. Returns True if command exits the loop."""
    parts = command.split()
    cmd = parts[0].lower()

    if cmd in ("/exit", "/quit", "/q"):
        return True

    elif cmd == "/clear":
        console.clear()
        console.print(
            Panel.fit(
                "[bold cyan]model-constellation Interactive Mode[/bold cyan]\n"
                "Type your messages or /help for commands",
                border_style="cyan",
            )
        )
        console.print(f"[dim]Model: {model}[/dim]")
        if session_name:
            console.print(f"[dim]Session: {session_name}[/dim]")
        console.print()

    elif cmd == "/history":
        if not history:
            console.print("[yellow]No conversation history[/yellow]")
        else:
            table = Table(title="Conversation History", box=box.ROUNDED)
            table.add_column("#", justify="right", width=4)
            table.add_column("Role", style="cyan", width=10)
            table.add_column("Content", width=60)

            for i, msg in enumerate(history):
                content = msg["content"]
                if len(content) > 57:
                    content = content[:57] + "..."
                table.add_row(str(i + 1), msg["role"], content)

            console.print(table)
            console.print(f"[dim]Total messages: {len(history)}[/dim]")

    elif cmd == "/model":
        console.print(f"[cyan]Current model:[/cyan] {model}")
        try:
            models = client.list_models()
            if models:
                console.print("[cyan]Available models:[/cyan]")
                for m in models[:10]:
                    console.print(f"  - {m.name}")
                if len(models) > 10:
                    console.print(f"  ... and {len(models) - 10} more")
        except Exception:
            pass

    elif cmd == "/help":
        help_text = """
[bold cyan]Commands:[/bold cyan]
  /exit, /quit, /q    Exit interactive mode
  /clear              Clear the screen
  /history            Show conversation history
  /model [name]       Show or switch model
  /help               Show this help message

[bold cyan]Tips:[/bold cyan]
  - Messages are sent to Ollama for responses
  - Conversation history is maintained during the session
  - Use --preserve-history to save session to disk
  - Use --session to resume a previous session
"""
        console.print(Panel.fit(help_text.strip(), border_style="cyan"))

    else:
        console.print(f"[yellow]Unknown command:[/yellow] {cmd}")
        console.print("Type /help for available commands")

    return False


@cli.group()
def agent() -> None:
    """Manage agents."""
    pass


@agent.command("create")
@click.argument("name")
@click.option(
    "--type",
    "agent_type",
    type=click.Choice(constants.AGENT_TYPES),
    default="specialized",
)
@click.option("--mode", type=click.Choice(constants.AGENT_MODES), default="isolated")
@click.option("--model", type=str, help="Ollama model")
@click.option("--tools", type=str, help="Comma-separated tool list")
@click.option("--system-prompt", type=str, help="Custom system prompt")
@click.option("--parent", type=str, help="Parent agent ID for hierarchical mode")
@click.option("--swarm", type=str, help="Swarm ID to join")
@click.pass_context
def agent_create(
    ctx: click.Context,
    name: str,
    agent_type: str,
    mode: str,
    model: Optional[str],
    tools: Optional[str],
    system_prompt: Optional[str],
    parent: Optional[str],
    swarm: Optional[str],
) -> None:
    """Create a new agent."""
    config = ctx.obj.get("config")
    agents_dir = _get_agents_dir()

    if mode == "hierarchical" and not parent:
        console.print("[red]Error:[/red] --parent is required for hierarchical mode")
        sys.exit(1)

    if mode != "hierarchical" and parent:
        console.print("[red]Error:[/red] --parent is only valid for hierarchical mode")
        sys.exit(1)

    agent_id = _generate_agent_id()

    agent_data = {
        "id": agent_id,
        "name": name,
        "type": agent_type,
        "mode": mode,
        "model": model or config.ollama.default_model if config else constants.DEFAULT_MODEL,
        "tools": [t.strip() for t in tools.split(",")] if tools else [],
        "system_prompt": system_prompt or _get_default_system_prompt(agent_type),
        "parent": parent,
        "swarm": swarm,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "history": [],
    }

    agent_file = agents_dir / f"{agent_id}.json"
    with open(agent_file, "w") as f:
        json.dump(agent_data, f, indent=2)

    console.print(f"[green]Created agent:[/green] {name}")
    console.print(f"  ID: {agent_id}")
    console.print(f"  Type: {agent_type}")
    console.print(f"  Mode: {mode}")
    console.print(f"  Model: {agent_data['model']}")


def _get_default_system_prompt(agent_type: str) -> str:
    """Get default system prompt for an agent type."""
    prompts = {
        "primary": "You are a helpful AI assistant.",
        "specialized": "You are a specialized AI assistant focused on your designated task.",
        "worker": "You are a worker agent that executes tasks efficiently.",
        "research": "You are a research agent that gathers and analyzes information.",
        "code": "You are a code generation and analysis assistant.",
    }
    return prompts.get(agent_type, "You are a helpful AI assistant.")


@agent.command("list")
@click.option(
    "--type",
    "agent_type",
    type=click.Choice(constants.AGENT_TYPES),
    help="Filter by agent type",
)
@click.option("--swarm", type=str, help="Filter by swarm")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed info")
@click.pass_context
def agent_list(
    ctx: click.Context,
    agent_type: Optional[str],
    swarm: Optional[str],
    verbose: bool,
) -> None:
    """List all agents."""
    agents_dir = _get_agents_dir()

    if not agents_dir.exists() or not list(agents_dir.glob("*.json")):
        console.print("[yellow]No agents found.[/yellow]")
        console.print("[dim]Create an agent with: model-constellation agent create <name>[/dim]")
        return

    agents = []
    for agent_file in agents_dir.glob("*.json"):
        try:
            with open(agent_file) as f:
                agent = json.load(f)
                agents.append(agent)
        except (json.JSONDecodeError, IOError):
            continue

    if agent_type:
        agents = [a for a in agents if a.get("type") == agent_type]
    if swarm:
        agents = [a for a in agents if a.get("swarm") == swarm]

    if not agents:
        console.print("[yellow]No agents found matching criteria.[/yellow]")
        return

    table = Table(title="Agents", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="green")
    table.add_column("ID", style="dim")
    table.add_column("Type")
    table.add_column("Mode")
    if verbose:
        table.add_column("Model")
        table.add_column("Tools")
        table.add_column("Created")

    for agent in agents:
        row = [
            agent.get("name", "unknown"),
            agent.get("id", "unknown"),
            agent.get("type", "unknown"),
            agent.get("mode", "unknown"),
        ]
        if verbose:
            row.append(agent.get("model", "unknown"))
            row.append(", ".join(agent.get("tools", [])) or "-")
            created = agent.get("created_at", "unknown")
            if created != "unknown":
                created = created[:10]
            row.append(created)
        table.add_row(*row)

    console.print(table)
    console.print(f"\n[dim]Total: {len(agents)} agent(s)[/dim]")


@agent.command()
@click.argument("agent_id")
@click.option("--history", is_flag=True, help="Show conversation history")
@click.option("--tools", is_flag=True, help="Show available tools")
@click.option("--parameters", is_flag=True, help="Show model parameters")
@click.pass_context
def agent_info(
    ctx: click.Context,
    agent_id: str,
    history: bool,
    tools: bool,
    parameters: bool,
) -> None:
    """Show agent information."""
    agents_dir = _get_agents_dir()

    agent_file = agents_dir / f"{agent_id}.json"
    if not agent_file.exists():
        agent_file = _find_agent_by_name(agents_dir, agent_id)
        if not agent_file:
            console.print(f"[red]Error:[/red] Agent '{agent_id}' not found")
            sys.exit(1)

    with open(agent_file) as f:
        agent = json.load(f)

    console.print(f"[bold cyan]Agent Information[/bold cyan]")
    console.print()

    info_table = Table(show_header=False, box=box.SIMPLE)
    info_table.add_column("Key", style="cyan", width=15)
    info_table.add_column("Value", style="white")

    info_table.add_row("ID", agent.get("id", "unknown"))
    info_table.add_row("Name", agent.get("name", "unknown"))
    info_table.add_row("Type", agent.get("type", "unknown"))
    info_table.add_row("Mode", agent.get("mode", "unknown"))
    info_table.add_row("Model", agent.get("model", "unknown"))
    info_table.add_row("Parent", agent.get("parent") or "-")
    info_table.add_row("Swarm", agent.get("swarm") or "-")
    info_table.add_row("Created", agent.get("created_at", "unknown")[:19])
    info_table.add_row("Updated", agent.get("updated_at", "unknown")[:19])

    console.print(info_table)

    if tools or not (history or parameters):
        console.print()
        console.print("[bold cyan]Tools:[/bold cyan]")
        agent_tools = agent.get("tools", [])
        if agent_tools:
            for tool in agent_tools:
                console.print(f"  - {tool}")
        else:
            console.print("  [dim]No tools configured[/dim]")

    if parameters:
        console.print()
        console.print("[bold cyan]Model Parameters:[/bold cyan]")
        params = agent.get("parameters", {})
        if params:
            params_table = Table(show_header=False, box=box.SIMPLE)
            params_table.add_column("Key", style="cyan", width=15)
            params_table.add_column("Value", style="white")
            for k, v in params.items():
                params_table.add_row(k, str(v))
            console.print(params_table)
        else:
            console.print("  [dim]Using default parameters[/dim]")

    if history:
        console.print()
        console.print("[bold cyan]Conversation History:[/bold cyan]")
        history_data = agent.get("history", [])
        if history_data:
            for i, msg in enumerate(history_data):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if len(content) > 100:
                    content = content[:100] + "..."
                console.print(f"  [{i + 1}] {role}: {content}")
        else:
            console.print("  [dim]No conversation history[/dim]")


def _find_agent_by_name(agents_dir: Path, name: str) -> Optional[Path]:
    """Find agent file by name or ID."""
    for agent_file in agents_dir.glob("*.json"):
        try:
            with open(agent_file) as f:
                agent = json.load(f)
                if agent.get("name") == name or agent.get("id") == name:
                    return agent_file
        except (json.JSONDecodeError, IOError):
            continue
    return None


@agent.command("delete")
@click.argument("agent_id")
@click.option("--force", is_flag=True, help="Force deletion without confirmation")
@click.pass_context
def agent_delete(ctx: click.Context, agent_id: str, force: bool) -> None:
    """Delete an agent."""
    agents_dir = _get_agents_dir()

    agent_file = agents_dir / f"{agent_id}.json"
    if not agent_file.exists():
        agent_file = _find_agent_by_name(agents_dir, agent_id)
        if not agent_file:
            console.print(f"[red]Error:[/red] Agent '{agent_id}' not found")
            sys.exit(1)

    with open(agent_file) as f:
        agent = json.load(f)

    agent_name = agent.get("name", agent_id)

    if not force:
        if not click.confirm(f"Delete agent '{agent_name}'?"):
            return

    agent_file.unlink()
    console.print(f"[green]Deleted agent:[/green] {agent_name}")


@cli.group()
def swarm() -> None:
    """Manage agent swarms."""
    pass


@swarm.command("create")
@click.argument("name")
@click.option("--agents", type=int, default=3, help="Number of agents")
@click.option("--mode", type=click.Choice(constants.SWARM_MODES), default="parallel")
@click.option("--type", "agent_type", type=click.Choice(constants.AGENT_TYPES), default="worker")
@click.option("--model", type=str, help="Model for all swarm agents")
@click.option("--shared-tools", type=str, help="Tools available to all agents")
@click.pass_context
def swarm_create(
    ctx: click.Context,
    name: str,
    agents: int,
    mode: str,
    agent_type: str,
    model: Optional[str],
    shared_tools: Optional[str],
) -> None:
    """Create a new agent swarm."""
    config = ctx.obj.get("config")
    swarms_dir = _get_swarms_dir()
    agents_dir = _get_agents_dir()

    if agents < 1:
        console.print("[red]Error:[/red] Number of agents must be at least 1")
        sys.exit(1)

    if agents > constants.DEFAULT_MAX_SWARM_SIZE:
        console.print(
            f"[red]Error:[/red] Maximum {constants.DEFAULT_MAX_SWARM_SIZE} agents allowed"
        )
        sys.exit(1)

    swarm_id = f"swarm_{uuid.uuid4().hex[:12]}"
    use_model = model or config.ollama.default_model if config else constants.DEFAULT_MODEL

    swarm_agents = []
    for i in range(agents):
        agent_id = _generate_agent_id()
        agent_data = {
            "id": agent_id,
            "name": f"{name}-agent-{i + 1}",
            "type": agent_type,
            "mode": "swarm",
            "model": use_model,
            "tools": [t.strip() for t in shared_tools.split(",")] if shared_tools else [],
            "system_prompt": _get_default_system_prompt(agent_type),
            "swarm": swarm_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "history": [],
        }

        agent_file = agents_dir / f"{agent_id}.json"
        with open(agent_file, "w") as f:
            json.dump(agent_data, f, indent=2)

        swarm_agents.append(
            {
                "agent_id": agent_id,
                "name": agent_data["name"],
                "model": use_model,
            }
        )

    swarm_data = {
        "id": swarm_id,
        "name": name,
        "mode": mode,
        "agent_type": agent_type,
        "model": use_model,
        "shared_tools": [t.strip() for t in shared_tools.split(",")] if shared_tools else [],
        "agents": swarm_agents,
        "status": "created",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "history": [],
    }

    swarm_file = swarms_dir / f"{swarm_id}.json"
    with open(swarm_file, "w") as f:
        json.dump(swarm_data, f, indent=2)

    console.print(f"[green]Created swarm:[/green] {name}")
    console.print(f"  ID: {swarm_id}")
    console.print(f"  Agents: {agents}")
    console.print(f"  Mode: {mode}")
    console.print(f"  Model: {use_model}")


@swarm.command("list")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed info")
@click.option("--active-only", is_flag=True, help="Show only active swarms")
@click.pass_context
def swarm_list(ctx: click.Context, verbose: bool, active_only: bool) -> None:
    """List all swarms."""
    swarms_dir = _get_swarms_dir()

    if not swarms_dir.exists() or not list(swarms_dir.glob("*.json")):
        console.print("[yellow]No swarms found.[/yellow]")
        console.print("[dim]Create a swarm with: model-constellation swarm create <name>[/dim]")
        return

    swarms = []
    for swarm_file in swarms_dir.glob("*.json"):
        try:
            with open(swarm_file) as f:
                swarm = json.load(f)
                swarms.append(swarm)
        except (json.JSONDecodeError, IOError):
            continue

    if active_only:
        swarms = [s for s in swarms if s.get("status") == "running"]

    if not swarms:
        if active_only:
            console.print("[yellow]No active swarms found.[/yellow]")
        else:
            console.print("[yellow]No swarms found.[/yellow]")
        return

    table = Table(title="Swarms", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="green")
    table.add_column("ID", style="dim")
    table.add_column("Mode")
    table.add_column("Agents")
    table.add_column("Status")
    if verbose:
        table.add_column("Model")
        table.add_column("Created")

    for swarm in swarms:
        row = [
            swarm.get("name", "unknown"),
            swarm.get("id", "unknown"),
            swarm.get("mode", "unknown"),
            str(len(swarm.get("agents", []))),
            swarm.get("status", "unknown"),
        ]
        if verbose:
            row.append(swarm.get("model", "unknown"))
            created = swarm.get("created_at", "unknown")
            if created != "unknown":
                created = created[:10]
            row.append(created)
        table.add_row(*row)

    console.print(table)
    console.print(f"\n[dim]Total: {len(swarms)} swarm(s)[/dim]")


@swarm.command()
@click.argument("swarm_id")
@click.option("--agents", is_flag=True, help="List all agents in swarm")
@click.option("--status", is_flag=True, help="Show execution status")
@click.option("--history", is_flag=True, help="Show swarm activity")
@click.pass_context
def swarm_info(
    ctx: click.Context,
    swarm_id: str,
    agents: bool,
    status: bool,
    history: bool,
) -> None:
    """Show swarm information."""
    swarms_dir = _get_swarms_dir()

    swarm_file = swarms_dir / f"{swarm_id}.json"
    if not swarm_file.exists():
        swarm_file = _find_swarm_by_name(swarms_dir, swarm_id)
        if not swarm_file:
            console.print(f"[red]Error:[/red] Swarm '{swarm_id}' not found")
            sys.exit(1)

    with open(swarm_file) as f:
        swarm = json.load(f)

    console.print(f"[bold cyan]Swarm Information[/bold cyan]")
    console.print()

    info_table = Table(show_header=False, box=box.SIMPLE)
    info_table.add_column("Key", style="cyan", width=15)
    info_table.add_column("Value", style="white")

    info_table.add_row("ID", swarm.get("id", "unknown"))
    info_table.add_row("Name", swarm.get("name", "unknown"))
    info_table.add_row("Mode", swarm.get("mode", "unknown"))
    info_table.add_row("Agent Type", swarm.get("agent_type", "unknown"))
    info_table.add_row("Model", swarm.get("model", "unknown"))
    info_table.add_row("Status", swarm.get("status", "unknown"))
    info_table.add_row("Created", swarm.get("created_at", "unknown")[:19])
    info_table.add_row("Updated", swarm.get("updated_at", "unknown")[:19])

    console.print(info_table)

    if agents or not (status or history):
        console.print()
        console.print("[bold cyan]Agents:[/bold cyan]")
        swarm_agents = swarm.get("agents", [])
        if swarm_agents:
            agent_table = Table(show_header=True, box=box.SIMPLE)
            agent_table.add_column("Name", style="green")
            agent_table.add_column("ID", style="dim")
            agent_table.add_column("Model")
            for agent in swarm_agents:
                agent_table.add_row(
                    agent.get("name", "unknown"),
                    agent.get("agent_id", "unknown"),
                    agent.get("model", "unknown"),
                )
            console.print(agent_table)
        else:
            console.print("  [dim]No agents in swarm[/dim]")

    if status or not (agents or history):
        console.print()
        console.print("[bold cyan]Status:[/bold cyan]")
        console.print(f"  Current: {swarm.get('status', 'unknown')}")
        console.print(f"  Total Tasks: {len(swarm.get('history', []))}")

    if history:
        console.print()
        console.print("[bold cyan]Activity History:[/bold cyan]")
        history_data = swarm.get("history", [])
        if history_data:
            for i, entry in enumerate(history_data):
                task = entry.get("task", "unknown")
                result = entry.get("result", "")
                if len(result) > 80:
                    result = result[:80] + "..."
                console.print(f"  [{i + 1}] {task}")
                console.print(f"      Result: {result}")
        else:
            console.print("  [dim]No activity history[/dim]")


def _find_swarm_by_name(swarms_dir: Path, name: str) -> Optional[Path]:
    """Find swarm file by name or ID."""
    for swarm_file in swarms_dir.glob("*.json"):
        try:
            with open(swarm_file) as f:
                swarm = json.load(f)
                if swarm.get("name") == name or swarm.get("id") == name:
                    return swarm_file
        except (json.JSONDecodeError, IOError):
            continue
    return None


@swarm.command("run")
@click.argument("swarm_id")
@click.argument("task")
@click.option("--wait", is_flag=True, help="Wait for completion")
@click.option("--timeout", type=int, help="Timeout in seconds")
@click.option("--output-format", type=click.Choice(["json", "text", "stream"]), default="text")
@click.pass_context
def swarm_run(
    ctx: click.Context,
    swarm_id: str,
    task: str,
    wait: bool,
    timeout: Optional[int],
    output_format: str,
) -> None:
    """Run task on swarm."""
    config = ctx.obj.get("config")
    swarms_dir = _get_swarms_dir()

    swarm_file = swarms_dir / f"{swarm_id}.json"
    if not swarm_file.exists():
        swarm_file = _find_swarm_by_name(swarms_dir, swarm_id)
        if not swarm_file:
            console.print(f"[red]Error:[/red] Swarm '{swarm_id}' not found")
            sys.exit(1)

    with open(swarm_file) as f:
        swarm = json.load(f)

    swarm_agents = swarm.get("agents", [])
    if not swarm_agents:
        console.print("[red]Error:[/red] Swarm has no agents")
        sys.exit(1)

    mode = swarm.get("mode", "parallel")
    model = swarm.get("model", config.ollama.default_model if config else constants.DEFAULT_MODEL)

    try:
        client = OllamaClient(
            base_url=config.ollama.base_url,
            default_model=model,
        )

        if not client.check_connection():
            console.print(
                "[red]Error:[/red] Cannot connect to Ollama. Make sure Ollama is running:"
            )
            console.print("  ollama serve")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    swarm["status"] = "running"
    swarm["updated_at"] = datetime.now().isoformat()

    with open(swarm_file, "w") as f:
        json.dump(swarm, f, indent=2)

    console.print(f"[cyan]Running task on swarm {swarm.get('name')}:[/cyan] {task}")
    console.print(f"  Mode: {mode}")
    console.print(f"  Agents: {len(swarm_agents)}")

    # Execute through the standardized agent framework (AgentSwarm). When the
    # swarm defines shared_tools, agents run with tools under the configured
    # permission mode; otherwise it is plain multi-agent chat.
    from model_constellation.runtime import AgentRuntime

    shared_tools = swarm.get("shared_tools", []) or []
    runtime = AgentRuntime.from_config(
        config,
        ollama_client=client,
        console=console,
        model=model,
        tool_names=shared_tools,
        enable_tools=bool(shared_tools),
    )

    agent_specs = [
        {
            "name": a.get("name", "agent"),
            "model": a.get("model", model),
            "type": swarm.get("agent_type", "worker"),
            "tools": shared_tools,
        }
        for a in swarm_agents
    ]

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        run_task = progress.add_task(f"[cyan]Running {mode} agents...", total=None)
        try:
            swarm_result = runtime.run_swarm(task, agent_specs, mode=mode)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)
        progress.update(run_task, completed=True)

    for task_result in swarm_result.task_results:
        if task_result.get("status") == "failed":
            results.append(
                {
                    "agent_id": task_result.get("agent_id"),
                    "agent_name": task_result.get("agent_name"),
                    "error": task_result.get("error", "Unknown error"),
                }
            )
        else:
            results.append(
                {
                    "agent_id": task_result.get("agent_id"),
                    "agent_name": task_result.get("agent_name"),
                    "result": task_result.get("result", ""),
                    "model": model,
                }
            )

    swarm["status"] = "completed"
    swarm["updated_at"] = datetime.now().isoformat()
    swarm["history"] = swarm.get("history", []) + [
        {
            "task": task,
            "timestamp": datetime.now().isoformat(),
            "result": "completed" if results else "failed",
        }
    ]

    with open(swarm_file, "w") as f:
        json.dump(swarm, f, indent=2)

    console.print()
    if output_format == "json":
        console.print_json(
            data={
                "swarm_id": swarm_id,
                "mode": mode,
                "results": results,
            }
        )
    else:
        console.print("[bold cyan]Results:[/bold cyan]")
        for result in results:
            agent_name = result.get("agent_name", "unknown")
            if "error" in result:
                console.print(f"  [red]{agent_name}:[/red] {result['error']}")
            else:
                console.print(f"  [green]{agent_name}:[/green]")
                console.print(f"    {result.get('result', '')}")
                console.print()

        if len(results) > 1:
            console.print("[bold cyan]Summary:[/bold cyan]")
            successful = sum(1 for r in results if "error" not in r)
            console.print(f"  Successful: {successful}/{len(results)}")


@swarm.command("delete")
@click.argument("swarm_id")
@click.option("--force", is_flag=True, help="Force deletion without confirmation")
@click.pass_context
def swarm_delete(ctx: click.Context, swarm_id: str, force: bool) -> None:
    """Delete a swarm."""
    swarms_dir = _get_swarms_dir()
    agents_dir = _get_agents_dir()

    swarm_file = swarms_dir / f"{swarm_id}.json"
    if not swarm_file.exists():
        swarm_file = _find_swarm_by_name(swarms_dir, swarm_id)
        if not swarm_file:
            console.print(f"[red]Error:[/red] Swarm '{swarm_id}' not found")
            sys.exit(1)

    with open(swarm_file) as f:
        swarm = json.load(f)

    swarm_name = swarm.get("name", swarm_id)
    swarm_agents = swarm.get("agents", [])

    if not force:
        if not click.confirm(f"Delete swarm '{swarm_name}' and its {len(swarm_agents)} agents?"):
            return

    for agent in swarm_agents:
        agent_id = agent.get("agent_id")
        if agent_id:
            agent_file = agents_dir / f"{agent_id}.json"
            if agent_file.exists():
                agent_file.unlink()

    swarm_file.unlink()
    console.print(f"[green]Deleted swarm:[/green] {swarm_name}")
    console.print(f"  Removed {len(swarm_agents)} agent(s)")


@cli.group()
def model() -> None:
    """Manage Ollama models."""
    pass


@model.command("list")
@click.option("--local", is_flag=True, help="Show only local models")
@click.option("--remote", is_flag=True, help="Show available remote models")
@click.option("--detailed", "-v", is_flag=True, help="Show model details")
@click.pass_context
def model_list(ctx: click.Context, local: bool, remote: bool, detailed: bool) -> None:
    """List available models."""
    try:
        client = get_ollama_client(ctx.obj.get("config"))
        models = client.list_models()

        if not models:
            console.print("[yellow]No models found. Pull a model with:[/yellow]")
            console.print("  model-constellation model pull <model-name>")
            return

        table = Table(title="Available Ollama Models", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="green")
        table.add_column("Size", justify="right")
        if detailed:
            table.add_column("Modified")
            table.add_column("Digest")

        for m in models:
            size_gb = m.size / (1024**3) if m.size else 0
            row = [m.name or "unknown", f"{size_gb:.2f} GB"]
            if detailed:
                row.append(m.modified_at or "unknown")
                row.append(m.digest[:12] if m.digest else "unknown")
            table.add_row(*row)

        console.print(table)

    except OllamaConnectionError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("[yellow]Make sure Ollama is running:[/yellow]")
        console.print("  ollama serve")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error listing models:[/red] {e}")
        sys.exit(1)


@model.command("params")
@click.argument("model_name", required=False)
@click.option("--show-presets", is_flag=True, help="Show available parameter presets")
@click.pass_context
def model_params(ctx: click.Context, model_name: Optional[str], show_presets: bool) -> None:
    """Query model parameters."""
    config = ctx.obj.get("config")
    model = model_name or config.ollama.default_model if config else "llama3.2"

    console.print(f"[cyan]Model:[/cyan] {model}")

    try:
        manager = ModelManager(
            client=get_ollama_client(config),
            default_model=model,
        )
        params = manager.get_parameters(model=model)

        table = Table(title="Model Parameters", show_header=True, header_style="bold cyan")
        table.add_column("Parameter", style="green", width=20)
        table.add_column("Value", justify="right")

        table.add_row("temperature", str(params.temperature))
        table.add_row("top_p", str(params.top_p))
        table.add_row("top_k", str(params.top_k))
        table.add_row("repeat_penalty", str(params.repeat_penalty))
        table.add_row("num_ctx", str(params.num_ctx))
        table.add_row("num_gpu", str(params.num_gpu))
        table.add_row("num_thread", str(params.num_thread))
        if params.seed is not None:
            table.add_row("seed", str(params.seed))

        console.print(table)

    except OllamaConnectionError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("[yellow]Using default parameters[/yellow]")

        params = ModelParameters()
        table = Table(title="Default Model Parameters", show_header=True, header_style="bold cyan")
        table.add_column("Parameter", style="green", width=20)
        table.add_column("Value", justify="right")

        table.add_row("temperature", str(params.temperature))
        table.add_row("top_p", str(params.top_p))
        table.add_row("top_k", str(params.top_k))
        table.add_row("repeat_penalty", str(params.repeat_penalty))
        table.add_row("num_ctx", str(params.num_ctx))
        table.add_row("num_gpu", str(params.num_gpu))
        table.add_row("num_thread", str(params.num_thread))

        console.print(table)

    if show_presets:
        console.print()
        presets_table = Table(
            title="Available Parameter Presets", show_header=True, header_style="bold cyan"
        )
        presets_table.add_column("Preset", style="green", width=15)
        presets_table.add_column("Description", width=35)
        presets_table.add_column("Temperature", justify="right")
        presets_table.add_column("Top P", justify="right")
        presets_table.add_column("Top K", justify="right")

        for name, preset in DEFAULT_PRESETS.items():
            p = preset.parameters
            presets_table.add_row(
                name,
                preset.description,
                str(p.temperature),
                str(p.top_p),
                str(p.top_k),
            )

        console.print(presets_table)


@model.command("pull")
@click.argument("model_name")
@click.option("--force", is_flag=True, help="Force pull even if model exists")
@click.pass_context
def model_pull(ctx: click.Context, model_name: str, force: bool) -> None:
    """Pull a model from Ollama library."""
    try:
        client = get_ollama_client(ctx.obj.get("config"))

        console.print(f"[cyan]Pulling model:[/cyan] {model_name}")
        if force:
            console.print("[yellow]Force mode enabled - will re-pull if model exists[/yellow]")

        total_size = 0
        downloaded = 0
        status_text = ""

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Downloading...", total=None)

            for progress_update in client.pull_model(model_name, stream=True, force=force):
                if isinstance(progress_update, dict):
                    if progress_update.get("status"):
                        status_text = progress_update.get("status", "")
                        progress.update(task, description=f"[cyan]{status_text}")

                    if progress_update.get("total"):
                        total_size = progress_update.get("total", 0)
                        downloaded = progress_update.get("completed", 0)
                        progress.update(
                            task,
                            completed=downloaded,
                            total=total_size,
                            description=f"[cyan]{status_text} ({_format_size(downloaded)} / {_format_size(total_size)})",
                        )

                    if progress_update.get("done"):
                        progress.update(task, completed=total_size, total=total_size)

        console.print(f"[green]Successfully pulled model:[/green] {model_name}")

    except OllamaConnectionError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("[yellow]Make sure Ollama is running:[/yellow]")
        console.print("  ollama serve")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error pulling model:[/red] {e}")
        sys.exit(1)


def _format_size(bytes_size: int) -> str:
    """Format byte size to human readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


@cli.group()
def config() -> None:
    """Configuration management."""
    pass


@config.command("init")
@click.pass_context
def config_init(ctx: click.Context) -> None:
    """Create default configuration."""
    manager = ctx.obj["config_manager"]
    cfg = manager.generate_default()
    console.print(f"[green]Created default configuration at:[/green] {manager.config_path}")


@config.command("show")
@click.option("--format", "output_format", type=click.Choice(["yaml", "json"]), default="yaml")
@click.pass_context
def config_show(ctx: click.Context, output_format: str) -> None:
    """Display current configuration."""
    cfg = ctx.obj["config"]
    if output_format == "yaml":
        import yaml

        console.print(yaml.dump(cfg.model_dump(mode="json"), default_flow_style=False))
    else:
        console.print(cfg.model_dump_json(indent=2))


@config.command("validate")
@click.pass_context
def config_validate(ctx: click.Context) -> None:
    """Validate configuration syntax."""
    manager = ctx.obj["config_manager"]
    if manager.validate():
        console.print("[green]Configuration is valid[/green]")
    else:
        console.print("[red]Configuration is invalid[/red]")
        sys.exit(1)


@config.command("edit")
@click.pass_context
def config_edit(ctx: click.Context) -> None:
    """Open config in editor."""
    manager = ctx.obj["config_manager"]
    click.edit(filename=str(manager.config_path))


@config.command("path")
@click.pass_context
def config_path(ctx: click.Context) -> None:
    """Show config file path."""
    manager = ctx.obj["config_manager"]
    console.print(str(manager.config_path))


@cli.group(invoke_without_command=True)
@click.pass_context
def tui(ctx: click.Context) -> None:
    """Themed Terminal User Interface commands."""
    if ctx.invoked_subcommand is None:
        exit_code = start_themed_tui(
            theme=None,
            model=None,
            no_streaming=False,
            permission_mode=None,
            base_url="http://localhost:11434",
        )
        ctx.exit(exit_code)


@tui.command(name="start")
@click.option(
    "--theme",
    "-t",
    type=str,
    help="Theme to use (default, dark, light, ocean, forest, sunset, neon, monokai)",
)
@click.option(
    "--model",
    "-m",
    type=str,
    help="Ollama model to use for chat",
)
@click.option(
    "--no-streaming",
    is_flag=True,
    help="Disable streaming responses",
)
@click.option(
    "--permission-mode",
    "-p",
    type=click.Choice(
        ["first-time", "every-time", "allow-all", "deny-all"],
        case_sensitive=False,
    ),
    help="Permission mode for tool execution",
)
@click.option(
    "--base-url",
    type=str,
    default="http://localhost:11434",
    help="Ollama server URL (default: http://localhost:11434)",
)
def tui_start(
    theme: Optional[str],
    model: Optional[str],
    no_streaming: bool,
    permission_mode: Optional[str],
    base_url: str,
) -> None:
    """Start the themed TUI chat interface."""
    available_themes = ["default", "dark", "light", "ocean", "forest", "sunset", "neon", "monokai"]

    if theme and theme not in available_themes:
        console.print(f"[red]Error:[/red] Unknown theme '{theme}'")
        console.print(f"Available themes: {', '.join(available_themes)}")
        sys.exit(1)

    exit_code = start_themed_tui(
        theme=theme,
        model=model,
        no_streaming=no_streaming,
        permission_mode=permission_mode,
        base_url=base_url,
    )
    sys.exit(exit_code)


@tui.command(name="themes")
def tui_themes() -> None:
    """List available themes."""
    from model_constellation.ui.cli_integration import get_theme_manager, ThemePreview

    if get_theme_manager is None or ThemePreview is None:
        console.print("[red]Error:[/red] TUI dependencies not available.")
        console.print("Please ensure pytermgui is properly installed.")
        sys.exit(1)
    theme_manager = get_theme_manager()
    preview = ThemePreview(theme_manager)
    preview.print_all_themes()


@tui.command(name="preview")
@click.argument("theme_name")
def tui_preview(theme_name: str) -> None:
    """Preview a specific theme."""
    from model_constellation.ui.cli_integration import get_theme_manager, ThemePreview

    if get_theme_manager is None or ThemePreview is None:
        console.print("[red]Error:[/red] TUI dependencies not available.")
        console.print("Please ensure pytermgui is properly installed.")
        sys.exit(1)
    theme_manager = get_theme_manager()
    theme = theme_manager.get_theme(theme_name)

    if theme is None:
        available = [t.name for t in theme_manager.list_themes()]
        console.print(f"[red]Error:[/red] Theme '{theme_name}' not found")
        console.print(f"Available: {', '.join(available)}")
        sys.exit(1)

    preview = ThemePreview(theme_manager)
    preview.print_preview(theme)


@tui.command(name="set-theme")
@click.argument("theme_name")
def tui_set_theme(theme_name: str) -> None:
    """Set the default theme."""
    from model_constellation.ui.cli_integration import get_theme_manager

    if get_theme_manager is None:
        console.print("[red]Error:[/red] TUI dependencies not available.")
        console.print("Please ensure pytermgui is properly installed.")
        sys.exit(1)
    theme_manager = get_theme_manager()

    if not theme_manager.set_theme(theme_name):
        available = [t.name for t in theme_manager.list_themes()]
        console.print(f"[red]Error:[/red] Theme '{theme_name}' not found")
        console.print(f"Available: {', '.join(available)}")
        sys.exit(1)

    theme_manager.apply_theme()
    current = theme_manager.get_current_theme()
    if current:
        console.print(f"Theme set to: {current.display_name}")
    else:
        console.print(f"Theme set to: {theme_name}")


@cli.command()
@click.option("--host", default="127.0.0.1", help="Bind host")
@click.option("--port", type=int, default=8000, help="Bind port")
@click.option("--allow-tools", is_flag=True, help="Permit tool execution over HTTP")
@click.option("--model", type=str, help="Default model for the API")
@click.option(
    "--permission-mode",
    type=click.Choice(["allow-all", "deny-all"]),
    default="deny-all",
    help="Default permission policy (interactive modes are not allowed over HTTP)",
)
@click.option("--api-key", type=str, help="Require this API key on requests")
@click.pass_context
def serve(
    ctx: click.Context,
    host: str,
    port: int,
    allow_tools: bool,
    model: Optional[str],
    permission_mode: str,
    api_key: Optional[str],
) -> None:
    """Start the HTTP API server (requires the 'api' extra)."""
    config = ctx.obj.get("config")
    try:
        import uvicorn

        from model_constellation.api.server import APISettings, create_app
    except ImportError:
        console.print("[red]Error:[/red] The API server requires extra dependencies.")
        console.print('Install with:  pip install "model-constellation[api]"')
        sys.exit(1)

    settings = APISettings(
        ollama_url=config.ollama.base_url if config else "http://localhost:11434",
        default_model=model or (config.ollama.default_model if config else "llama3.1"),
        allow_tools=allow_tools,
        default_permission_mode=permission_mode,
        api_key=api_key,
    )
    app = create_app(settings)

    console.print(f"[green]model-constellation API[/green] on http://{host}:{port}")
    console.print(f"  Ollama: {settings.ollama_url} | model: {settings.default_model}")
    console.print(f"  Tools over HTTP: {'enabled' if allow_tools else 'disabled (safe default)'}")
    if api_key:
        console.print("  Auth: API key required")
    uvicorn.run(app, host=host, port=port)


@cli.command()
def version() -> None:
    """Show model-constellation version."""
    from model_constellation import __version__

    console.print(f"model-constellation version {__version__}")


def main() -> None:
    """Main entry point for model-constellation CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
