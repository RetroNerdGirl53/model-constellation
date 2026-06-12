"""Constants used throughout the model-constellation framework."""

import os
from pathlib import Path

CONFIG_VERSION = "1.0"

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama2"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.9
DEFAULT_TOP_K = 40
DEFAULT_REPEAT_PENALTY = 1.1
DEFAULT_NUM_CTX = 4096
DEFAULT_NUM_GPU = -1
DEFAULT_NUM_THREAD = -1
DEFAULT_TIMEOUT = 120000
DEFAULT_KEEP_ALIVE = "5m"

DEFAULT_PERMISSION_MODE = "first-time"
DEFAULT_CACHE_TTL = 3600

DEFAULT_MAX_MESSAGES = 10000
DEFAULT_MAX_TOKENS = 128000
DEFAULT_RETENTION_DAYS = 30

DEFAULT_MAX_AGENTS = 10
DEFAULT_MAX_SWARM_SIZE = 20
DEFAULT_SWARM_MODE = "parallel"
DEFAULT_MAX_CONCURRENT = 5

DEFAULT_SESSION_AUTO_SAVE_INTERVAL = 300
DEFAULT_TOOL_TIMEOUT = 30000

DEFAULT_LOG_LEVEL = "info"
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_LOG_MAX_SIZE = "10MB"
DEFAULT_LOG_BACKUP_COUNT = 5

MODEL_CONSTELLATION_DIR = Path.home() / ".model-constellation"
TARS_DIR = MODEL_CONSTELLATION_DIR  # Backwards compatibility alias
DEFAULT_CONFIG_PATH = MODEL_CONSTELLATION_DIR / "config.yaml"
DEFAULT_HISTORY_DIR = MODEL_CONSTELLATION_DIR / "history"
DEFAULT_LOGS_DIR = MODEL_CONSTELLATION_DIR / "logs"
DEFAULT_TOOLS_DIR = MODEL_CONSTELLATION_DIR / "tools"

PERMISSION_MODES = ["first-time", "every-time", "allow-all", "deny-all"]
AGENT_MODES = ["isolated", "swarm", "hierarchical"]
AGENT_TYPES = ["primary", "specialized", "worker", "research", "code"]
SWARM_MODES = ["parallel", "sequential", "pipeline", "adaptive"]
LOG_LEVELS = ["debug", "info", "warning", "error", "critical"]

BUILTIN_TOOLS = [
    "bash",
    "read",
    "write",
    "glob",
    "grep",
    "webfetch",
    "websearch",
    "codesearch",
]

DANGEROUS_COMMANDS = ["rm", "del", "format", "mkfs", "dd"]
PRIVILEGED_COMMANDS = ["sudo", "su", "doas"]

ENV_VAR_PREFIX = "MODEL_CONSTELLATION_"
ENV_BASE_URL = f"{ENV_VAR_PREFIX}BASE_URL"
ENV_MODEL = f"{ENV_VAR_PREFIX}MODEL"
ENV_CONFIG = f"{ENV_VAR_PREFIX}CONFIG"
ENV_PERMISSION_MODE = f"{ENV_VAR_PREFIX}PERMISSION_MODE"
ENV_LOG_LEVEL = f"{ENV_VAR_PREFIX}LOG_LEVEL"
ENV_NO_COLOR = f"{ENV_VAR_PREFIX}NO_COLOR"
