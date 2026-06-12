"""Configuration management for model-constellation."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

from model_constellation import constants
from model_constellation.models import ModelConstellationConfig


class ConfigManager:
    """Manages model-constellation configuration loading, saving, and validation."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self._get_config_path()
        self._config: Optional[ModelConstellationConfig] = None

    def _get_config_path(self) -> Path:
        env_config = os.environ.get(constants.ENV_CONFIG)
        if env_config:
            return Path(env_config)
        project_config = Path.cwd() / ".model-constellation.yaml"
        if project_config.exists():
            return project_config
        return constants.DEFAULT_CONFIG_PATH

    def load(self) -> ModelConstellationConfig:
        """Load configuration from file with environment variable overrides."""
        if self._config:
            return self._config

        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = yaml.safe_load(f) or {}
            except yaml.constructor.ConstructorError as e:
                print(f"Warning: Config file is corrupted: {e}")
                print("Creating fresh configuration...")
                backup_path = self.config_path.with_suffix(".yaml.broken")
                self.config_path.rename(backup_path)
                print(f"Broken config backed up to: {backup_path}")
                data = {}
        else:
            data = {}

        self._apply_env_overrides(data)
        self._config = ModelConstellationConfig(**data)
        return self._config

    def _apply_env_overrides(self, data: dict) -> None:
        """Apply environment variable overrides to configuration."""
        if constants.ENV_BASE_URL in os.environ:
            data.setdefault("ollama", {})
            data["ollama"]["base_url"] = os.environ[constants.ENV_BASE_URL]

        if constants.ENV_MODEL in os.environ:
            data.setdefault("ollama", {})
            data["ollama"]["default_model"] = os.environ[constants.ENV_MODEL]

        if constants.ENV_PERMISSION_MODE in os.environ:
            data.setdefault("permission", {})
            data["permission"]["mode"] = os.environ[constants.ENV_PERMISSION_MODE]

        if constants.ENV_LOG_LEVEL in os.environ:
            data.setdefault("logging", {})
            data["logging"]["level"] = os.environ[constants.ENV_LOG_LEVEL]

    def save(self, config: Optional[ModelConstellationConfig] = None) -> None:
        """Save configuration to file."""
        config = config or self._config
        if not config:
            raise ValueError("No configuration to save")

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump(config.model_dump(mode="json"), f, default_flow_style=False)

    def generate_default(self) -> ModelConstellationConfig:
        """Generate and save default configuration."""
        config = ModelConstellationConfig()
        self._config = config
        self.save(config)
        return config

    def validate(self, config: Optional[ModelConstellationConfig] = None) -> bool:
        """Validate configuration."""
        try:
            config = config or self._config or self.load()
            return True
        except Exception:
            return False

    @property
    def config(self) -> ModelConstellationConfig:
        """Get current configuration."""
        if not self._config:
            self._config = self.load()
        return self._config


def get_config_manager(config_path: Optional[Path] = None) -> ConfigManager:
    """Get a configuration manager instance."""
    return ConfigManager(config_path)


def load_config(config_path: Optional[Path] = None) -> ModelConstellationConfig:
    """Load configuration from file."""
    manager = ConfigManager(config_path)
    return manager.load()


def save_config(config: ModelConstellationConfig, config_path: Optional[Path] = None) -> None:
    """Save configuration to file."""
    manager = ConfigManager(config_path)
    manager.save(config)


def generate_default_config(config_path: Optional[Path] = None) -> ModelConstellationConfig:
    """Generate default configuration."""
    manager = ConfigManager(config_path)
    return manager.generate_default()
