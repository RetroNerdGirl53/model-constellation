"""model-constellation package main entry point.

This module enables running model-constellation via `python -m model_constellation` command.
It simply delegates to the core CLI module.
"""

from model_constellation.core import main

if __name__ == "__main__":
    main()
