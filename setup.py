"""Setup configuration for model-constellation package.

This module provides the setuptools configuration for installing model-constellation
as a Python package. It reads dependencies from pyproject.toml and
defines entry points for console scripts.
"""

from pathlib import Path

from setuptools import find_packages, setup

here = Path(__file__).parent.resolve()

long_description = """
# model-constellation - Ollama-Powered CLI AI Agent Framework

model-constellation is a powerful CLI framework that brings AI agent capabilities to your terminal.
Built on top of Ollama, it enables you to create and manage AI agents that can
execute tasks, run commands, and collaborate in swarms.

## Features

- **AI-Powered CLI**: Interact with Ollama models directly from your terminal
- **Agent Management**: Create, manage, and orchestrate multiple AI agents
- **Agent Swarms**: Coordinate multiple agents to work on complex tasks
- **Tool Execution**: Agents can execute real commands with permission controls
- **Interactive Mode**: Chat with AI agents in an interactive session
- **Flexible Configuration**: Customize models, permissions, and behavior

## Quick Start

```bash
# Run a simple query
model-constellation run "Hello, how are you?"

# Start interactive mode
model-constellation interactive

# Create an agent
model-constellation agent create my-agent --type specialized

# List available models
model-constellation model list --local
```

## Requirements

- Python 3.10+
- Ollama server running locally or remotely

## Installation

```bash
# From source
pip install -e .

# Or install directly
pip install .
```

See the full documentation at: https://github.com/model_constellation/model_constellation
"""

setup(
    name="model-constellation",
    version="1.1.0",
    description="Ollama-powered CLI AI agent framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="model-constellation Team",
    author_email="team@model_constellation.ai",
    url="https://github.com/model_constellation/model_constellation",
    project_urls={
        "Bug Tracker": "https://github.com/model_constellation/model_constellation/issues",
        "Documentation": "https://github.com/model_constellation/model_constellation#readme",
        "Source Code": "https://github.com/model_constellation/model_constellation",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="ai ollama cli agent llm",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.10",
    install_requires=[
        "ollama>=0.3.0",
        "pytermgui>=7.0.0",
        "pyyaml>=6.0",
        "requests>=2.31.0",
        "click>=8.1.0",
        "rich>=13.0.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "api": [
            "fastapi>=0.110.0",
            "uvicorn>=0.27.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "httpx>=0.27.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "model-constellation=model_constellation.core:main",
        ],
    },
    package_data={
        "model_constellation": ["py.typed"],
    },
    zip_safe=False,
)
