"""Run the HTTP API: ``python -m model_constellation.api``."""

from __future__ import annotations


def main() -> None:
    import os

    import uvicorn

    host = os.environ.get("MC_API_HOST", "127.0.0.1")
    port = int(os.environ.get("MC_API_PORT", "8000"))
    # Import string so uvicorn can manage the app lifecycle; settings come from env.
    uvicorn.run("model_constellation.api.server:app", host=host, port=port)


if __name__ == "__main__":
    main()
