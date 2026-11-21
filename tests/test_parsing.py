"""Offline unit tests: no Snowflake account or network needed.

Run with:  python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snowcortex.agent import build_agent_request, collect_text, parse_sse  # noqa: E402
from snowcortex.analyst import parse_analyst_response  # noqa: E402
from snowcortex.config import Settings  # noqa: E402
from snowcortex.llm import parse_extracted_answer, parse_json_object, parse_label  # noqa: E402
from snowcortex.rag import build_context  # noqa: E402


class LlmParsing(unittest.TestCase):
    def test_label_from_json_string_and_dict(self):
        self.assertEqual(parse_label('{"label": "billing"}'), "billing")
        self.assertEqual(parse_label({"label": "bug"}), "bug")

    def test_extracted_answer(self):
        self.assertEqual(parse_extracted_answer('[{"answer": "DataSync", "score": 0.9}]'), "DataSync")
        self.assertIsNone(parse_extracted_answer("[]"))

    def test_json_object_tolerates_fences_and_prose(self):
        self.assertEqual(parse_json_object('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(parse_json_object('Sure! {"urgency": "high"} Hope that helps.'), {"urgency": "high"})
        self.assertIsNone(parse_json_object("no json here"))
        self.assertIsNone(parse_json_object("{not valid}"))


class AnalystParsing(unittest.TestCase):
    def test_flattens_message(self):
        payload = {
            "request_id": "abc",
            "message": {
                "role": "analyst",
                "content": [
                    {"type": "text", "text": "Here is the answer."},
                    {"type": "sql", "statement": "SELECT 1"},
                    {"type": "suggestions", "suggestions": ["What about next month?"]},
                ],
            },
        }
        r = parse_analyst_response(payload)
        self.assertEqual(r.text, "Here is the answer.")
        self.assertEqual(r.sql, "SELECT 1")
        self.assertEqual(r.suggestions, ["What about next month?"])
        self.assertEqual(r.request_id, "abc")


class AgentParsing(unittest.TestCase):
    def test_sse_parsing(self):
        lines = [
            "event: response.text.delta",
            'data: {"text": "Hello "}',
            "",
            ": keep-alive",
            "event: response.text.delta",
            'data: {"text": "world"}',
            "",
            "event: done",
            "data: [DONE]",
            "",
        ]
        events = list(parse_sse(iter(lines)))
        self.assertEqual([e["event"] for e in events], ["response.text.delta", "response.text.delta", "done"])
        self.assertEqual(events[0]["data"], {"text": "Hello "})
        self.assertEqual(events[2]["data"], "[DONE]")

    def test_sse_without_trailing_blank_line(self):
        events = list(parse_sse(iter(["event: x", 'data: {"a": 1}'])))
        self.assertEqual(events, [{"event": "x", "data": {"a": 1}}])

    def test_collect_text_walks_nested_structures(self):
        node = {"content": [{"type": "text", "text": "A"}, {"type": "tool_use", "x": [{"type": "text", "text": "B"}]}]}
        self.assertEqual(collect_text(node), ["A", "B"])

    def test_request_body_shape(self):
        s = Settings(database="DB", schema="SC", warehouse="WH", search_service="SVC",
                     semantic_stage="ST", semantic_file="m.yaml", agent_model="auto")
        body = build_agent_request("hi", s)
        self.assertEqual(body["messages"][-1]["content"][0]["text"], "hi")
        names = {t["tool_spec"]["name"] for t in body["tools"]}
        self.assertEqual(names, set(body["tool_resources"]))
        self.assertEqual(body["tool_resources"]["ticket_analyst"]["semantic_model_file"], "@DB.SC.ST/m.yaml")
        self.assertEqual(body["tool_resources"]["kb_search"]["name"], "DB.SC.SVC")


class RagContext(unittest.TestCase):
    def test_build_context(self):
        ctx = build_context([{"TITLE": "T1", "BODY": "b1"}, {"TITLE": "T2", "BODY": "b2"}])
        self.assertIn("[1] T1\nb1", ctx)
        self.assertIn("[2] T2\nb2", ctx)
        self.assertIn("no relevant", build_context([]))


class SemanticModel(unittest.TestCase):
    def test_yaml_is_valid_and_references_real_columns(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        root = Path(__file__).resolve().parents[1]
        model = yaml.safe_load((root / "semantic_models" / "support_tickets.yaml").read_text())
        table = model["tables"][0]
        ddl = (root / "sql" / "00_setup.sql").read_text()
        for dim in table["dimensions"] + table["time_dimensions"] + table["facts"][:1]:
            self.assertIn(dim["expr"], ddl, f"{dim['expr']} missing from 00_setup.sql")


if __name__ == "__main__":
    unittest.main()
