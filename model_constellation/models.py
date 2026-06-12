"""Data models for model-constellation using Pydantic."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentMode(str, Enum):
    ISOLATED = "isolated"
    SWARM = "swarm"
    HIERARCHICAL = "hierarchical"


class AgentType(str, Enum):
    PRIMARY = "primary"
    SPECIALIZED = "specialized"
    WORKER = "worker"
    RESEARCH = "research"
    CODE = "code"


class PermissionMode(str, Enum):
    FIRST_TIME = "first-time"
    EVERY_TIME = "every-time"
    ALLOW_ALL = "allow-all"
    DENY_ALL = "deny-all"


class SwarmMode(str, Enum):
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    PIPELINE = "pipeline"
    ADAPTIVE = "adaptive"


class Message(BaseModel):
    id: str
    role: str
    content: str
    tool_calls: Optional[list[dict[str, Any]]] = None
    tool_result: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = False
    default: Any = None


class ToolDefinition(BaseModel):
    name: str
    description: str
    category: str
    parameters: list[ToolParameter]
    handler: str
    timeout: int = 30000
    retry_config: Optional[dict[str, Any]] = None
    enabled: bool = True


class ToolExecution(BaseModel):
    id: str
    tool_name: str
    parameters: dict[str, Any]
    result: Any
    status: str
    duration_ms: int
    timestamp: datetime = Field(default_factory=datetime.now)


class Agent(BaseModel):
    id: str
    name: str
    agent_type: AgentType
    mode: AgentMode
    model: str
    parameters: dict[str, Any]
    system_prompt: str
    tools: list[str]
    parent_id: Optional[str] = None
    swarm_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    agent_id: str
    status: str
    output: str
    error: Optional[str] = None
    duration_ms: int = 0
    tool_executions: list[dict[str, Any]] = Field(default_factory=list)


class Swarm(BaseModel):
    id: str
    name: str
    agents: list[Agent]
    mode: SwarmMode
    coordinator_id: str
    shared_context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


class Conversation(BaseModel):
    id: str
    session_id: str
    agent_id: str
    messages: list[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Session(BaseModel):
    id: str
    name: str
    agent: Agent
    conversation: Conversation
    created_at: datetime
    last_active: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class PermissionCache(BaseModel):
    tool_name: str
    allowed: bool
    expires_at: datetime
    mode: str


class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    default_model: str = "llama2"
    timeout: int = 120000
    keep_alive: str = "5m"


class ModelParameters(BaseModel):
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    seed: Optional[int] = None
    num_ctx: int = 4096
    num_gpu: int = -1
    num_thread: int = -1


class ParameterPreset(BaseModel):
    name: str
    temperature: float
    top_p: float
    top_k: int = 40
    repeat_penalty: float = 1.1


class PermissionConfig(BaseModel):
    mode: PermissionMode = PermissionMode.FIRST_TIME
    cache_ttl: int = 3600
    denied_tools: list[str] = Field(default_factory=list)


class HistoryConfig(BaseModel):
    max_messages: int = 10000
    max_tokens: int = 128000
    storage_path: str = "~/.model-constellation/history"
    retention_days: int = 30
    compress: bool = True


class LoggingConfig(BaseModel):
    level: str = "info"
    file: str = "~/.model-constellation/logs/model_constellation.log"
    max_size: str = "10MB"
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    handlers: list[str] = Field(default_factory=lambda: ["console", "file"])


class ToolConfig(BaseModel):
    enabled: list[str] = Field(default_factory=list)
    custom: list[ToolDefinition] = Field(default_factory=list)
    defaults: dict[str, Any] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    default_type: AgentType = AgentType.PRIMARY
    default_mode: AgentMode = AgentMode.ISOLATED
    max_agents: int = 10
    max_swarm_size: int = 20
    default_system_prompt: str = ""


class SwarmConfig(BaseModel):
    default_mode: SwarmMode = SwarmMode.PARALLEL
    max_concurrent: int = 5
    coordination_timeout: int = 30000


class SessionConfig(BaseModel):
    default_name: str = "interactive"
    auto_save: bool = True
    auto_save_interval: int = 300


class UIConfig(BaseModel):
    theme: str = "default"
    color: bool = True
    show_tokens: bool = False
    streaming: bool = True


class PresetsConfig(BaseModel):
    creative: Optional[ParameterPreset] = None
    precise: Optional[ParameterPreset] = None
    balanced: Optional[ParameterPreset] = None


class ModelConstellationConfig(BaseModel):
    version: str = "1.0"
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    parameters: ModelParameters = Field(default_factory=ModelParameters)
    presets: Optional[PresetsConfig] = None
    permission: PermissionConfig = Field(default_factory=PermissionConfig)
    history: HistoryConfig = Field(default_factory=HistoryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    tools: ToolConfig = Field(default_factory=ToolConfig)
    agents: AgentConfig = Field(default_factory=AgentConfig)
    swarm: SwarmConfig = Field(default_factory=SwarmConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
