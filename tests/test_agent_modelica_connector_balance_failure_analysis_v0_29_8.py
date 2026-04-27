from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_connector_balance_failure_analysis_v0_29_8 import (
    build_connector_balance_failure_analysis,
    classify_patch_patterns,
    run_connector_balance_failure_analysis,
)


def _row(tool_profile: str, tools: list[str]) -> dict:
    steps = []
    for idx, tool in enumerate(tools):
        model_text = (
            "model Case\n"
            "  connector MeasurementPin\n"
            "    Real v;\n"
            "    flow Real i;\n"
            "    flow Real iSense;\n"
            "  end MeasurementPin;\n"
            "  model MeasurementAdapter\n"
            "    MeasurementPin p;\n"
            "    MeasurementPin n;\n"
            "    output Real v;\n"
            "  equation\n"
            "    v = p.v - n.v;\n"
            "    p.i + n.i = 0;\n"
            "  end MeasurementAdapter;\n"
            "  Modelica.Electrical.Analog.Basic.Capacitor C1(C=0.001);\n"
            "  MeasurementAdapter adapter;\n"
            "equation\n"
            "  adapter.p.v = C1.p.v;\n"
            "  adapter.n.v = C1.n.v;\n"
            "end Case;\n"
        )
        if idx == 1:
            model_text = model_text.replace("    flow Real iSense;\n", "")
        steps.append(
            {
                "step": idx,
                "tool_calls": [{"name": tool, "arguments": {"model_text": model_text}}],
                "tool_results": [
                    {
                        "name": tool,
                        "result": (
                            "Class Case has 33 equation(s) and 32 variable(s).\n"
                            "messages = \"Failed to build model: Case\"\n"
                        ),
                    }
                ],
            }
        )
    return {
        "case_id": "singleroot2_03_connector_balance_migration",
        "tool_profile": tool_profile,
        "final_verdict": "FAILED",
        "submitted": False,
        "step_count": len(steps),
        "token_used": 123,
        "steps": steps,
    }


class ConnectorBalanceFailureAnalysisV0298Tests(unittest.TestCase):
    def test_classify_patch_patterns_detects_oscillation(self) -> None:
        patterns = classify_patch_patterns(
            [
                "connector P Real v; flow Real i; flow Real iSense; end P; equation adapter.p.v = C1.p.v; adapter.n.v = C1.n.v;",
                "connector P Real v; flow Real i; end P; equation adapter.p.v = C1.p.v; adapter.n.v = C1.n.v;",
                "connector P Real v; flow Real i; Real iSense; Real vSense; end P; equation connect(adapter.p, C1.p);",
            ]
        )
        self.assertTrue(patterns["removed_extra_flow_sensor"])
        self.assertTrue(patterns["demoted_extra_flow_sensor_to_plain_real"])
        self.assertTrue(patterns["added_extra_potential_sensor"])
        self.assertTrue(patterns["oscillation_detected"])

    def test_build_summary_marks_connector_semantics_gap(self) -> None:
        summary = build_connector_balance_failure_analysis(
            base_row=_row("base", ["check_model", "check_model"]),
            structural_row=_row("structural", ["check_model", "get_unmatched_vars", "causalized_form"]),
        )
        self.assertEqual(summary["status"], "PASS")
        self.assertTrue(summary["comparison"]["both_arms_failed"])
        self.assertEqual(summary["comparison"]["primary_failure_class"], "connector_balance_semantics_gap")
        self.assertTrue(summary["structural"]["tool_usage"]["structural_tool_calls"] >= 2)

    def test_run_analysis_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_path = root / "base.jsonl"
            structural_path = root / "structural.jsonl"
            out_dir = root / "out"
            base_path.write_text(json.dumps(_row("base", ["check_model"])) + "\n", encoding="utf-8")
            structural_path.write_text(
                json.dumps(_row("structural", ["check_model", "causalized_form"])) + "\n",
                encoding="utf-8",
            )
            summary = run_connector_balance_failure_analysis(
                base_results_path=base_path,
                structural_results_path=structural_path,
                out_dir=out_dir,
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
