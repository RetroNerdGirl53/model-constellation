# model-constellation - Ollama-Powered CLI AI Agent Framework

model-constellation is a powerful CLI framework that brings AI agent capabilities to your terminal. Built on top of [Ollama](https://github.com/ollama/ollama), it enables you to create and manage AI agents that can execute tasks, run commands, and collaborate in swarms.

## Features

- **AI-Powered CLI**: Interact with Ollama models directly from your terminal
- **Agent Management**: Create, manage, and orchestrate multiple AI agents
- **Agent Swarms**: Coordinate multiple agents to work on complex tasks in parallel
- **Tool Execution**: Agents can execute real commands with configurable permission controls
- **Interactive Mode**: Chat with AI agents in an interactive terminal session
- **Flexible Configuration**: Customize models, permissions, and behavior via YAML config
- **Rich UI**: Beautiful terminal interface powered by Rich
- **Tool use & permissions**: Agents call tools (read/write files, run commands,
  search) gated by a permission system with danger detection
- **Use as a library or HTTP backend**: a standardized `AgentRuntime` engine, plus an
  optional FastAPI server, so other apps can embed it

## Documentation

Developer docs live in [`docs/`](docs/README.md):

- [Overview](docs/01-overview.md) and [Architecture](docs/02-architecture.md)
- [Code walkthrough](docs/03-code-walkthrough.md) and [Python concepts](docs/04-python-concepts.md)
- [Agent runtime](docs/06-agent-runtime.md) — how the agent, tools, and permission
  frameworks are wired together
- [Backend API](docs/07-backend-api.md) — using model-constellation as a Python SDK or
  HTTP server

## Use as a Library or HTTP Backend

**Python SDK:**

```python
from model_constellation import AgentRuntime, OllamaClient

runtime = AgentRuntime(OllamaClient(base_url="http://localhost:11434"),
                       model="llama3.1", permission_mode="allow-all")
result = runtime.run("List the Python files here and count them")
print(result.content)

# Multi-/cross-model swarm
swarm = runtime.run_swarm("Summarize the project",
                          [{"name": "a", "model": "llama3.1"},
                           {"name": "b", "model": "qwen2.5"}], mode="parallel")
```

**HTTP API** (FastAPI, safe-by-default — tools opt-in, no interactive prompts over the wire):

```bash
pip install "model-constellation[api]"
model-constellation serve --host 0.0.0.0 --port 8000     # add --allow-tools to enable tools

curl -s localhost:8000/v1/chat -d '{"prompt":"Say hello","model":"llama3.1"}'
```

See [docs/07-backend-api.md](docs/07-backend-api.md) for the full SDK and endpoint reference.

## Requirements

- Python 3.10+
- Ollama server running locally (default: http://localhost:11434) or remotely

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/model_constellation/model_constellation.git
cd model_constellation

# Install in development mode
pip install -e .

# Or install normally
pip install .
```

### Using pip

```bash
pip install model_constellation
```

### Verify Installation

```bash
model-constellation --version
```

## Quick Start

### Basic Query

```bash
# Run a simple query
model-constellation run "What is the capital of France?"
```

### Interactive Mode

```bash
# Start an interactive chat session
model-constellation interactive

# Or with specific model
model-constellation interactive --model llama2
```

### Agent Management

```bash
# Create a new agent
model-constellation agent create my-agent --type specialized

# List all agents
model-constellation agent list

# Get agent info
model-constellation agent info my-agent

# Delete an agent
model-constellation agent delete my-agent --force
```

### Model Management

```bash
# List available local models
model-constellation model list --local

# List available remote models
model-constellation model list --remote

# Pull a new model
model-constellation model pull mistral
```

### Agent Swarms

```bash
# Create a swarm
model-constellation swarm create research-swarm --agents 5 --mode parallel

# Run task on swarm
model-constellation swarm run research-swarm "Research quantum computing"

# List swarms
model-constellation swarm list
```

### Configuration

```bash
# Initialize default config
model-constellation config init

# Show current config
model-constellation config show

# Validate config
model-constellation config validate

# Edit config in editor
model-constellation config edit

# Show config path
model-constellation config path
```

## CLI Commands Reference

### Global Options

| Option | Description |
|--------|-------------|
| `--debug` | Enable debug mode |
| `--config PATH` | Use custom config file |

### Main Commands

| Command | Description |
|---------|-------------|
| `model-constellation run [QUERY]` | Run a query with the agent |
| `model-constellation interactive` | Start interactive session |
| `model-constellation version` | Show version info |

### Agent Subcommands

| Command | Description |
|---------|-------------|
| `model-constellation agent create NAME` | Create a new agent |
| `model-constellation agent list` | List all agents |
| `model-constellation agent info ID` | Show agent information |
| `model-constellation agent delete ID` | Delete an agent |

### Swarm Subcommands

| Command | Description |
|---------|-------------|
| `model-constellation swarm create NAME` | Create a new swarm |
| `model-constellation swarm list` | List all swarms |
| `model-constellation swarm info ID` | Show swarm information |
| `model-constellation swarm run ID TASK` | Run task on swarm |
| `model-constellation swarm delete ID` | Delete a swarm |

### Model Subcommands

| Command | Description |
|---------|-------------|
| `model-constellation model list` | List available models |
| `model-constellation model params NAME` | Show model parameters |
| `model-constellation model pull NAME` | Pull a model from library |

### Config Subcommands

| Command | Description |
|---------|-------------|
| `model-constellation config init` | Create default configuration |
| `model-constellation config show` | Display current config |
| `model-constellation config validate` | Validate config syntax |
| `model-constellation config edit` | Open config in editor |
| `model-constellation config path` | Show config file path |

## Configuration Guide

### Default Configuration Location

- Linux/macOS: `.model-constellation//.model-constellation/config.yaml`
- Windows: `%USERPROFILE%\.model-constellation\config.yaml`

### Configuration File Format

```yaml
# .model-constellation//.model-constellation/config.yaml

# Ollama connection
ollama:
  base_url: "http://localhost:11434"
  default_model: "llama2"
  timeout: 120000

# Agent defaults
agent:
  default_type: "specialized"
  default_mode: "isolated"
  max_agents: 10

# Permission settings
permissions:
  mode: "first-time"
  allowed_tools:
    - bash
    - read
    - glob
    - grep
  denied_commands:
    - rm
    - del

# Logging
logging:
  level: "info"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MODEL_CONSTELLATION_BASE_URL` | Ollama server URL | http://localhost:11434 |
| `MODEL_CONSTELLATION_MODEL` | Default model | llama2 |
| `MODEL_CONSTELLATION_CONFIG` | Config file path | .model-constellation//.model-constellation/config.yaml |
| `MODEL_CONSTELLATION_PERMISSION_MODE` | Permission mode | first-time |
| `MODEL_CONSTELLATION_LOG_LEVEL` | Logging level | info |

## Examples

### Simple Query

```bash
$ model-constellation run "List files in current directory"
Query: List files in current directory
...
```

### Create Specialized Agent

```bash
$ model-constellation agent create coder --type code --tools bash,read,write,glob
Creating agent: coder
   Type: code
   Mode: isolated
```

### Research with Swarm

```bash
$ model-constellation swarm create research-team --agents 3 --mode parallel
Creating swarm: research-team
   Agents: 3
   Mode: parallel

$ model-constellation swarm run research-team "Summarize latest AI news"
```

### Custom Model Parameters

```bash
$ model-constellation run "Write a poem" --model codellama --temperature 0.9 --top-p 0.95
```

## Development

### Setup Development Environment

```bash
# Clone and install with dev dependencies
git clone https://github.com/model_constellation/model_constellation.git
cd model_constellation
pip install -e ".[dev]"

# Run tests
pytest

# Run linters
ruff check .
black --check .
mypy model_constellation/
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request on GitHub.

## Support

- Bug Reports: https://github.com/model_constellation/model_constellation/issues
- Documentation: https://github.com/model_constellation/model_constellation#readme
