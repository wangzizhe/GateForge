from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_trajectory_diff_v0_64_0 import (
    build_trajectory_diff_summary,
    extract_gateforge_candidate_trace,
    run_trajectory_diff,
    zero_flow_targets,
)


class TrajectoryDiffV064Tests(unittest.TestCase):
    def test_zero_flow_targets_are_sorted(self) -> None:
        self.assertEqual(zero_flow_targets("n.i = 0; p[1].i=0;"), ["n.i", "p[1].i"])

    def test_extract_gateforge_candidate_trace_reports_delta_and_success(self) -> None:
        trace = extract_gateforge_candidate_trace(
            {
                "steps": [
                    {
                        "step": 1,
                        "tool_calls": [
                            {
                                "name": "check_model",
                                "arguments": {"model_text": "model M equation p.i = 0; end M;"},
                            }
                        ],
                        "tool_results": [
                            {
                                "result": 'Class M has 2 equation(s) and 3 variable(s). record SimulationResult resultFile = ""'
                            }
                        ],
                    },
                    {
                        "step": 2,
                        "tool_calls": [
                            {
                                "name": "simulate_model",
                                "arguments": {"model_text": "model M equation p.i = 0; n.i = 0; end M;"},
                            }
                        ],
                        "tool_results": [
                            {
                                "result": 'Class M has 3 equation(s) and 3 variable(s). record SimulationResult resultFile = "/workspace/M_res.mat"'
                            }
                        ],
                    },
                ]
            }
        )
        self.assertEqual(trace[0]["equation_variable_delta"], -1)
        self.assertFalse(trace[0]["omc_success"])
        self.assertTrue(trace[1]["omc_success"])
        self.assertEqual(trace[1]["zero_flow_count"], 2)

    def test_build_summary_reports_difference_buckets(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            final_model = root / "final.mo"
            final_model.write_text("model M equation p.i = 0; n.i = 0; end M;", encoding="utf-8")
            summary = build_trajectory_diff_summary(
                gateforge_rows=[
                    {
                        "case_id": "case_a",
                        "final_verdict": "FAILED",
                        "submitted": False,
                        "steps": [
                            {
                                "step": 1,
                                "tool_calls": [
                                    {
                                        "name": "check_model",
                                        "arguments": {"model_text": "model M equation p.i = 0; end M;"},
                                    }
                                ],
                                "tool_results": [{"result": "Class M has 2 equation(s) and 3 variable(s)."}],
                            }
                        ],
                    }
                ],
                external_rows={"case_a": {"final_model_path": str(final_model), "omc_invocation_count": 1}},
                attribution_summary={
                    "paired_rows": [
                        {
                            "case_id": "case_a",
                            "paired_outcome": "gateforge_fail_external_pass",
                            "gateforge_failure_attribution": "zero_flow_pattern_underfit",
                        }
                    ]
                },
            )
        self.assertEqual(summary["paired_difference_count"], 1)
        self.assertEqual(summary["diff_zero_flow_attempt_without_exact_match_count"], 1)

    def test_run_trajectory_diff_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gf = root / "gf.jsonl"
            ext_dir = root / "ext"
            out_dir = root / "out"
            ext_dir.mkdir()
            model = ext_dir / "final.mo"
            model.write_text("model M equation p.i = 0; end M;", encoding="utf-8")
            gf.write_text(json.dumps({"case_id": "case_a", "steps": []}) + "\n", encoding="utf-8")
            (ext_dir / "case_a.json").write_text(
                json.dumps({"case_id": "case_a", "final_model_path": str(model)}),
                encoding="utf-8",
            )
            attr = root / "attr.json"
            attr.write_text(json.dumps({"paired_rows": [{"case_id": "case_a"}]}), encoding="utf-8")
            summary = run_trajectory_diff(
                gateforge_results_path=gf,
                external_results_dir=ext_dir,
                attribution_path=attr,
                out_dir=out_dir,
            )
            self.assertEqual(summary["case_count"], 1)
            self.assertTrue((out_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
