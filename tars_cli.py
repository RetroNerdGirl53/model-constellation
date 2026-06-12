#!/usr/bin/env python3
"""Simple CLI wrapper for model-constellation.

This module provides a simplified CLI entry point that can be run directly
with `python tars_cli.py`. It's designed for users who want to run model-constellation
without installing it as a package.

Usage:
    python tars_cli.py --help
    python tars_cli.py run "Hello world"
    python tars_cli.py interactive
    python tars_cli.py --debug run "Test query"
"""

import argparse
import logging
import os
import sys
from pathlib import Path

TARS_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(TARS_ROOT.parent))

from model_constellation import __version__
from model_constellation.constants import (
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOG_FORMAT,
    TARS_DIR,
    ENV_BASE_URL,
    ENV_MODEL,
    ENV_LOG_LEVEL,
)


def setup_logging(level: str) -> logging.Logger:
    """Configure application logging.

    Args:
        level: Log level (debug, info, warning, error, critical)

    Returns:
        Configured logger instance.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format=DEFAULT_LOG_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger = logging.getLogger("model_constellation")
    logger.setLevel(log_level)

    return logger


def print_banner() -> None:
    """Print model-constellation ASCII banner."""
    banner = r"""
  _______ 
  |       |
  | MODEL_CONSTELLATION  |   Ollama-Powered CLI AI Agent
  |_______|   Version {}
    """.format(__version__)
    print(banner)


def check_ollama_connection(base_url: str) -> bool:
    """Check if Ollama server is accessible.

    Args:
        base_url: Ollama server URL

    Returns:
        True if connection successful, False otherwise
    """
    try:
        import requests

        response = requests.get(f"{base_url}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def main() -> int:
    """Main entry point for the CLI wrapper.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    parser = argparse.ArgumentParser(
        prog="model_constellation",
        description="model-constellation - Ollama-Powered CLI AI Agent Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --help
  %(prog)s run "What is Python?"
  %(prog)s interactive
  %(prog)s --debug run "List files"
  %(prog)s model list --local
        """,
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    parser.add_argument("--config", type=str, help="Path to configuration file")

    parser.add_argument(
        "--base-url",
        type=str,
        default=os.environ.get(ENV_BASE_URL, "http://localhost:11434"),
        help="Ollama server URL (default: http://localhost:11434)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=os.environ.get(ENV_MODEL, "llama2"),
        help="Default model to use",
    )

    parser.add_argument(
        "command", nargs="?", help="Command to run (run, interactive, agent, swarm, model, config)"
    )

    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments for the command")

    args = parser.parse_args()

    log_level = "debug" if args.debug else os.environ.get(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL)
    logger = setup_logging(log_level)

    logger.debug(f"model-constellation CLI wrapper v{__version__}")
    logger.debug(f"Base URL: {args.base_url}")
    logger.debug(f"Model: {args.model}")

    if not args.command:
        print_banner()
        parser.print_help()
        return 0

    if args.command == "version":
        print(f"model-constellation version {__version__}")
        return 0

    if args.command in ("run", "interactive", "agent", "swarm", "model", "config"):
        logger.info(f"Executing: {args.command}")

        if not check_ollama_connection(args.base_url):
            logger.warning(
                f"Cannot connect to Ollama at {args.base_url}. Make sure Ollama is running."
            )

            if args.command in ("run", "interactive"):
                response = input("Continue anyway? (y/N): ")
                if response.lower() != "y":
                    return 1

        try:
            from model_constellation.core import cli

            cli_args = [args.command] + args.args

            if args.debug:
                cli_args.insert(0, "--debug")
            if args.config:
                cli_args.insert(0, f"--config={args.config}")

            cli(obj={}, args=cli_args)
            return 0

        except ImportError as e:
            logger.error(f"Import error: {e}")
            print(f"Error: Could not import model_constellation modules: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            logger.exception(f"Error executing command: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1
    else:
        logger.error(f"Unknown command: {args.command}")
        print(f"Error: Unknown command '{args.command}'", file=sys.stderr)
        print("Run 'tars_cli.py --help' for usage information.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
