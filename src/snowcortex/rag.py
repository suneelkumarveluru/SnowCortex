"""Retrieval-augmented generation: Cortex Search for retrieval, Cortex COMPLETE for the answer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Settings, get_settings
from .connection import get_root
from .llm import complete

RAG_PROMPT = """You are a helpful support assistant. Answer the question using ONLY the context below.
If the context does not contain the answer, say you don't know and suggest contacting support.
Cite the article titles you used in square brackets.

<context>
{context}
</context>

Question: {question}
Answer:"""


@dataclass
class RagAnswer:
    answer: str
    sources: list[dict[str, Any]]


class KnowledgeBase:
    """Query a Cortex Search service and answer questions grounded in the results."""

    def __init__(self, conn, settings: Settings | None = None):
        self.conn = conn
        self.settings = settings or get_settings()
        s = self.settings
        self._service = (
            get_root(conn)
            .databases[s.database]
            .schemas[s.schema]
            .cortex_search_services[s.search_service]
        )

    def search(
        self,
        query: str,
        limit: int = 5,
        category: str | None = None,
        columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid (keyword + vector) search. Optionally filter on the CATEGORY attribute."""
        kwargs: dict[str, Any] = {
            "query": query,
            "columns": columns or ["TITLE", "CATEGORY", "BODY"],
            "limit": limit,
        }
        if category:
            kwargs["filter"] = {"@eq": {"CATEGORY": category}}
        response = self._service.search(**kwargs)
        return list(response.results)

    def answer(self, question: str, limit: int = 3, category: str | None = None) -> RagAnswer:
        hits = self.search(question, limit=limit, category=category)
        prompt = RAG_PROMPT.format(context=build_context(hits), question=question)
        return RagAnswer(answer=complete(self.conn, prompt, self.settings.llm_model), sources=hits)


def build_context(hits: list[dict[str, Any]]) -> str:
    """Format search hits as a numbered context block for the prompt."""
    if not hits:
        return "(no relevant articles found)"
    parts = []
    for i, hit in enumerate(hits, start=1):
        parts.append(f"[{i}] {hit.get('TITLE', 'Untitled')}\n{hit.get('BODY', '')}")
    return "\n\n".join(parts)
