"""Main entry point for model-constellation CLI.

This module serves as the primary entry point when running model-constellation directly
via `python main.py` or when installed as a package.

It sets up logging, handles global exceptions, and delegates to the core CLI.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from model_constellation import __version__
from model_constellation.core import cli, setup_logging
from model_constellation.constants import DEFAULT_LOG_LEVEL, DEFAULT_LOG_FORMAT, MODEL_CONSTELLATION_DIR


def setup_application() -> logging.Logger:
    """Initialize application directories and logging.

    Returns:
        Configured logger instance.
    """
    MODEL_CONSTELLATION_DIR.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(DEFAULT_LOG_LEVEL)
    logger.debug(f"model-constellation v{__version__} starting up")
    logger.debug(f"Configuration directory: {MODEL_CONSTELLATION_DIR}")

    return logger


def handle_exception(exc_type, exc_value, exc_traceback) -> None:
    """Global exception handler for uncaught exceptions.

    Args:
        exc_type: Exception class
        exc_value: Exception instance
        exc_traceback: Traceback object
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger = logging.getLogger("model_constellation")
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    print(f"\n[ERROR] Fatal error: {exc_value}", file=sys.stderr)
    print("Run with --debug flag for detailed traceback.", file=sys.stderr)
    sys.exit(1)


def main(args: Optional[list[str]] = None) -> int:
    """Main entry point for model-constellation CLI.

    Args:
        args: Command line arguments (defaults to sys.argv)

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    logger = setup_application()

    sys.excepthook = handle_exception

    try:
        cli(obj={}, args=args)
        return 0
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130
    except EnvironmentError as e:
        logger.error(f"Environment error: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
