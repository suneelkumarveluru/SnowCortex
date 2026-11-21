"""Command-line entry point:  python -m snowcortex.cli <command>  (or `snowcortex <command>`)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import get_settings
from .connection import get_connection


def _print_rows(rows: list[dict]) -> None:
    print(json.dumps(rows, indent=2, default=str) if rows else "(no rows)")


def cmd_complete(args) -> None:
    from . import llm

    print(llm.complete(get_connection(), args.prompt, args.model))


def cmd_sentiment(args) -> None:
    from . import llm

    print(f"{llm.sentiment(get_connection(), args.text):.3f}")


def cmd_classify(args) -> None:
    from . import llm

    print(llm.classify(get_connection(), args.text, args.categories))


def cmd_search(args) -> None:
    from .rag import KnowledgeBase

    hits = KnowledgeBase(get_connection()).search(args.query, limit=args.limit, category=args.category)
    for hit in hits:
        print(f"- [{hit.get('CATEGORY')}] {hit.get('TITLE')}\n  {str(hit.get('BODY', ''))[:160]}...")


def cmd_ask(args) -> None:
    from .rag import KnowledgeBase

    result = KnowledgeBase(get_connection()).answer(args.question, category=args.category)
    print(result.answer)
    print("\nSources:", ", ".join(str(h.get("TITLE")) for h in result.sources))


def cmd_analyst(args) -> None:
    from .analyst import CortexAnalyst

    result, rows = CortexAnalyst(get_connection()).ask_and_run(args.question)
    if result.text:
        print(result.text, "\n")
    if result.sql:
        print("SQL:\n" + result.sql, "\n")
    _print_rows(rows)


def cmd_agent(args) -> None:
    from .agent import CortexAgent

    agent = CortexAgent(get_connection())
    if args.raw:
        for event in agent.stream(args.question):
            print(json.dumps(event, default=str))
        return
    print(agent.ask(args.question).text)


def cmd_upload_model(args) -> None:
    """PUT the semantic model YAML onto the Snowflake stage."""
    s = get_settings()
    path = Path(args.file).resolve()
    if not path.exists():
        sys.exit(f"File not found: {path}")
    stage = f"@{s.database}.{s.schema}.{s.semantic_stage}"
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(f"PUT 'file://{path.as_posix()}' {stage} AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
        print(cur.fetchall())
    print(f"Uploaded to {stage}/{path.name}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="snowcortex", description="Snowflake Cortex toolkit")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("complete", help="LLM text generation")
    c.add_argument("prompt")
    c.add_argument("--model")
    c.set_defaults(func=cmd_complete)

    c = sub.add_parser("sentiment", help="Sentiment score (-1..1)")
    c.add_argument("text")
    c.set_defaults(func=cmd_sentiment)

    c = sub.add_parser("classify", help="Zero-shot classification")
    c.add_argument("text")
    c.add_argument("categories", nargs="+")
    c.set_defaults(func=cmd_classify)

    c = sub.add_parser("search", help="Cortex Search over the knowledge base")
    c.add_argument("query")
    c.add_argument("--limit", type=int, default=5)
    c.add_argument("--category")
    c.set_defaults(func=cmd_search)

    c = sub.add_parser("ask", help="RAG answer grounded in the knowledge base")
    c.add_argument("question")
    c.add_argument("--category")
    c.set_defaults(func=cmd_ask)

    c = sub.add_parser("analyst", help="Cortex Analyst: natural language -> SQL -> rows")
    c.add_argument("question")
    c.set_defaults(func=cmd_analyst)

    c = sub.add_parser("agent", help="Cortex Agent (Search + Analyst)")
    c.add_argument("question")
    c.add_argument("--raw", action="store_true", help="print raw SSE events")
    c.set_defaults(func=cmd_agent)

    c = sub.add_parser("upload-model", help="Upload the semantic model YAML to the stage")
    c.add_argument("--file", default="semantic_models/support_tickets.yaml")
    c.set_defaults(func=cmd_upload_model)

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
