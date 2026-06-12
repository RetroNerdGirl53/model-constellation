"""Ollama client wrapper for model-constellation framework.

This module provides a clean API wrapper around the Ollama client with:
- Sync and async operations
- Streaming responses
- Custom model parameters
- Proper error handling and logging
"""

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Union

import ollama
from ollama import AsyncClient, Client

from model_constellation.constants import (
    DEFAULT_KEEP_ALIVE,
    DEFAULT_MODEL,
    DEFAULT_NUM_CTX,
    DEFAULT_NUM_GPU,
    DEFAULT_NUM_THREAD,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_REPEAT_PENALTY,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    DEFAULT_TOP_K,
    DEFAULT_TOP_P,
)

logger = logging.getLogger(__name__)


@dataclass
class ModelParameters:
    """Model parameters for Ollama generation requests."""

    temperature: float = DEFAULT_TEMPERATURE
    top_p: float = DEFAULT_TOP_P
    top_k: int = DEFAULT_TOP_K
    repeat_penalty: float = DEFAULT_REPEAT_PENALTY
    seed: Optional[int] = None
    num_ctx: int = DEFAULT_NUM_CTX
    num_gpu: int = DEFAULT_NUM_GPU
    num_thread: int = DEFAULT_NUM_THREAD
    stop: Optional[List[str]] = None
    rope_frequency_base: Optional[float] = None
    rope_frequency_scale: Optional[float] = None
    mirostat: Optional[int] = None
    mirostat_eta: Optional[float] = None
    mirostat_tau: Optional[float] = None
    format: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert parameters to dictionary for Ollama API."""
        result = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repeat_penalty": self.repeat_penalty,
            "num_ctx": self.num_ctx,
            "num_gpu": self.num_gpu,
            "num_thread": self.num_thread,
        }
        if self.seed is not None:
            result["seed"] = self.seed
        if self.stop is not None:
            result["stop"] = self.stop
        if self.rope_frequency_base is not None:
            result["rope_frequency_base"] = self.rope_frequency_base
        if self.rope_frequency_scale is not None:
            result["rope_frequency_scale"] = self.rope_frequency_scale
        if self.mirostat is not None:
            result["mirostat"] = self.mirostat
        if self.mirostat_eta is not None:
            result["mirostat_eta"] = self.mirostat_eta
        if self.mirostat_tau is not None:
            result["mirostat_tau"] = self.mirostat_tau
        if self.format is not None:
            result["format"] = self.format
        return {k: v for k, v in result.items() if v != -1 and v is not None}


@dataclass
class ChatMessage:
    """Chat message structure."""

    role: str
    content: str
    images: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Ollama API."""
        result: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.images is not None:
            result["images"] = self.images
        return result


def _normalize_tool_calls(raw: Any) -> Optional[List[Dict[str, Any]]]:
    """Normalize Ollama tool_calls into a list of plain dicts.

    Ollama may return tool calls as pydantic objects (with ``.function.name`` and
    ``.function.arguments``) or as dicts. This flattens both into the canonical
    shape ``{"function": {"name": str, "arguments": dict}}`` so the rest of the
    framework never has to branch on the underlying type.

    Args:
        raw: The ``tool_calls`` value from an Ollama message (objects or dicts).

    Returns:
        A list of normalized tool-call dicts, or None if there are none.
    """
    if not raw:
        return None

    normalized: List[Dict[str, Any]] = []
    for call in raw:
        if isinstance(call, dict):
            function = call.get("function", {}) or {}
            name = function.get("name", "")
            arguments = function.get("arguments", {})
        else:
            function = getattr(call, "function", None)
            name = getattr(function, "name", "") if function is not None else ""
            arguments = getattr(function, "arguments", {}) if function is not None else {}

        if not isinstance(arguments, dict):
            arguments = {}
        if name:
            normalized.append({"function": {"name": name, "arguments": arguments}})

    return normalized or None


@dataclass
class ChatResponse:
    """Chat completion response."""

    model: str
    message: ChatMessage
    done: bool
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None
    context: Optional[List[int]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def from_ollama_response(cls, response: Any) -> "ChatResponse":
        """Create ChatResponse from Ollama API response."""
        # Handle pydantic model from ollama library
        if hasattr(response, "message"):
            # It's a pydantic model
            msg = response.message
            tool_calls = _normalize_tool_calls(getattr(msg, "tool_calls", None))
            return cls(
                model=response.model if hasattr(response, "model") else "",
                message=ChatMessage(
                    role=msg.role if hasattr(msg, "role") else "assistant",
                    content=msg.content if hasattr(msg, "content") else "",
                ),
                done=response.done if hasattr(response, "done") else True,
                total_duration=response.total_duration
                if hasattr(response, "total_duration")
                else None,
                load_duration=response.load_duration
                if hasattr(response, "load_duration")
                else None,
                prompt_eval_count=response.prompt_eval_count
                if hasattr(response, "prompt_eval_count")
                else None,
                eval_count=response.eval_count if hasattr(response, "eval_count") else None,
                context=response.context if hasattr(response, "context") else None,
                tool_calls=tool_calls,
            )
        # Handle dict response
        message_data = response.get("message", {}) if isinstance(response, dict) else {}
        return cls(
            model=response.get("model", "") if isinstance(response, dict) else "",
            message=ChatMessage(
                role=message_data.get("role", "assistant"),
                content=message_data.get("content", ""),
            ),
            done=response.get("done", True) if isinstance(response, dict) else True,
            total_duration=response.get("total_duration") if isinstance(response, dict) else None,
            load_duration=response.get("load_duration") if isinstance(response, dict) else None,
            prompt_eval_count=response.get("prompt_eval_count")
            if isinstance(response, dict)
            else None,
            eval_count=response.get("eval_count") if isinstance(response, dict) else None,
            context=response.get("context") if isinstance(response, dict) else None,
            tool_calls=_normalize_tool_calls(message_data.get("tool_calls")),
        )


@dataclass
class GenerateResponse:
    """Generate completion response."""

    model: str
    response: str
    done: bool
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None
    context: Optional[List[int]] = None

    @classmethod
    def from_ollama_response(cls, response: Any) -> "GenerateResponse":
        """Create GenerateResponse from Ollama API response."""
        return cls(
            model=response.get("model", "") if isinstance(response, dict) else "",
            response=response.get("response", "") if isinstance(response, dict) else "",
            done=response.get("done", True) if isinstance(response, dict) else True,
            total_duration=response.get("total_duration") if isinstance(response, dict) else None,
            load_duration=response.get("load_duration") if isinstance(response, dict) else None,
            prompt_eval_count=response.get("prompt_eval_count")
            if isinstance(response, dict)
            else None,
            eval_count=response.get("eval_count") if isinstance(response, dict) else None,
            context=response.get("context") if isinstance(response, dict) else None,
        )


@dataclass
class ModelInfo:
    """Information about an Ollama model."""

    name: str
    model: str
    size: Optional[int] = None
    digest: Optional[str] = None
    modified_at: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    @classmethod
    def from_ollama_model(cls, model_data) -> "ModelInfo":
        """Create ModelInfo from Ollama API model data.

        Handles both dict and pydantic model responses from Ollama.
        """
        # Handle pydantic model or dict
        if hasattr(model_data, "model"):
            # It's a pydantic model from ollama library
            name = getattr(model_data, "name", None) or model_data.model
            model = model_data.model
            size = model_data.size
            digest = model_data.digest
            modified_at = str(model_data.modified_at) if model_data.modified_at else None
            details = (
                model_data.details.model_dump()
                if model_data.details
                else None
                if hasattr(model_data, "details")
                else None
            )
        else:
            # It's a dict
            name = model_data.get("name") or model_data.get("model", "")
            model = model_data.get("model", "")
            size = model_data.get("size")
            digest = model_data.get("digest")
            modified_at = model_data.get("modified_at")
            details = model_data.get("details")

        return cls(
            name=name,
            model=model,
            size=size,
            digest=digest,
            modified_at=modified_at,
            details=details,
        )


class OllamaConnectionError(Exception):
    """Raised when unable to connect to Ollama server."""

    pass


class OllamaModelError(Exception):
    """Raised when model-related operations fail."""

    pass


class OllamaClient:
    """Ollama client wrapper with sync and async operations.

    Provides a clean API for interacting with local Ollama instances,
    supporting chat completions, generation, model management, and embeddings.

    Attributes:
        base_url: The base URL of the Ollama server.
        default_model: The default model to use for requests.
        timeout: Request timeout in milliseconds.

    Example:
        >>> client = OllamaClient()
        >>> response = client.chat("llama2", [{"role": "user", "content": "Hello"}])
        >>> print(response.message.content)
    """

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        default_model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
        keep_alive: str = DEFAULT_KEEP_ALIVE,
    ):
        """Initialize the Ollama client.

        Args:
            base_url: The base URL of the Ollama server.
            default_model: The default model to use for requests.
            timeout: Request timeout in milliseconds.
            keep_alive: Keep alive duration for model loading.
        """
        self.base_url = base_url
        self.default_model = default_model
        self.timeout = timeout
        self.keep_alive = keep_alive

        self._client = Client(host=base_url)
        # The async client (httpx under the hood) binds to the event loop it first
        # runs on. We create it lazily and rebind when the running loop changes, so
        # one OllamaClient works across multiple loops (e.g. Starlette's per-request
        # test loop, or repeated asyncio.run calls).
        self._async_client: Optional[AsyncClient] = None
        self._async_loop: Any = None

        logger.info(
            f"Initialized OllamaClient with base_url={base_url}, default_model={default_model}"
        )

    def _aclient(self) -> AsyncClient:
        """Return an async client bound to the current running event loop."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._async_client is None or self._async_loop is not loop:
            self._async_client = AsyncClient(host=self.base_url)
            self._async_loop = loop
        return self._async_client

    def _ensure_model(self, model: Optional[str]) -> str:
        """Ensure a model name is provided."""
        return model or self.default_model

    def list_models(self) -> List[ModelInfo]:
        """List all available models from the Ollama server.

        Returns:
            List of ModelInfo objects.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
        """
        try:
            response = self._client.list()
            models = []
            for model in response.get("models", []):
                models.append(ModelInfo.from_ollama_model(model))
            logger.info(f"Listed {len(models)} models")
            return models
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            raise OllamaConnectionError(f"Failed to connect to Ollama: {e}") from e

    async def async_list_models(self) -> List[ModelInfo]:
        """List all available models asynchronously.

        Returns:
            List of ModelInfo objects.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
        """
        try:
            response = await self._aclient().list()
            models = []
            for model in response.get("models", []):
                models.append(ModelInfo.from_ollama_model(model))
            logger.info(f"Listed {len(models)} models (async)")
            return models
        except Exception as e:
            logger.error(f"Failed to list models (async): {e}")
            raise OllamaConnectionError(f"Failed to connect to Ollama: {e}") from e

    def get_model_info(self, model: Optional[str] = None) -> Dict[str, Any]:
        """Get detailed information about a specific model.

        Args:
            model: Model name (uses default if not provided).

        Returns:
            Dictionary containing model information.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
            OllamaModelError: If the model is not found.
        """
        model = self._ensure_model(model)
        try:
            response = self._client.show(model)
            logger.info(f"Retrieved info for model: {model}")
            return dict(response) if hasattr(response, "__iter__") else {"raw": response}
        except Exception as e:
            logger.error(f"Failed to get model info for {model}: {e}")
            if "not found" in str(e).lower():
                raise OllamaModelError(f"Model '{model}' not found") from e
            raise OllamaConnectionError(f"Failed to connect to Ollama: {e}") from e

    def chat(
        self,
        model: Optional[str],
        messages: List[Union[Dict[str, str], ChatMessage]],
        stream: bool = False,
        parameters: Optional[ModelParameters] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> Union[ChatResponse, Generator[ChatResponse, None, None]]:
        """Send a chat completion request.

        Args:
            model: Model name (uses default if not provided).
            messages: List of chat messages.
            stream: Whether to stream the response.
            parameters: Model parameters.
            tools: Optional list of tool schemas (Ollama native function-calling
                format). When provided, tool-capable models may return
                ``response.tool_calls``.
            **kwargs: Additional parameters for Ollama API.

        Returns:
            ChatResponse object or generator of ChatResponse objects if streaming.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
            OllamaModelError: If the model is not found.
        """
        model = self._ensure_model(model)
        params = (parameters or ModelParameters()).to_dict()
        params.update(kwargs)

        formatted_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                formatted_messages.append(msg)
            elif isinstance(msg, ChatMessage):
                formatted_messages.append(msg.to_dict())

        try:
            if stream:
                return self._stream_chat(model, formatted_messages, params, tools)
            else:
                response = self._client.chat(
                    model=model,
                    messages=formatted_messages,
                    stream=False,
                    options=params,
                    tools=tools,
                )
                logger.info(f"Chat request completed for model: {model}")
                return ChatResponse.from_ollama_response(response)
        except Exception as e:
            logger.error(f"Chat request failed: {e}")
            if "not found" in str(e).lower():
                raise OllamaModelError(f"Model '{model}' not found") from e
            raise OllamaConnectionError(f"Failed to connect to Ollama: {e}") from e

    def _stream_chat(
        self,
        model: str,
        messages: List[Dict],
        params: Dict[str, Any],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Generator[ChatResponse, None, None]:
        """Stream chat responses."""
        try:
            for response in self._client.chat(
                model=model, messages=messages, stream=True, options=params, tools=tools
            ):
                yield ChatResponse.from_ollama_response(response)
        except Exception as e:
            logger.error(f"Streaming chat failed: {e}")
            raise OllamaConnectionError(f"Streaming failed: {e}") from e

    async def async_chat(
        self,
        model: Optional[str],
        messages: List[Union[Dict[str, str], ChatMessage]],
        stream: bool = False,
        parameters: Optional[ModelParameters] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> Union[ChatResponse, AsyncGenerator[ChatResponse, None]]:
        """Send a chat completion request asynchronously.

        Args:
            model: Model name (uses default if not provided).
            messages: List of chat messages.
            stream: Whether to stream the response.
            parameters: Model parameters.
            tools: Optional list of tool schemas (Ollama native function-calling
                format). When provided, tool-capable models may return
                ``response.tool_calls``.
            **kwargs: Additional parameters for Ollama API.

        Returns:
            ChatResponse object or async generator of ChatResponse objects.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
            OllamaModelError: If the model is not found.
        """
        model = self._ensure_model(model)
        params = (parameters or ModelParameters()).to_dict()
        params.update(kwargs)

        formatted_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                formatted_messages.append(msg)
            elif isinstance(msg, ChatMessage):
                formatted_messages.append(msg.to_dict())

        try:
            if stream:
                return self._async_stream_chat(model, formatted_messages, params, tools)
            else:
                response = await self._aclient().chat(
                    model=model,
                    messages=formatted_messages,
                    stream=False,
                    options=params,
                    tools=tools,
                )
                logger.info(f"Async chat request completed for model: {model}")
                return ChatResponse.from_ollama_response(response)
        except Exception as e:
            logger.error(f"Async chat request failed: {e}")
            if "not found" in str(e).lower():
                raise OllamaModelError(f"Model '{model}' not found") from e
            raise OllamaConnectionError(f"Failed to connect to Ollama: {e}") from e

    async def _async_stream_chat(
        self,
        model: str,
        messages: List[Dict],
        params: Dict[str, Any],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[ChatResponse, None]:
        """Stream chat responses asynchronously."""
        try:
            async for response in self._aclient().chat(  # type: ignore[union-attr]
                model=model, messages=messages, stream=True, options=params, tools=tools
            ):
                yield ChatResponse.from_ollama_response(response)
        except Exception as e:
            logger.error(f"Async streaming chat failed: {e}")
            raise OllamaConnectionError(f"Streaming failed: {e}") from e

    def generate(
        self,
        model: Optional[str],
        prompt: str,
        stream: bool = False,
        parameters: Optional[ModelParameters] = None,
        **kwargs,
    ) -> Union[GenerateResponse, Generator[GenerateResponse, None, None]]:
        """Send a generation request.

        Args:
            model: Model name (uses default if not provided).
            prompt: Prompt text.
            stream: Whether to stream the response.
            parameters: Model parameters.
            **kwargs: Additional parameters for Ollama API.

        Returns:
            GenerateResponse object or generator of GenerateResponse objects.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
            OllamaModelError: If the model is not found.
        """
        model = self._ensure_model(model)
        params = (parameters or ModelParameters()).to_dict()
        params.update(kwargs)

        try:
            if stream:
                return self._stream_generate(model, prompt, params)
            else:
                response = self._client.generate(
                    model=model,
                    prompt=prompt,
                    stream=False,
                    options=params,
                )
                logger.info(f"Generate request completed for model: {model}")
                return GenerateResponse.from_ollama_response(response)
        except Exception as e:
            logger.error(f"Generate request failed: {e}")
            if "not found" in str(e).lower():
                raise OllamaModelError(f"Model '{model}' not found") from e
            raise OllamaConnectionError(f"Failed to connect to Ollama: {e}") from e

    def _stream_generate(
        self, model: str, prompt: str, params: Dict[str, Any]
    ) -> Generator[GenerateResponse, None, None]:
        """Stream generation responses."""
        try:
            for response in self._client.generate(
                model=model, prompt=prompt, stream=True, options=params
            ):
                yield GenerateResponse.from_ollama_response(response)
        except Exception as e:
            logger.error(f"Streaming generate failed: {e}")
            raise OllamaConnectionError(f"Streaming failed: {e}") from e

    async def async_generate(
        self,
        model: Optional[str],
        prompt: str,
        stream: bool = False,
        parameters: Optional[ModelParameters] = None,
        **kwargs,
    ) -> Union[GenerateResponse, AsyncGenerator[GenerateResponse, None]]:
        """Send a generation request asynchronously.

        Args:
            model: Model name (uses default if not provided).
            prompt: Prompt text.
            stream: Whether to stream the response.
            parameters: Model parameters.
            **kwargs: Additional parameters for Ollama API.

        Returns:
            GenerateResponse object or async generator.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
            OllamaModelError: If the model is not found.
        """
        model = self._ensure_model(model)
        params = (parameters or ModelParameters()).to_dict()
        params.update(kwargs)

        try:
            if stream:
                return self._async_stream_generate(model, prompt, params)
            else:
                response = await self._aclient().generate(
                    model=model,
                    prompt=prompt,
                    stream=False,
                    options=params,
                )
                logger.info(f"Async generate request completed for model: {model}")
                return GenerateResponse.from_ollama_response(response)
        except Exception as e:
            logger.error(f"Async generate request failed: {e}")
            if "not found" in str(e).lower():
                raise OllamaModelError(f"Model '{model}' not found") from e
            raise OllamaConnectionError(f"Failed to connect to Ollama: {e}") from e

    async def _async_stream_generate(
        self, model: str, prompt: str, params: Dict[str, Any]
    ) -> AsyncGenerator[GenerateResponse, None]:
        """Stream generation responses asynchronously."""
        try:
            async for response in self._aclient().generate(  # type: ignore[union-attr]
                model=model, prompt=prompt, stream=True, options=params
            ):
                yield GenerateResponse.from_ollama_response(response)
        except Exception as e:
            logger.error(f"Async streaming generate failed: {e}")
            raise OllamaConnectionError(f"Streaming failed: {e}") from e

    def pull_model(
        self,
        model: str,
        stream: bool = False,
        force: bool = False,
    ) -> Any:
        """Pull a model from Ollama registry.

        Args:
            model: Model name to pull.
            stream: Whether to stream progress.
            force: Force re-pull even if model exists.

        Returns:
            Response dictionary or generator of progress updates.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
        """
        try:
            if stream:
                return self._stream_pull(model, force)
            else:
                response = self._client.pull(model, stream=False, insecure=force)
                logger.info(f"Pulled model: {model}")
                return response
        except Exception as e:
            logger.error(f"Failed to pull model {model}: {e}")
            raise OllamaConnectionError(f"Failed to pull model: {e}") from e

    def _stream_pull(self, model: str, force: bool) -> Generator[Any, None, None]:
        """Stream model pull progress."""
        try:
            for progress in self._client.pull(model, stream=True, insecure=force):
                yield progress
        except Exception as e:
            logger.error(f"Streaming pull failed for {model}: {e}")
            raise OllamaConnectionError(f"Streaming pull failed: {e}") from e

    async def async_pull_model(
        self,
        model: str,
        stream: bool = False,
        force: bool = False,
    ) -> Any:
        """Pull a model from Ollama registry asynchronously.

        Args:
            model: Model name to pull.
            stream: Whether to stream progress.
            force: Force re-pull even if model exists.

        Returns:
            Response dictionary or async generator of progress updates.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
        """
        try:
            if stream:
                return self._async_stream_pull(model, force)  # type: ignore[return-value]
            else:
                response = await self._aclient().pull(model, stream=False, insecure=force)
                logger.info(f"Pulled model (async): {model}")
                return response
        except Exception as e:
            logger.error(f"Failed to pull model (async) {model}: {e}")
            raise OllamaConnectionError(f"Failed to pull model: {e}") from e

    async def _async_stream_pull(self, model: str, force: bool) -> AsyncGenerator[Any, None]:
        """Stream model pull progress asynchronously."""
        try:
            async for progress in self._aclient().pull(model, stream=True, insecure=force):  # type: ignore[union-attr]
                yield progress
        except Exception as e:
            logger.error(f"Async streaming pull failed for {model}: {e}")
            raise OllamaConnectionError(f"Streaming pull failed: {e}") from e

    def delete_model(self, model: str) -> Any:
        """Delete a model from local storage.

        Args:
            model: Model name to delete.

        Returns:
            Response dictionary.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
        """
        try:
            response = self._client.delete(model)
            logger.info(f"Deleted model: {model}")
            return response
        except Exception as e:
            logger.error(f"Failed to delete model {model}: {e}")
            raise OllamaConnectionError(f"Failed to delete model: {e}") from e

    async def async_delete_model(self, model: str) -> Any:
        """Delete a model from local storage asynchronously.

        Args:
            model: Model name to delete.

        Returns:
            Response dictionary.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
        """
        try:
            response = await self._aclient().delete(model)
            logger.info(f"Deleted model (async): {model}")
            return response
        except Exception as e:
            logger.error(f"Failed to delete model (async) {model}: {e}")
            raise OllamaConnectionError(f"Failed to delete model: {e}") from e

    def embeddings(
        self,
        model: Optional[str],
        prompt: str,
    ) -> List[float]:
        """Generate embeddings for a prompt.

        Args:
            model: Model name (uses default if not provided).
            prompt: Text to generate embeddings for.

        Returns:
            List of embedding values.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
        """
        model = self._ensure_model(model)
        try:
            response = self._client.embeddings(model=model, prompt=prompt)
            logger.info(f"Generated embeddings for model: {model}")
            return response.get("embedding", [])
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise OllamaConnectionError(f"Failed to generate embeddings: {e}") from e

    async def async_embeddings(
        self,
        model: Optional[str],
        prompt: str,
    ) -> List[float]:
        """Generate embeddings for a prompt asynchronously.

        Args:
            model: Model name (uses default if not provided).
            prompt: Text to generate embeddings for.

        Returns:
            List of embedding values.

        Raises:
            OllamaConnectionError: If unable to connect to Ollama server.
        """
        model = self._ensure_model(model)
        try:
            response = await self._aclient().embeddings(model=model, prompt=prompt)
            logger.info(f"Generated embeddings (async) for model: {model}")
            return response.get("embedding", [])
        except Exception as e:
            logger.error(f"Failed to generate embeddings (async): {e}")
            raise OllamaConnectionError(f"Failed to generate embeddings: {e}") from e

    def check_connection(self) -> bool:
        """Check if connection to Ollama server is available.

        Returns:
            True if connected, False otherwise.
        """
        try:
            self._client.list()
            return True
        except Exception:
            return False

    async def async_check_connection(self) -> bool:
        """Check if connection to Ollama server is available (async).

        Returns:
            True if connected, False otherwise.
        """
        try:
            await self._aclient().list()
            return True
        except Exception:
            return False
