"""MCP server exposing Snowflake Cortex capabilities to any MCP client
(Claude Desktop, Claude Code, Cursor, ...).

Run over stdio:
    python -m snowcortex.mcp_server

Claude Desktop / Claude Code config example:
    {
      "mcpServers": {
        "snowcortex": {
          "command": "python",
          "args": ["-m", "snowcortex.mcp_server"],
          "env": {"SNOWFLAKE_CONNECTION_NAME": "default"}
        }
      }
    }

Note: Snowflake also offers a fully managed MCP server. This one is a small,
self-hosted example you can extend with your own tools.
"""

from __future__ import annotations

import json
from functools import lru_cache

from mcp.server.fastmcp import FastMCP

from . import llm
from .agent import CortexAgent
from .analyst import CortexAnalyst
from .connection import get_connection
from .rag import KnowledgeBase

mcp = FastMCP("snowcortex")


@lru_cache(maxsize=1)
def _conn():
    return get_connection()


@mcp.tool()
def cortex_complete(prompt: str, model: str | None = None) -> str:
    """Generate text with a Snowflake Cortex LLM."""
    return llm.complete(_conn(), prompt, model)


@mcp.tool()
def cortex_summarize(text: str) -> str:
    """Summarize text with Snowflake Cortex."""
    return llm.summarize(_conn(), text)


@mcp.tool()
def cortex_sentiment(text: str) -> float:
    """Sentiment score from -1 (negative) to 1 (positive)."""
    return llm.sentiment(_conn(), text)


@mcp.tool()
def cortex_classify(text: str, categories: list[str]) -> str:
    """Classify text into one of the given categories."""
    return llm.classify(_conn(), text, categories)


@mcp.tool()
def search_knowledge_base(query: str, limit: int = 5, category: str | None = None) -> str:
    """Hybrid search over the support knowledge base (Cortex Search). Returns JSON."""
    hits = KnowledgeBase(_conn()).search(query, limit=limit, category=category)
    return json.dumps(hits, indent=2, default=str)


@mcp.tool()
def answer_from_knowledge_base(question: str) -> str:
    """RAG: answer a question grounded in the knowledge base, with sources."""
    result = KnowledgeBase(_conn()).answer(question)
    titles = ", ".join(str(h.get("TITLE")) for h in result.sources)
    return f"{result.answer}\n\nSources: {titles}"


@mcp.tool()
def ask_data_analyst(question: str) -> str:
    """Ask a natural-language question about support-ticket data (Cortex Analyst).

    Returns the generated SQL and the resulting rows as JSON.
    """
    result, rows = CortexAnalyst(_conn()).ask_and_run(question)
    return json.dumps({"explanation": result.text, "sql": result.sql, "rows": rows}, indent=2, default=str)


@mcp.tool()
def ask_agent(question: str) -> str:
    """Ask the Cortex Agent, which combines data analysis and knowledge-base search."""
    return CortexAgent(_conn()).ask(question).text


def main() -> None:
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
