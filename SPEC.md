# Tars - Ollama-Powered CLI AI Agent Framework

## Specification Document v1.0

> **Status note (as of v1.1.0):** This is the original design specification. The project
> shipped as **model-constellation** and the agent, tools, and permission subsystems are now
> implemented and wired together through a standardized `AgentRuntime`, with a Python SDK and
> an HTTP API. For the as-built system, see [`docs/`](docs/README.md) — especially
> [docs/06-agent-runtime.md](docs/06-agent-runtime.md) and
> [docs/07-backend-api.md](docs/07-backend-api.md). Some details below predate the
> implementation: the project/config prefix is `model-constellation` (env vars are
> `MODEL_CONSTELLATION_*`, not `TARS_*`) and the current version is 1.1.0.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Core Components](#3-core-components)
4. [Feature Specifications](#4-feature-specifications)
5. [Data Structures](#5-data-structures)
6. [CLI Commands](#6-cli-commands)
7. [Configuration](#7-configuration)
8. [Permission System](#8-permission-system)
9. [API Specifications](#9-api-specifications)

---

## 1. Project Overview

### 1.1 Introduction

**Tars** is an advanced CLI AI agent framework powered by Ollama, designed to function similarly to Claude CLI or Kilo Code. It provides a sophisticated multi-agent system capable of creating, managing, and coordinating sub-agents and agent swarms for complex task execution.

### 1.2 Core Philosophy

- **Autonomy with Oversight**: Agents operate with varying levels of independence while maintaining user control
- **Hierarchical Agent Management**: Primary planning agent coordinates sub-agents in structured hierarchies
- **Transparent Operations**: All agent actions, decisions, and communications are logged and auditable
- **Permission-Based Execution**: Two distinct permission modes for tool execution
- **Flexible Communication**: Multiple inter-agent communication patterns

### 1.3 Primary Use Cases

1. **Complex Task Decomposition**: Break down complex tasks into manageable sub-tasks executed by specialized agents
2. **Agent Swarm Coordination**: Manage multiple agents working in parallel on related tasks
3. **Iterative Problem Solving**: Primary agent plans, delegates, and synthesizes results from sub-agents
4. **Tool-Augmented Operations**: AI agents execute real-world commands via CLI tools
5. **Research and Exploration**: Query Ollama models for information with agentic oversight

### 1.4 Goals

1. Provide a seamless CLI experience for AI-powered task execution
2. Enable sophisticated multi-agent workflows
3. Maintain full user control over agent actions
4. Support extensible tool and agent systems
5. Offer comprehensive logging and debugging capabilities

---

## 2. Architecture

### 2.1 System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Tars CLI Framework                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     ┌──────────────────────────────────────────┐    │
│  │   User CLI   │────▶│              Session Manager              │    │
│  │   Interface  │     └──────────────────────────────────────────┘    │
│  └──────────────┘                    │                                  │
│                                       ▼                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Permission Coordinator                       │   │
│  │         (First-Time Mode / Every-Time Mode)                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                       │                                  │
│                                       ▼                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Agent Coordinator                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │   │
│  │  │   Primary   │  │  Sub-Agent  │  │    Agent Swarm          │ │   │
│  │  │   Agent     │  │   Pool      │  │    Manager              │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                       │                                  │
│                                       ▼                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Tool Executor                                 │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐ │   │
│  │  │   Bash     │  │   File     │  │   Search   │  │   Custom  │ │   │
│  │  │   Tool     │  │   Tools    │  │   Tools    │  │   Tools   │ │   │
│  │  └────────────┘  └────────────┘  └────────────┘  └───────────┘ │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                       │                                  │
│                                       ▼                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Ollama Provider                              │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐                 │   │
│  │  │   Model    │  │  Parameter │  │  Context   │                 │   │
│  │  │   Manager  │  │   Tuner    │  │  Manager   │                 │   │
│  │  └────────────┘  └────────────┘  └────────────┘                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                       │                                  │
│                                       ▼                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Ollama Backend (localhost:11434)             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Layer Architecture

```
┌────────────────────────────────────────────────┐
│            Presentation Layer                 │
│         (pytermgui TUI / CLI Output)          │
├────────────────────────────────────────────────┤
│            Command Layer                      │
│         (CLI Commands & Options)              │
├────────────────────────────────────────────────┤
│            Business Logic Layer               │
│   (Agents, Swarms, Tools, Permissions)        │
├────────────────────────────────────────────────┤
│            Data Layer                         │
│   (Config, History, Sessions, Logs)           │
├────────────────────────────────────────────────┤
│            Integration Layer                  │
│        (Ollama API Client)                    │
└────────────────────────────────────────────────┘
```

### 2.3 Component Relationships

```
User Input
    │
    ▼
┌─────────────────────────────────────────────────────┐
│                   Tars CLI Entry                    │
│                 (main.py / __main__)                │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│              Command Dispatcher                     │
│            (argparse / click handler)               │
└─────────────────────────────────────────────────────┘
    │
    ├──────────────────┬──────────────────┐
    ▼                  ▼                  ▼
┌─────────┐      ┌──────────┐      ┌──────────────┐
│  Agent  │      │  Config  │      │  Session    │
│ Manager │      │  Loader  │      │  Manager    │
└─────────┘      └──────────┘      └──────────────┘
    │                  │                  │
    └──────────────────┼──────────────────┘
                       ▼
              ┌──────────────────┐
              │  Ollama Client   │
              └──────────────────┘
```

---

## 3. Core Components

### 3.1 Agent System

#### 3.1.1 Primary Agent

The primary agent serves as the orchestrator and planning unit for all operations.

**Responsibilities:**
- Task decomposition and planning
- Sub-agent creation and delegation
- Result synthesis and response generation
- Conversation flow management

**Characteristics:**
- Has full context of all sub-agent activities
- Maintains the master conversation state
- Controls permission escalation
- Has access to all tools by default

#### 3.1.2 Sub-Agent

Sub-agents are specialized execution units created by the primary agent for specific tasks.

**Sub-Agent Types:**

1. **Specialized Agent**: Created for a specific domain (code, research, file operations)
2. **Worker Agent**: Parallel execution unit for subtasks
3. **Research Agent**: Information gathering and analysis
4. **Code Agent**: Software development and modification

**Sub-Agent Modes:**

| Mode | Communication | Description |
|------|---------------|-------------|
| `isolated` | Primary only | Sub-agent communicates only with primary planning agent |
| `swarm` | All agents | Sub-agent can communicate with other swarm agents |
| `hierarchical` | Parent only | Sub-agent reports only to parent agent |

#### 3.1.3 Agent Swarm

A collection of sub-agents working together on related tasks.

**Swarm Characteristics:**
- Shared context within the swarm
- Parallel or sequential task execution
- Coordinator agent for swarm management
- Result aggregation capability

### 3.2 Tool System

#### 3.2.1 Built-in Tools

| Tool Name | Description | Parameters |
|-----------|-------------|------------|
| `bash` | Execute shell commands | `command`, `timeout`, `environment` |
| `read` | Read file contents | `path`, `offset`, `limit` |
| `write` | Write content to files | `path`, `content`, `append` |
| `glob` | Find files by pattern | `pattern`, `path` |
| `grep` | Search file contents | `pattern`, `path`, `include` |
| `webfetch` | Fetch web content | `url`, `format` |
| `websearch` | Search the web | `query`, `num_results` |
| `codesearch` | Search code documentation | `query`, `tokens_num` |

#### 3.2.2 Custom Tool Definition

Tools can be defined in configuration with:

```yaml
tools:
  - name: "my_custom_tool"
    description: "Custom tool description"
    parameters:
      required: ["param1"]
      optional: ["param2"]
    command: "python /path/to/tool.py"
    schema: "json_schema_for_parameters"
```

### 3.3 Permission System

#### 3.3.1 Permission Modes

| Mode | Behavior |
|------|----------|
| `first-time` | Ask permission once per unique tool, remember for session |
| `every-time` | Always ask permission before each tool execution |
| `allow-all` | Execute all tools without prompting |
| `deny-all` | Block all tool executions |

#### 3.3.2 Permission Categories

- **File Operations**: read, write, glob, grep
- **System Operations**: bash, environment
- **Network Operations**: webfetch, websearch
- **Agent Operations**: create_agent, delegate_task

### 3.4 Session Management

#### 3.4.1 Session Types

| Type | Description | Persistence |
|------|-------------|--------------|
| `interactive` | Main CLI session | In-memory |
| `background` | Long-running task | Persistent |
| `saved` | Named session with history | File-based |

#### 3.4.2 Session Data

- Conversation history
- Agent states
- Tool execution log
- Permission cache

---

## 4. Feature Specifications

### 4.1 Agent Swarm Coordination

#### 4.1.1 Swarm Creation

```bash
model-constellation swarm create --name research_swarm --agents 5 --mode parallel
```

#### 4.1.2 Swarm Communication Patterns

**Broadcast**: Message sent to all swarm agents
**Direct**: Point-to-point communication
**Hierarchical**: Messages flow through coordinator
**Event-Based**: Agents react to shared events

#### 4.1.3 Swarm Execution Modes

| Mode | Description |
|------|-------------|
| `parallel` | All agents execute simultaneously |
| `sequential` | Agents execute one after another |
| `pipeline` | Output of one agent feeds the next |
| `adaptive` | Dynamic mode selection based on task |

### 4.2 Conversation History Management

#### 4.2.1 History Features

- Full message persistence
- Searchable history
- Session branching
- Import/export capabilities

#### 4.2.2 History Configuration

```yaml
history:
  max_messages: 10000
  max_tokens: 128000
  storage_path: ".model-constellation//.model-constellation/history"
  retention_days: 30
  compress: true
```

### 4.3 Model Parameter Tuning

#### 4.3.1 Adjustable Parameters

| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| `temperature` | 0.0-2.0 | 0.7 | Sampling temperature |
| `top_p` | 0.0-1.0 | 0.9 | Nucleus sampling |
| `top_k` | 1-100 | 40 | Top-k sampling |
| `repeat_penalty` | 0.0-2.0 | 1.1 | Repetition penalty |
| `seed` | int | random | Random seed |
| `num_ctx` | 128-128000 | 4096 | Context window size |
| `num_gpu` | 0-100 | -1 | GPU layers |
| `num_thread` | 1-32 | -1 | CPU threads |

#### 4.3.2 Parameter Presets

```yaml
presets:
  creative:
    temperature: 1.2
    top_p: 0.95
  precise:
    temperature: 0.3
    top_p: 0.8
  balanced:
    temperature: 0.7
    top_p: 0.9
```

### 4.4 Tool Definition System

#### 4.4.1 Tool Schema

```yaml
tools:
  - name: string
    description: string
    category: string
    parameters:
      type: object
      properties: {}
      required: []
    handler: string | python_module
    timeout: integer
    retry:
      max_attempts: integer
      backoff: exponential
```

#### 4.4.2 Dynamic Tool Loading

Tools can be loaded from:
- Built-in tool directory
- User's .model-constellation//.model-constellation/tools/
- Package entry points
- Runtime registration

### 4.5 Session Management

#### 4.5.1 Session Commands

```bash
# Create session
model-constellation session new --name my_session

# List sessions
model-constellation session list

# Resume session
model-constellation session resume my_session

# Save session
model-constellation session save my_session

# Delete session
model-constellation session delete my_session
```

### 4.6 Logging and Debugging

#### 4.6.1 Log Levels

| Level | Value | Usage |
|-------|-------|-------|
| `debug` | 0 | Detailed diagnostic info |
| `info` | 1 | General informational messages |
| `warning` | 2 | Warning messages |
| `error` | 3 | Error conditions |
| `critical` | 4 | Critical failures |

#### 4.6.2 Log Configuration

```yaml
logging:
  level: "info"
  file: ".model-constellation//.model-constellation/logs/model-constellation.log"
  max_size: "10MB"
  backup_count: 5
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  handlers:
    - console
    - file
```

#### 4.6.3 Debug Mode

```bash
model-constellation --debug run "your query"
model-constellation --trace run "your query"  # Verbose output
```

### 4.7 Configuration System

#### 4.7.1 Configuration Hierarchy

1. Default configuration (.model-constellation//.model-constellation/default.yaml)
2. Project configuration (./.model-constellation.yaml)
3. Environment variables (TARS_* prefix)
4. Command-line arguments

#### 4.7.2 Configuration Commands

```bash
model-constellation config init          # Create default config
model-constellation config show          # Display current config
model-constellation config validate      # Validate config syntax
model-constellation config edit          # Open config in editor
```

---

## 5. Data Structures

### 5.1 Agent Data Structures

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class AgentMode(Enum):
    ISOLATED = "isolated"
    SWARM = "swarm"
    HIERARCHICAL = "hierarchical"

class AgentType(Enum):
    PRIMARY = "primary"
    SPECIALIZED = "specialized"
    WORKER = "worker"
    RESEARCH = "research"
    CODE = "code"

@dataclass
class Agent:
    id: str
    name: str
    agent_type: AgentType
    mode: AgentMode
    model: str
    parameters: Dict[str, Any]
    system_prompt: str
    tools: List[str]
    parent_id: Optional[str] = None
    swarm_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentResult:
    agent_id: str
    status: str  # "success", "failed", "timeout"
    output: str
    error: Optional[str] = None
    duration_ms: int = 0
    tool_executions: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class Swarm:
    id: str
    name: str
    agents: List[Agent]
    mode: str  # "parallel", "sequential", "pipeline", "adaptive"
    coordinator_id: str
    shared_context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
```

### 5.2 Message Data Structures

```python
@dataclass
class Message:
    id: str
    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_result: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Conversation:
    id: str
    session_id: str
    agent_id: str
    messages: List[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
```

### 5.3 Tool Data Structures

```python
@dataclass
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = False
    default: Any = None

@dataclass
class Tool:
    name: str
    description: str
    category: str
    parameters: List[ToolParameter]
    handler: str  # module.function or command
    timeout: int = 30000
    retry_config: Optional[Dict[str, Any]] = None
    enabled: bool = True

@dataclass
class ToolExecution:
    id: str
    tool_name: str
    parameters: Dict[str, Any]
    result: Any
    status: str
    duration_ms: int
    timestamp: datetime = field(default_factory=datetime.now)
```

### 5.4 Session Data Structures

```python
@dataclass
class Session:
    id: str
    name: str
    agent: Agent
    conversation: Conversation
    created_at: datetime
    last_active: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PermissionCache:
    tool_name: str
    allowed: bool
    expires_at: datetime
    mode: str  # "first-time", "every-time"
```

### 5.5 Configuration Data Structures

```python
@dataclass
class OllamaConfig:
    base_url: str = "http://localhost:11434"
    default_model: str = "llama2"
    timeout: int = 120000
    keep_alive: str = "5m"

@dataclass
class ModelParameters:
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    seed: Optional[int] = None
    num_ctx: int = 4096
    num_gpu: int = -1
    num_thread: int = -1

@dataclass
class TarsConfig:
    ollama: OllamaConfig
    default_parameters: ModelParameters
    permission_mode: str = "first-time"
    history: Dict[str, Any]
    logging: Dict[str, Any]
    tools: List[Tool]
    agents: Dict[str, Any]
```

---

## 6. CLI Commands

### 6.1 Primary Commands

#### 6.1.1 Run Command

```bash
model-constellation run [OPTIONS] [QUERY]

Options:
  --agent, -a TEXT         Agent type (primary, code, research)
  --model, -m TEXT         Ollama model to use
  --temperature FLOAT     Set temperature (0.0-2.0)
  --top-p FLOAT           Set top_p (0.0-1.0)
  --swarm TEXT             Run with agent swarm
  --parallel              Enable parallel execution
  --timeout INTEGER       Request timeout in seconds
  --no-tools              Disable tool execution
  --permission-mode MODE  first-time|every-time|allow-all|deny-all
```

#### 6.1.2 Interactive Mode

```bash
model-constellation interactive [OPTIONS]
# or
model-constellation chat [OPTIONS]

Options:
  --session TEXT          Resume existing session
  --new-session TEXT      Create new named session
  --model TEXT            Ollama model
  --preserve-history      Keep history after exit
```

### 6.2 Agent Commands

#### 6.2.1 Create Agent

```bash
model-constellation agent create [OPTIONS] NAME

Options:
  --type TYPE             Agent type (specialized, worker, research, code)
  --mode MODE             Agent mode (isolated, swarm, hierarchical)
  --model TEXT            Ollama model
  --tools TEXT            Comma-separated tool list
  --system-prompt TEXT    Custom system prompt
  --parent TEXT           Parent agent ID for hierarchical mode
  --swarm TEXT            Swarm ID to join
```

#### 6.2.2 List Agents

```bash
model-constellation agent list [OPTIONS]

Options:
  --type TYPE             Filter by agent type
  --swarm TEXT            Filter by swarm
  --verbose, -v           Show detailed info
```

#### 6.2.3 Agent Info

```bash
model-constellation agent info [OPTIONS] AGENT_ID

Options:
  --history               Show conversation history
  --tools                 Show available tools
  --parameters            Show model parameters
```

#### 6.2.4 Delete Agent

```bash
model-constellation agent delete AGENT_ID [--force]
```

### 6.3 Swarm Commands

#### 6.3.1 Create Swarm

```bash
model-constellation swarm create [OPTIONS] NAME

Options:
  --agents INTEGER        Number of agents (default: 3)
  --mode MODE             Execution mode (parallel, sequential, pipeline)
  --type TYPE             Agent type for swarm members
  --model TEXT            Model for all swarm agents
  --shared-tools TEXT     Tools available to all agents
```

#### 6.3.2 List Swarms

```bash
model-constellation swarm list [OPTIONS]

Options:
  --verbose, -v           Show detailed info
  --active-only           Show only active swarms
```

#### 6.3.3 Swarm Info

```bash
model-constellation swarm info SWARM_ID

Options:
  --agents                List all agents in swarm
  --status                Show execution status
  --history               Show swarm activity
```

#### 6.3.4 Run Swarm

```bash
model-constellation swarm run SWARM_ID TASK

Options:
  --wait                  Wait for completion
  --timeout INTEGER       Timeout in seconds
  --output-format FORMAT  json, text, stream
```

#### 6.3.5 Delete Swarm

```bash
model-constellation swarm delete SWARM_ID [--force]
```

### 6.4 Model Commands

#### 6.4.1 List Models

```bash
model-constellation model list

Options:
  --local                 Show only local models
  --remote                Show available remote models
  --detailed              Show model details
```

#### 6.4.2 Query Model Parameters

```bash
model-constellation model params MODEL_NAME

Options:
  --show-presets          Show available parameter presets
```

#### 6.4.3 Pull Model

```bash
model-constellation model pull MODEL_NAME [--force]
```

### 6.5 Session Commands

```bash
model-constellation session new [--name TEXT]
model-constellation session list
model-constellation session resume SESSION_ID
model-constellation session save SESSION_ID [--name TEXT]
model-constellation session delete SESSION_ID
model-constellation session export SESSION_ID [--format json|markdown]
```

### 6.6 Configuration Commands

```bash
model-constellation config init
model-constellation config show [--format yaml|json]
model-constellation config validate
model-constellation config edit
model-constellation config path          # Show config file path
```

### 6.7 Tool Commands

```bash
model-constellation tool list             # List available tools
model-constellation tool info TOOL_NAME   # Show tool details
model-constellation tool add TOOL_DEF     # Add custom tool
model-constellation tool remove TOOL_NAME # Remove custom tool
model-constellation tool test TOOL_NAME  # Test tool execution
```

### 6.8 Permission Commands

```bash
model-constellation permission status     # Show current permission mode
model-constellation permission set MODE   # Set permission mode
model-constellation permission allow TOOL # Allow tool (first-time mode)
model-constellation permission deny TOOL  # Deny tool
model-constellation permission reset      # Reset all cached permissions
```

### 6.9 Utility Commands

```bash
model-constellation logs [OPTIONS]        # View logs
  --level LEVEL            # Filter by level
  --agent ID               # Filter by agent
  --tail INTEGER           # Last N lines
  --follow                 # Stream logs

model-constellation version              # Show version
model-constellation doctor               # Run diagnostics
model-constellation completions SHELL    # Generate completions
```

---

## 7. Configuration

### 7.1 Default Configuration File

Location: `.model-constellation//.model-constellation/config.yaml`

```yaml
version: "1.0"

# Ollama Connection Settings
ollama:
  base_url: "http://localhost:11434"
  default_model: "llama2"
  timeout: 120000  # milliseconds
  keep_alive: "5m"

# Default Model Parameters
parameters:
  temperature: 0.7
  top_p: 0.9
  top_k: 40
  repeat_penalty: 1.1
  num_ctx: 4096
  num_gpu: -1  # Auto-detect
  num_thread: -1  # Auto-detect

# Parameter Presets
presets:
  creative:
    temperature: 1.2
    top_p: 0.95
  precise:
    temperature: 0.3
    top_p: 0.8
  balanced:
    temperature: 0.7
    top_p: 0.9

# Permission System
permission:
  mode: "first-time"  # first-time, every-time, allow-all, deny-all
  cache_ttl: 3600  # seconds
  denied_tools: []

# Conversation History
history:
  max_messages: 10000
  max_tokens: 128000
  storage_path: ".model-constellation//.model-constellation/history"
  retention_days: 30
  compress: true

# Logging Configuration
logging:
  level: "info"  # debug, info, warning, error, critical
  file: ".model-constellation//.model-constellation/logs/model-constellation.log"
  max_size: "10MB"
  backup_count: 5
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  handlers:
    - console
    - file

# Tool Configuration
tools:
  enabled:
    - bash
    - read
    - write
    - glob
    - grep
    - webfetch
    - websearch
    - codesearch
  
  custom: []
  
  defaults:
    timeout: 30000
    retry:
      max_attempts: 3
      backoff: "exponential"

# Agent Configuration
agents:
  default_type: "primary"
  default_mode: "isolated"
  max_agents: 10
  max_swarm_size: 20
  default_system_prompt: |
    You are Tars, an AI assistant powered by Ollama.
    You can execute tools to help complete tasks.
    Always explain your reasoning and ask for clarification when needed.

# Swarm Configuration
swarm:
  default_mode: "parallel"
  max_concurrent: 5
  coordination_timeout: 30000

# Session Configuration
session:
  default_name: "interactive"
  auto_save: true
  auto_save_interval: 300  # seconds

# UI Configuration
ui:
  theme: "default"
  color: true
  show_tokens: false
  streaming: true
```

### 7.2 Project Configuration

Location: `./.model-constellation.yaml` (in project directory)

```yaml
# Project-specific overrides
ollama:
  model: "codellama"  # Override default model

parameters:
  temperature: 0.5

tools:
  enabled:
    - bash
    - read
    - write
    - glob
    - grep

agents:
  default_system_prompt: |
    You are a code-focused AI assistant.
    Prioritize writing clean, efficient code.

# Project-specific custom tools
custom_tools:
  - name: "pytest"
    description: "Run pytest tests"
    command: "pytest {args}"
```

### 7.3 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TARS_BASE_URL` | Ollama base URL | http://localhost:11434 |
| `TARS_MODEL` | Default model | llama2 |
| `TARS_CONFIG` | Config file path | .model-constellation//.model-constellation/config.yaml |
| `TARS_PERMISSION_MODE` | Permission mode | first-time |
| `TARS_LOG_LEVEL` | Log level | info |
| `TARS_NO_COLOR` | Disable colors | false |

---

## 8. Permission System

### 8.1 Permission Flow

```
User Query
    │
    ▼
┌─────────────────────────────┐
│   Agent Processing          │
│   (Analyzes query)           │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│   Tool Execution Request    │
│   (Identifies needed tools) │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│   Permission Coordinator    │
└─────────────────────────────┘
    │
    ├─► Mode: first-time ──▶ Check cache
    │       ├── Cache hit ──▶ Execute/Deny
    │       └── Cache miss ──▶ Prompt user
    │
    ├─► Mode: every-time ──▶ Prompt user
    │
    ├─► Mode: allow-all ──▶ Execute
    │
    └─► Mode: deny-all ──▶ Deny
    │
    ▼
┌─────────────────────────────┐
│   Tool Executor             │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│   Return Result to Agent    │
└─────────────────────────────┘
```

### 8.2 Permission Modes Detail

#### 8.2.1 First-Time Mode (Default)

- First execution of any tool prompts user
- Decision is cached for the session
- User can override cached decisions
- Most convenient while maintaining safety

#### 8.2.2 Every-Time Mode

- Prompts before every tool execution
- Maximum safety
- Use cases: security-sensitive environments, new tool testing
- Flag: `--permission-mode every-time`

#### 8.2.3 Allow-All Mode

- Executes all tools without prompting
- Use cases: trusted automation, batch processing
- Warning: Use with caution
- Flag: `--permission-mode allow-all`

#### 8.2.4 Deny-All Mode

- Blocks all tool executions
- Use cases: query-only mode, testing
- Allows AI to reason without acting
- Flag: `--permission-mode deny-all`

### 8.3 Permission Cache

```python
@dataclass
class PermissionCache:
    tool_name: str
    action: str  # "allow" or "deny"
    timestamp: datetime
    expires_in: int  # seconds
    session_id: str

# Cache is session-scoped
# Cleared on session end or manual reset
```

### 8.4 User Prompt Format

```
┌─────────────────────────────────────────────────────────┐
│  ⚠️  Tool Execution Request                             │
├─────────────────────────────────────────────────────────┤
│  Tool: bash                                             │
│  Command: rm -rf /important                            │
│                                                          │
│  This tool will: Delete files irreversibly             │
│                                                          │
│  [Allow] [Deny] [Allow All Session] [View Context]     │
└─────────────────────────────────────────────────────────┘
```

### 8.5 Dangerous Tool Detection

Automatically flag high-risk operations:

| Tool | Risk Level | Additional Prompt |
|------|------------|-------------------|
| `bash` (rm, del, format) | Critical | "This will permanently delete data" |
| `bash` (sudo, su) | Critical | "This executes with elevated privileges" |
| `write` (overwrite) | High | "This will overwrite existing file" |
| `network` | Medium | "This will make network request" |

---

## 9. API Specifications

### 9.1 Ollama API Integration

#### 9.1.1 Direct Ollama Endpoints

```python
# Chat Completion
POST /api/chat
{
  "model": "llama2",
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "stream": false,
  "options": {
    "temperature": 0.7,
    "top_p": 0.9
  }
}

# Generate Completion
POST /api/generate
{
  "model": "llama2",
  "prompt": "Write a function",
  "stream": false,
  "options": {}
}

# List Models
GET /api/tags

# Pull Model
POST /api/pull
{
  "name": "llama2",
  "stream": false
}
```

#### 9.1.2 Tars API Wrapper

```python
class OllamaClient:
    def __init__(self, base_url: str, timeout: int):
        self.base_url = base_url
        self.timeout = timeout
    
    def chat(
        self,
        model: str,
        messages: List[Dict],
        stream: bool = False,
        **options
    ) -> Dict:
        """Send chat completion request"""
    
    def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
        **options
    ) -> Dict:
        """Send generation request"""
    
    def list_models(self) -> List[str]:
        """List available models"""
    
    def pull_model(self, name: str, stream: bool = False):
        """Pull a model from library"""
    
    def get_model_info(self, name: str) -> Dict:
        """Get model information"""
```

### 9.2 Internal Agent API

```python
class AgentManager:
    def create_agent(
        self,
        name: str,
        agent_type: AgentType,
        model: str,
        system_prompt: str,
        tools: List[str],
        mode: AgentMode = AgentMode.ISOLATED,
        parent_id: Optional[str] = None,
        swarm_id: Optional[str] = None
    ) -> Agent:
        """Create a new agent"""
    
    def get_agent(self, agent_id: str) -> Agent:
        """Get agent by ID"""
    
    def list_agents(self, filters: Dict) -> List[Agent]:
        """List agents with optional filters"""
    
    def delete_agent(self, agent_id: str):
        """Delete an agent"""
    
    def execute_agent(
        self,
        agent_id: str,
        prompt: str,
        context: Dict = None
    ) -> AgentResult:
        """Execute agent with prompt"""

class SwarmManager:
    def create_swarm(
        self,
        name: str,
        agent_count: int,
        mode: str,
        agent_type: AgentType,
        model: str
    ) -> Swarm:
        """Create a new agent swarm"""
    
    def execute_swarm(
        self,
        swarm_id: str,
        task: str,
        wait: bool = True
    ) -> List[AgentResult]:
        """Execute task on swarm"""
    
    def get_swarm_status(self, swarm_id: str) -> SwarmStatus:
        """Get swarm execution status"""
    
    def terminate_swarm(self, swarm_id: str):
        """Terminate swarm execution"""
```

### 9.3 Tool Execution API

```python
class ToolExecutor:
    def __init__(self, config: ToolConfig):
        self.tools = self._load_tools()
    
    def execute(
        self,
        tool_name: str,
        parameters: Dict,
        timeout: int = None
    ) -> ToolExecution:
        """Execute a tool with given parameters"""
    
    def register_tool(self, tool: Tool):
        """Register a new tool"""
    
    def unregister_tool(self, tool_name: str):
        """Unregister a tool"""
    
    def list_tools(self) -> List[Tool]:
        """List all available tools"""

class BashTool:
    def execute(
        self,
        command: str,
        timeout: int = 30000,
        environment: Dict = None
    ) -> str:
        """Execute bash command"""

class FileTool:
    def read(self, path: str, offset: int = 0, limit: int = None) -> str:
        """Read file contents"""
    
    def write(self, path: str, content: str, append: bool = False):
        """Write content to file"""
    
    def glob(self, pattern: str, path: str = ".") -> List[str]:
        """Find files matching pattern"""
    
    def grep(self, pattern: str, path: str = ".") -> List[Dict]:
        """Search file contents"""
```

### 9.4 Session API

```python
class SessionManager:
    def create_session(
        self,
        name: str,
        agent: Agent,
        metadata: Dict = None
    ) -> Session:
        """Create new session"""
    
    def get_session(self, session_id: str) -> Session:
        """Get session by ID"""
    
    def list_sessions(self) -> List[Session]:
        """List all sessions"""
    
    def save_session(self, session_id: str):
        """Persist session to disk"""
    
    def load_session(self, session_id: str) -> Session:
        """Load session from disk"""
    
    def delete_session(self, session_id: str):
        """Delete session"""
    
    def add_message(self, session_id: str, message: Message):
        """Add message to session conversation"""
    
    def get_history(
        self,
        session_id: str,
        limit: int = None
    ) -> List[Message]:
        """Get conversation history"""
```

### 9.5 Permission API

```python
class PermissionManager:
    def __init__(self, mode: str, cache_ttl: int):
        self.mode = mode
        self.cache_ttl = cache_ttl
        self._cache = {}
    
    def check_permission(
        self,
        tool_name: str,
        parameters: Dict
    ) -> PermissionResult:
        """Check if tool execution is allowed"""
    
    def prompt_user(
        self,
        tool_name: str,
        parameters: Dict
    ) -> bool:
        """Prompt user for permission"""
    
    def cache_decision(
        self,
        tool_name: str,
        allowed: bool
    ):
        """Cache permission decision"""
    
    def get_cached_decision(self, tool_name: str) -> Optional[bool]:
        """Get cached permission decision"""
    
    def clear_cache(self):
        """Clear all cached permissions"""
    
    def set_mode(self, mode: str):
        """Change permission mode"""
```

---

## 10. Implementation Notes

### 10.1 Project Structure

```
model-constellation/
├── model-constellation/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── commands.py
│   │   ├── formatters.py
│   │   └── completer.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── swarm.py
│   │   ├── tool.py
│   │   ├── session.py
│   │   └── permission.py
│   ├── ollama/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── models.py
│   │   └── parameters.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   ├── schema.py
│   │   └── defaults.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── terminal.py
│   │   ├── prompts.py
│   │   └── theme.py
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       └── helpers.py
├── tests/
├── tools/
├── examples/
├── pyproject.toml
├── setup.py
├── README.md
└── SPEC.md
```

### 10.2 Dependencies

```toml
[project]
name = "model-constellation"
version = "1.0.0"
description = "Ollama-powered CLI AI agent framework"
requires-python = ">=3.10"

dependencies = [
    "pytermgui>=7.0.0",
    "pyyaml>=6.0",
    "requests>=2.31.0",
    "click>=8.1.0",
    "rich>=13.0.0",
    "shtab>=1.5.0",
    "python-dotenv>=1.0.0",
    "aiohttp>=3.9.0",
    "tenacity>=8.2.0",
]
```

---

## 11. Future Enhancements

### 11.1 Planned Features

1. **Agent Memory System**: Persistent memory across sessions
2. **Multi-Model Routing**: Route to different models based on task
3. **Plugin System**: Extend functionality via plugins
4. **Web UI**: Browser-based interface option
5. **Team Collaboration**: Share agents and workflows
6. **Metrics Dashboard**: Agent performance analytics

### 11.2 Extension Points

- Custom tool handlers
- Agent behavior plugins
- Output formatters
- Model adapters
- Storage backends

---

## 12. Glossary

| Term | Definition |
|------|------------|
| Primary Agent | Main orchestrator agent that plans and coordinates |
| Sub-Agent | Specialized agent created by primary for specific tasks |
| Agent Swarm | Collection of agents working together |
| Permission Mode | Controls when user is prompted for tool execution |
| Tool | Executable capability available to agents |
| Session | Persistent conversation context |
| Swarm Mode | Execution pattern for multiple agents |

---

*Document Version: 1.0*  
*Last Updated: 2026-03-16*  
*Project: Tars - Ollama-Powered CLI AI Agent Framework*
