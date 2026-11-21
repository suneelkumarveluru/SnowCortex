"""Cortex Analyst client: natural-language question -> SQL (+ optional execution)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests

from .config import Settings, get_settings
from .connection import auth_headers, rest_base_url, run_query

ANALYST_PATH = "/api/v2/cortex/analyst/message"


@dataclass
class AnalystResult:
    text: str = ""
    sql: str | None = None
    suggestions: list[str] = field(default_factory=list)
    request_id: str | None = None
    message: dict[str, Any] = field(default_factory=dict)  # raw message, reusable as history


class CortexAnalyst:
    def __init__(self, conn, settings: Settings | None = None):
        self.conn = conn
        self.settings = settings or get_settings()

    def ask(self, question: str, history: list[dict[str, Any]] | None = None) -> AnalystResult:
        """Send a question. Pass `history` (previous messages) for multi-turn conversations."""
        messages = list(history or [])
        messages.append({"role": "user", "content": [{"type": "text", "text": question}]})
        body = {"messages": messages, "semantic_model_file": self.settings.semantic_model_path}

        resp = requests.post(
            rest_base_url(self.conn) + ANALYST_PATH,
            json=body,
            headers=auth_headers(self.conn, self.settings),
            timeout=120,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Cortex Analyst error {resp.status_code}: {resp.text}")
        return parse_analyst_response(resp.json())

    def ask_and_run(self, question: str, history: list[dict[str, Any]] | None = None):
        """Ask, then execute the generated SQL. Returns (AnalystResult, rows)."""
        result = self.ask(question, history)
        rows = run_query(self.conn, result.sql) if result.sql else []
        return result, rows


def parse_analyst_response(payload: dict[str, Any]) -> AnalystResult:
    """Flatten the Analyst response into text / sql / suggestions."""
    message = payload.get("message", {})
    result = AnalystResult(request_id=payload.get("request_id"), message=message)
    for item in message.get("content", []):
        kind = item.get("type")
        if kind == "text":
            result.text += item.get("text", "")
        elif kind == "sql":
            result.sql = item.get("statement")
        elif kind == "suggestions":
            result.suggestions.extend(item.get("suggestions", []))
    return result
