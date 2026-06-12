"""Web utilities for tools.

Provides web search, web fetch, and code search functionality.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def web_search(query: str, num_results: int = 8) -> str:
    """Search the web for information.

    Args:
        query: Search query.
        num_results: Number of results.

    Returns:
        Formatted search results.
    """
    try:
        from exa import Exa

        exa = Exa()
        results = exa.search(
            query,
            num_results=num_results,
            type="auto",
        )

        if not results.results:
            return "No results found"

        output_lines = []
        for i, result in enumerate(results.results, 1):
            title = getattr(result, "title", "Untitled")
            url = getattr(result, "url", "")
            snippet = getattr(result, "text", "")[:200]

            output_lines.append(f"{i}. {title}")
            output_lines.append(f"   URL: {url}")
            if snippet:
                output_lines.append(f"   {snippet}...")
            output_lines.append("")

        return "\n".join(output_lines)

    except ImportError:
        return "Error: exa-python package not installed. Install with: pip install exa-python"
    except Exception as e:
        logger.exception("Web search failed")
        return f"Search failed: {str(e)}"


def web_fetch(url: str, format: str = "markdown") -> str:
    """Fetch content from a URL.

    Args:
        url: URL to fetch.
        format: Output format (text, markdown, html).

    Returns:
        Fetched content.
    """
    try:
        from exa import Exa

        exa = Exa()
        result = exa.load_url(url)

        if not result:
            return "No content fetched"

        content = ""
        if hasattr(result, "text") and result.text:
            content = result.text
        elif hasattr(result, "html") and result.html:
            content = result.html

        if format == "text" and hasattr(result, "text"):
            return result.text
        elif format == "html" and hasattr(result, "html"):
            return result.html
        else:
            return content

    except ImportError:
        return "Error: exa-python package not installed. Install with: pip install exa-python"
    except Exception as e:
        logger.exception("Web fetch failed")
        return f"Fetch failed: {str(e)}"


def code_search(query: str, tokens_num: int = 5000) -> str:
    """Search code documentation and examples.

    Args:
        query: Search query.
        tokens_num: Maximum tokens to return.

    Returns:
        Code search results.
    """
    try:
        from exa import Exa

        exa = Exa()
        results = exa.search(
            query,
            num_results=5,
            type="code",
        )

        if not results.results:
            return "No code examples found"

        output_lines = []
        for i, result in enumerate(results.results, 1):
            title = getattr(result, "title", "Untitled")
            url = getattr(result, "url", "")
            snippet = getattr(result, "text", "")[:500]

            output_lines.append(f"--- Result {i} ---")
            output_lines.append(f"Title: {title}")
            output_lines.append(f"URL: {url}")
            output_lines.append("Code:")
            output_lines.append(snippet)
            output_lines.append("")

        return "\n".join(output_lines)

    except ImportError:
        return "Error: exa-python package not installed. Install with: pip install exa-python"
    except Exception as e:
        logger.exception("Code search failed")
        return f"Code search failed: {str(e)}"
