"""HTTP backend for model-constellation (FastAPI).

A thin async layer over :class:`model_constellation.runtime.AgentRuntime` that lets
other apps, machines, or languages use the engine over HTTP. Requires the ``api``
extra:

    pip install "model-constellation[api]"
    model-constellation serve            # or: uvicorn model_constellation.api:app

See :mod:`model_constellation.api.server` for the app factory and settings.
"""

from model_constellation.api.server import APISettings, create_app

__all__ = ["create_app", "APISettings"]
