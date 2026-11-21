"""Thin Python wrappers around the Cortex LLM SQL functions.

Every call is a plain `SELECT SNOWFLAKE.CORTEX.<fn>(...)` using bind parameters, so
text is never interpolated into SQL.
"""

from __future__ import annotations

import json
from typing import Sequence

from .config import get_settings


def _scalar(conn, sql: str, params: Sequence) -> object:
    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
    return row[0] if row else None


def complete(conn, prompt: str, model: str | None = None) -> str:
    """Free-form text generation."""
    model = model or get_settings().llm_model
    return str(_scalar(conn, "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)", (model, prompt)))


def summarize(conn, text: str) -> str:
    return str(_scalar(conn, "SELECT SNOWFLAKE.CORTEX.SUMMARIZE(%s)", (text,)))


def sentiment(conn, text: str) -> float:
    """Sentiment score between -1 (negative) and 1 (positive)."""
    return float(_scalar(conn, "SELECT SNOWFLAKE.CORTEX.SENTIMENT(%s)", (text,)))


def translate(conn, text: str, source_lang: str, target_lang: str) -> str:
    return str(
        _scalar(conn, "SELECT SNOWFLAKE.CORTEX.TRANSLATE(%s, %s, %s)", (text, source_lang, target_lang))
    )


def classify(conn, text: str, categories: Sequence[str]) -> str:
    """Zero-shot classification into one of `categories`."""
    if len(categories) < 2:
        raise ValueError("Provide at least two categories.")
    placeholders = ", ".join(["%s"] * len(categories))
    sql = f"SELECT SNOWFLAKE.CORTEX.CLASSIFY_TEXT(%s, ARRAY_CONSTRUCT({placeholders}))"
    raw = _scalar(conn, sql, (text, *categories))
    return parse_label(raw)


def extract_answer(conn, text: str, question: str) -> str | None:
    """Extract the answer to `question` from `text`."""
    raw = _scalar(conn, "SELECT SNOWFLAKE.CORTEX.EXTRACT_ANSWER(%s, %s)", (text, question))
    return parse_extracted_answer(raw)


def extract_json(conn, text: str, instruction: str, model: str | None = None) -> dict | None:
    """Ask the model for a JSON object and parse it defensively."""
    prompt = (
        f"{instruction}\n\nRespond with ONLY a valid JSON object, no prose, no code fences.\n\n"
        f"Text:\n{text}"
    )
    return parse_json_object(complete(conn, prompt, model))


# --- pure helpers (unit-tested without a Snowflake connection) -----------------


def parse_label(raw: object) -> str:
    """CLASSIFY_TEXT returns {"label": "..."} (as a JSON string or dict)."""
    data = json.loads(raw) if isinstance(raw, str) else raw
    return str(data["label"])


def parse_extracted_answer(raw: object) -> str | None:
    """EXTRACT_ANSWER returns [{"answer": "...", "score": 0.9}, ...]."""
    data = json.loads(raw) if isinstance(raw, str) else raw
    if not data:
        return None
    return data[0].get("answer")


def parse_json_object(text: str) -> dict | None:
    """Parse a JSON object from model output, tolerating code fences and stray prose."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
