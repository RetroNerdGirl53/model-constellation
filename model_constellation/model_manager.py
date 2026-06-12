"""Model management module for model-constellation.

This module provides model management functionality including:
- Listing installed models
- Showing model details
- Selecting default model
- Configuring model parameters
- Pulling models from Ollama registry
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from model_constellation.constants import (
    DEFAULT_KEEP_ALIVE,
    DEFAULT_MODEL,
    DEFAULT_NUM_CTX,
    DEFAULT_NUM_GPU,
    DEFAULT_NUM_THREAD,
    DEFAULT_REPEAT_PENALTY,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
)
from model_constellation.ollama_client import (
    ModelInfo,
    ModelParameters,
    OllamaClient,
    OllamaConnectionError,
    OllamaModelError,
)

logger = logging.getLogger(__name__)


@dataclass
class ParameterPreset:
    """Predefined parameter preset for different use cases."""

    name: str
    description: str
    parameters: ModelParameters

    @classmethod
    def create_creative(cls) -> "ParameterPreset":
        """Create a creative preset for more diverse outputs."""
        return cls(
            name="creative",
            description="More creative and diverse outputs",
            parameters=ModelParameters(
                temperature=1.2,
                top_p=0.95,
                top_k=50,
            ),
        )

    @classmethod
    def create_precise(cls) -> "ParameterPreset":
        """Create a precise preset for accurate, focused outputs."""
        return cls(
            name="precise",
            description="More precise and accurate outputs",
            parameters=ModelParameters(
                temperature=0.3,
                top_p=0.8,
                top_k=20,
            ),
        )

    @classmethod
    def create_balanced(cls) -> "ParameterPreset":
        """Create a balanced preset for general use."""
        return cls(
            name="balanced",
            description="Balanced parameters for general use",
            parameters=ModelParameters(
                temperature=0.7,
                top_p=0.9,
                top_k=40,
            ),
        )

    @classmethod
    def create_code(cls) -> "ParameterPreset":
        """Create a code-focused preset for programming tasks."""
        return cls(
            name="code",
            description="Optimized for code generation",
            parameters=ModelParameters(
                temperature=0.2,
                top_p=0.85,
                top_k=60,
                num_ctx=8192,
            ),
        )


DEFAULT_PRESETS: Dict[str, ParameterPreset] = {
    "creative": ParameterPreset.create_creative(),
    "precise": ParameterPreset.create_precise(),
    "balanced": ParameterPreset.create_balanced(),
    "code": ParameterPreset.create_code(),
}


@dataclass
class ModelDetails:
    """Detailed information about an Ollama model."""

    name: str
    model: str
    size: Optional[int] = None
    digest: Optional[str] = None
    modified_at: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    @property
    def size_formatted(self) -> str:
        """Return human-readable size."""
        if self.size is None:
            return "Unknown"
        size = self.size
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"


@dataclass
class ModelConfig:
    """Configuration for a specific model."""

    name: str
    parameters: ModelParameters = field(default_factory=ModelParameters)
    keep_alive: str = DEFAULT_KEEP_ALIVE


class ModelManager:
    """Manager for Ollama models.

    Provides functionality to manage models including listing, pulling,
    configuring parameters, and managing the default model.

    Attributes:
        client: The Ollama client instance.
        default_model: The current default model name.

    Example:
        >>> manager = ModelManager()
        >>> models = manager.list_models()
        >>> manager.pull_model("llama2:7b")
        >>> manager.set_default_model("llama2:7b")
    """

    def __init__(
        self,
        client: Optional[OllamaClient] = None,
        default_model: str = DEFAULT_MODEL,
    ):
        """Initialize the model manager.

        Args:
            client: OllamaClient instance (creates new one if not provided).
            default_model: Default model name.
        """
        self.client = client or OllamaClient()
        self.default_model = default_model
        self._presets: Dict[str, ParameterPreset] = DEFAULT_PRESETS.copy()

        logger.info(f"Initialized ModelManager with default_model={default_model}")

    def list_models(self, detailed: bool = False) -> List[ModelInfo]:
        """List all installed models.

        Args:
            detailed: Include detailed information.

        Returns:
            List of ModelInfo objects.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
        """
        models = self.client.list_models()
        if detailed:
            logger.info(f"Listed {len(models)} models (detailed)")
        else:
            logger.info(f"Listed {len(models)} models")
        return models

    def get_model_details(self, model: Optional[str] = None) -> ModelDetails:
        """Get detailed information about a model.

        Args:
            model: Model name (uses default if not provided).

        Returns:
            ModelDetails object.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
            OllamaModelError: If the model is not found.
        """
        model = model or self.default_model
        try:
            info = self.client.get_model_info(model)
            return ModelDetails(
                name=info.get("name", model),
                model=info.get("model", model),
                size=info.get("size"),
                digest=info.get("digest"),
                modified_at=info.get("modified_at"),
                details=info,
            )
        except OllamaConnectionError:
            raise
        except OllamaModelError:
            raise

    def pull_model(
        self,
        model: str,
        stream: bool = True,
        force: bool = False,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> bool:
        """Pull a model from Ollama registry.

        Args:
            model: Model name to pull.
            stream: Whether to stream progress.
            force: Force re-pull if model exists.
            progress_callback: Optional callback for progress updates.

        Returns:
            True if successful.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
        """
        logger.info(f"Pulling model: {model}")

        if stream and progress_callback:
            for progress in self.client.pull_model(model, stream=True, force=force):
                progress_callback(progress)
                if progress.get("status") == "success":
                    logger.info(f"Successfully pulled model: {model}")
                    return True
            return True
        else:
            self.client.pull_model(model, stream=False, force=force)
            logger.info(f"Successfully pulled model: {model}")
            return True

    async def async_pull_model(
        self,
        model: str,
        stream: bool = True,
        force: bool = False,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> bool:
        """Pull a model from Ollama registry asynchronously.

        Args:
            model: Model name to pull.
            stream: Whether to stream progress.
            force: Force re-pull if model exists.
            progress_callback: Optional callback for progress updates.

        Returns:
            True if successful.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
        """
        logger.info(f"Pulling model (async): {model}")

        if stream and progress_callback:
            async for progress in await self.client.async_pull_model(
                model, stream=True, force=force
            ):
                progress_callback(progress)
                if progress.get("status") == "success":
                    logger.info(f"Successfully pulled model (async): {model}")
                    return True
            return True
        else:
            await self.client.async_pull_model(model, stream=False, force=force)
            logger.info(f"Successfully pulled model (async): {model}")
            return True

    def delete_model(self, model: str) -> bool:
        """Delete a model from local storage.

        Args:
            model: Model name to delete.

        Returns:
            True if successful.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
        """
        logger.info(f"Deleting model: {model}")
        self.client.delete_model(model)
        logger.info(f"Successfully deleted model: {model}")
        return True

    async def async_delete_model(self, model: str) -> bool:
        """Delete a model from local storage asynchronously.

        Args:
            model: Model name to delete.

        Returns:
            True if successful.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
        """
        logger.info(f"Deleting model (async): {model}")
        await self.client.async_delete_model(model)
        logger.info(f"Successfully deleted model (async): {model}")
        return True

    def set_default_model(self, model: str) -> None:
        """Set the default model.

        Args:
            model: Model name to set as default.

        Raises:
            OllamaModelError: If the model is not found.
        """
        models = self.list_models()
        model_names = [m.name for m in models]
        if model not in model_names:
            logger.warning(
                f"Model '{model}' not found in installed models. "
                "Setting as default anyway (may need to pull first)."
            )
        self.default_model = model
        logger.info(f"Set default model to: {model}")

    def get_default_model(self) -> str:
        """Get the current default model name.

        Returns:
            Default model name.
        """
        return self.default_model

    def get_parameters(
        self,
        preset: Optional[str] = None,
        model: Optional[str] = None,
    ) -> ModelParameters:
        """Get model parameters.

        Args:
            preset: Name of preset to use (creative, precise, balanced, code).
            model: Model name for getting model-specific defaults.

        Returns:
            ModelParameters object.
        """
        if preset and preset in self._presets:
            return self._presets[preset].parameters

        if model:
            try:
                details = self.get_model_details(model)
                if details.details and "parameters" in details.details:
                    params = details.details["parameters"]
                    return ModelParameters(
                        temperature=params.get("temperature", DEFAULT_TEMPERATURE),
                        top_p=params.get("top_p", DEFAULT_TOP_P),
                        top_k=params.get("top_k", DEFAULT_TOP_K),
                        repeat_penalty=params.get("repeat_penalty", DEFAULT_REPEAT_PENALTY),
                        num_ctx=params.get("num_ctx", DEFAULT_NUM_CTX),
                    )
            except OllamaModelError:
                pass

        return ModelParameters()

    def configure_parameters(
        self,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        repeat_penalty: Optional[float] = None,
        seed: Optional[int] = None,
        num_ctx: Optional[int] = None,
        num_gpu: Optional[int] = None,
        num_thread: Optional[int] = None,
    ) -> ModelParameters:
        """Configure model parameters.

        All parameters are optional. Only provided values will be updated.

        Args:
            temperature: Sampling temperature (0.0-2.0).
            top_p: Nucleus sampling threshold (0.0-1.0).
            top_k: Top-k sampling (1-100).
            repeat_penalty: Repetition penalty (0.0-2.0).
            seed: Random seed.
            num_ctx: Context window size.
            num_gpu: GPU layers to use.
            num_thread: CPU threads to use.

        Returns:
            ModelParameters object with the configured values.
        """
        params = ModelParameters()

        if temperature is not None:
            params.temperature = max(0.0, min(2.0, temperature))
        if top_p is not None:
            params.top_p = max(0.0, min(1.0, top_p))
        if top_k is not None:
            params.top_k = max(1, min(100, top_k))
        if repeat_penalty is not None:
            params.repeat_penalty = max(0.0, min(2.0, repeat_penalty))
        if seed is not None:
            params.seed = seed
        if num_ctx is not None:
            params.num_ctx = max(128, min(128000, num_ctx))
        if num_gpu is not None:
            params.num_gpu = num_gpu
        if num_thread is not None:
            params.num_thread = max(1, min(32, num_thread))

        logger.info(f"Configured parameters: {params.to_dict()}")
        return params

    def list_presets(self) -> Dict[str, ParameterPreset]:
        """List all available parameter presets.

        Returns:
            Dictionary of preset name to ParameterPreset.
        """
        return self._presets.copy()

    def add_preset(self, preset: ParameterPreset) -> None:
        """Add a custom parameter preset.

        Args:
            preset: ParameterPreset to add.
        """
        self._presets[preset.name] = preset
        logger.info(f"Added custom preset: {preset.name}")

    def remove_preset(self, name: str) -> bool:
        """Remove a custom parameter preset.

        Args:
            name: Preset name to remove.

        Returns:
            True if removed, False if preset doesn't exist or is default.
        """
        if name in DEFAULT_PRESETS:
            logger.warning(f"Cannot remove default preset: {name}")
            return False

        if name in self._presets:
            del self._presets[name]
            logger.info(f"Removed preset: {name}")
            return True

        return False

    def validate_model(self, model: str) -> bool:
        """Check if a model is available locally.

        Args:
            model: Model name to validate.

        Returns:
            True if model is available, False otherwise.
        """
        try:
            models = self.list_models()
            model_names = [m.name for m in models]
            return model in model_names
        except OllamaConnectionError:
            return False

    def get_model_config(self, model: Optional[str] = None) -> ModelConfig:
        """Get configuration for a specific model.

        Args:
            model: Model name (uses default if not provided).

        Returns:
            ModelConfig object.
        """
        model = model or self.default_model
        parameters = self.get_parameters(model=model)
        return ModelConfig(name=model, parameters=parameters)

    def check_connection(self) -> bool:
        """Check if connection to Ollama server is available.

        Returns:
            True if connected, False otherwise.
        """
        return self.client.check_connection()

    async def async_check_connection(self) -> bool:
        """Check if connection to Ollama server is available (async).

        Returns:
            True if connected, False otherwise.
        """
        return await self.client.async_check_connection()
