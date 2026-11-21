"""Cortex Agent: orchestrates Cortex Search (documents) + Cortex Analyst (structured data).

Calls the `agent:run` REST endpoint without a saved agent object, so everything the
agent needs is defined in code. See:
https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-run
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterator

import requests

from .config import Settings, get_settings
from .connection import auth_headers, rest_base_url

AGENT_PATH = "/api/v2/cortex/agent:run"

ORCHESTRATION_INSTRUCTIONS = (
    "Use the analyst tool for questions about ticket counts, priorities, resolution times "
    "and CSAT. Use the knowledge base search tool for how-to, troubleshooting and policy "
    "questions. For questions that need both, call both and combine the results."
)
RESPONSE_INSTRUCTIONS = "Be concise. Use bullet points for lists and mention which tool produced the facts."


@dataclass
class AgentAnswer:
    text: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)


def build_agent_request(question: str, settings: Settings, history: list[dict[str, Any]] | None = None) -> dict:
    """Request body for POST /api/v2/cortex/agent:run."""
    messages = list(history or [])
    messages.append({"role": "user", "content": [{"type": "text", "text": question}]})
    return {
        "models": {"orchestration": settings.agent_model},
        "instructions": {
            "orchestration": ORCHESTRATION_INSTRUCTIONS,
            "response": RESPONSE_INSTRUCTIONS,
        },
        "tools": [
            {
                "tool_spec": {
                    "type": "cortex_analyst_text_to_sql",
                    "name": "ticket_analyst",
                    "description": "Answers quantitative questions about support tickets "
                    "(volume, priority, status, resolution time, CSAT) by generating SQL.",
                }
            },
            {
                "tool_spec": {
                    "type": "cortex_search",
                    "name": "kb_search",
                    "description": "Searches the support knowledge base for troubleshooting "
                    "steps, how-to guides, security and billing policies.",
                }
            },
        ],
        "tool_resources": {
            "ticket_analyst": {
                "semantic_model_file": settings.semantic_model_path,
                "execution_environment": {"type": "warehouse", "warehouse": settings.warehouse},
            },
            "kb_search": {"name": settings.search_service_fqn, "max_results": 5},
        },
        "messages": messages,
    }


class CortexAgent:
    def __init__(self, conn, settings: Settings | None = None):
        self.conn = conn
        self.settings = settings or get_settings()

    def stream(self, question: str, history: list[dict[str, Any]] | None = None) -> Iterator[dict[str, Any]]:
        """Yield Server-Sent Events as {"event": str, "data": Any} dicts."""
        body = build_agent_request(question, self.settings, history)
        headers = auth_headers(self.conn, self.settings)
        headers["Accept"] = "text/event-stream"
        with requests.post(
            rest_base_url(self.conn) + AGENT_PATH, json=body, headers=headers, stream=True, timeout=900
        ) as resp:
            if resp.status_code >= 400:
                raise RuntimeError(f"Cortex Agent error {resp.status_code}: {resp.text}")
            yield from parse_sse(resp.iter_lines(decode_unicode=True))

    def ask(self, question: str, history: list[dict[str, Any]] | None = None) -> AgentAnswer:
        """Run the agent to completion and return the final text plus raw events."""
        answer = AgentAnswer()
        deltas: list[str] = []
        final_event: Any = None
        for event in self.stream(question, history):
            answer.events.append(event)
            name = event["event"]
            if name == "response.text.delta":
                deltas.append(_text_of(event["data"]))
            elif name == "response":
                final_event = event["data"]
        answer.text = "".join(deltas) or "".join(collect_text(final_event))
        return answer


# --- pure helpers (unit-tested without Snowflake) -------------------------------


def parse_sse(lines: Iterator[str]) -> Iterator[dict[str, Any]]:
    """Parse an SSE line stream into {"event", "data"} dicts. Data is JSON-decoded when possible."""
    event_name = "message"
    data_lines: list[str] = []

    def flush():
        nonlocal event_name, data_lines
        if not data_lines:
            event_name = "message"
            return None
        raw = "\n".join(data_lines)
        try:
            data: Any = json.loads(raw)
        except json.JSONDecodeError:
            data = raw
        out = {"event": event_name, "data": data}
        event_name, data_lines = "message", []
        return out

    for line in lines:
        if line is None:
            continue
        if line == "":
            item = flush()
            if item:
                yield item
        elif line.startswith(":"):
            continue  # SSE comment / keep-alive
        elif line.startswith("event:"):
            event_name = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].lstrip())
    item = flush()
    if item:
        yield item


def _text_of(data: Any) -> str:
    if isinstance(data, dict):
        return str(data.get("text", ""))
    return str(data) if data is not None else ""


def collect_text(node: Any) -> list[str]:
    """Walk a response object and gather every {"type": "text", "text": ...} fragment."""
    found: list[str] = []
    if isinstance(node, dict):
        if node.get("type") == "text" and isinstance(node.get("text"), str):
            found.append(node["text"])
        else:
            for value in node.values():
                found.extend(collect_text(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(collect_text(item))
    return found
