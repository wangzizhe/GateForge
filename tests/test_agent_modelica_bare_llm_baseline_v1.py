"""Unit tests for agent_modelica_bare_llm_baseline_v1."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gateforge.agent_modelica_bare_llm_baseline_v1 import (
    build_bare_prompt,
    extract_model_name,
    parse_bare_response,
    run_bare_repair,
)
from gateforge.agent_modelica_omc_workspace_v1 import WorkspaceModelLayout


class TestExtractModelName(unittest.TestCase):
    def test_simple_model(self):
        self.assertEqual(extract_model_name("model MyModel\nend MyModel;"), "MyModel")

    def test_block_keyword(self):
        self.assertEqual(extract_model_name("block PID\n  Real x;\nend PID;"), "PID")

    def test_class_keyword(self):
        self.assertEqual(extract_model_name("class Foo\nend Foo;"), "Foo")

    def test_connector_keyword(self):
        self.assertEqual(
            extract_model_name("connector Port\n  Real v;\nend Port;"), "Port"
        )

    def test_function_keyword(self):
        self.assertEqual(
            extract_model_name("function square\n  input Real x;\nend square;"),
            "square",
        )

    def test_leading_whitespace(self):
        self.assertEqual(extract_model_name("  model   Inner\nend Inner;"), "Inner")

    def test_fallback_empty(self):
        self.assertEqual(extract_model_name(""), "UnknownModel")

    def test_fallback_no_keyword(self):
        self.assertEqual(extract_model_name("Real x = 1.0;"), "UnknownModel")

    def test_first_match_wins(self):
        text = "model First\nend First;\nmodel Second\nend Second;"
        self.assertEqual(extract_model_name(text), "First")

    def test_mutation_comment_ignored(self):
        text = "model A1\n  Real x;\n  // GateForge mutation: check failure\nequation\n  der(x) = -x;\nend A1;"
        self.assertEqual(extract_model_name(text), "A1")


class TestBuildBarePrompt(unittest.TestCase):
    def setUp(self):
        self.prompt = build_bare_prompt(
            model_text="model Foo\nend Foo;",
            model_name="Foo",
            omc_error="Error: undefined variable",
        )

    def test_contains_model_name(self):
        self.assertIn("Foo", self.prompt)

    def test_contains_omc_error(self):
        self.assertIn("Error: undefined variable", self.prompt)

    def test_contains_begin_delimiter(self):
        self.assertIn("-----BEGIN_MODEL-----", self.prompt)

    def test_contains_end_delimiter(self):
        self.assertIn("-----END_MODEL-----", self.prompt)

    def test_contains_json_instruction(self):
        self.assertIn("repaired_model_text", self.prompt)

    def test_omc_error_truncated_at_2000(self):
        long_error = "x" * 3000
        p = build_bare_prompt("model T\nend T;", "T", long_error)
        # The omc_error slice is [:2000], so prompt should not contain all 3000 x's
        self.assertNotIn("x" * 2001, p)

    def test_empty_omc_error(self):
        p = build_bare_prompt("model T\nend T;", "T", "")
        self.assertIn("Model name: T", p)

    def test_model_text_preserved(self):
        self.assertIn("model Foo\nend Foo;", self.prompt)


class TestParseBareResponse(unittest.TestCase):
    def test_strict_json(self):
        raw = json.dumps({"repaired_model_text": "model Foo\nend Foo;"})
        self.assertEqual(parse_bare_response(raw), "model Foo\nend Foo;")

    def test_json_with_surrounding_text(self):
        # Use a single-line model text; literal newlines inside JSON strings are invalid.
        raw = 'Sure:\n{"repaired_model_text": "model X end X;"}\nDone.'
        self.assertEqual(parse_bare_response(raw), "model X end X;")

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_bare_response(""))

    def test_none_input_returns_none(self):
        self.assertIsNone(parse_bare_response(None))  # type: ignore[arg-type]

    def test_missing_key_returns_none(self):
        raw = json.dumps({"other_key": "value"})
        self.assertIsNone(parse_bare_response(raw))

    def test_empty_value_returns_none(self):
        raw = json.dumps({"repaired_model_text": "   "})
        self.assertIsNone(parse_bare_response(raw))

    def test_non_string_value_returns_none(self):
        raw = json.dumps({"repaired_model_text": 42})
        self.assertIsNone(parse_bare_response(raw))

    def test_invalid_json_returns_none(self):
        self.assertIsNone(parse_bare_response("this is not json"))

    def test_whitespace_stripped(self):
        raw = json.dumps({"repaired_model_text": "  model T\nend T;  "})
        result = parse_bare_response(raw)
        self.assertEqual(result, "model T\nend T;")

    def test_nested_json_in_text(self):
        # Should find the first valid object even with nesting noise
        payload = {"repaired_model_text": "model A\nend A;"}
        raw = f"Response: {json.dumps(payload)} End."
        self.assertEqual(parse_bare_response(raw), "model A\nend A;")


class TestRunBareRepair(unittest.TestCase):
    def test_uses_external_library_layout_when_metadata_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            mirrored_model = workspace / "Buildings" / "Examples" / "Demo.mo"
            mirrored_model.parent.mkdir(parents=True, exist_ok=True)
            layout = WorkspaceModelLayout(
                model_write_path=mirrored_model,
                model_load_files=["Buildings/package.mo", "Buildings/Examples/Demo.mo"],
                model_identifier="Buildings.Examples.Demo",
                uses_external_library=True,
            )

            with mock.patch(
                "gateforge.agent_modelica_bare_llm_baseline_v1.resolve_provider_adapter",
                return_value=(
                    object(),
                    mock.Mock(provider_name="gemini", api_key="set"),
                ),
            ), mock.patch(
                "gateforge.agent_modelica_bare_llm_baseline_v1.prepare_workspace_model_layout",
                return_value=layout,
            ) as prepare_layout, mock.patch(
                "gateforge.agent_modelica_bare_llm_baseline_v1.run_check_and_simulate",
                side_effect=[
                    (0, "Error", False, False),
                    (0, "OK", True, True),
                ],
            ) as run_check, mock.patch(
                "gateforge.agent_modelica_bare_llm_baseline_v1.send_with_budget",
                return_value=(json.dumps({"repaired_model_text": "model Demo end Demo;"}), ""),
            ):
                result = run_bare_repair(
                    model_text="model Demo end Demo;",
                    model_name="Demo",
                    backend="gemini",
                    source_library_path="/repo/Buildings",
                    source_package_name="Buildings",
                    source_library_model_path="/repo/Buildings/Examples/Demo.mo",
                    source_qualified_model_name="Buildings.Examples.Demo",
                )
                written_text = mirrored_model.read_text(encoding="utf-8")

        self.assertTrue(result["success"])
        prepare_layout.assert_called_once()
        first_call = run_check.call_args_list[0].kwargs
        second_call = run_check.call_args_list[1].kwargs
        self.assertEqual(
            first_call["model_load_files"],
            ["Buildings/package.mo", "Buildings/Examples/Demo.mo"],
        )
        self.assertEqual(first_call["model_name"], "Buildings.Examples.Demo")
        self.assertEqual(second_call["model_name"], "Buildings.Examples.Demo")
        self.assertEqual(written_text, "model Demo end Demo;")


if __name__ == "__main__":
    unittest.main()
