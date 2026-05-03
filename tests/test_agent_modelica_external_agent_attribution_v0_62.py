from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_external_agent_attribution_v0_62_0 import (
    build_external_agent_attribution_summary,
    classify_repair_pattern,
    run_external_agent_attribution,
)


class ExternalAgentAttributionV062Tests(unittest.TestCase):
    def test_classify_repair_pattern_detects_zero_flow_constraints(self) -> None:
        pattern = classify_repair_pattern(
            """
            model M
            equation
              p[1].i = 0;
              n[1].i = 0;
            end M;
            """
        )
        self.assertEqual(pattern["repair_pattern"], "probe_zero_flow_constraint")
        self.assertEqual(pattern["zero_flow_equation_count"], 2)

    def test_build_summary_reports_paired_difference_and_attribution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            final_model = root / "final.mo"
            final_model.write_text(
                "model M\n connector Pin flow Real i; Real v; end Pin;\n Pin p;\n equation\n p.i = 0;\nend M;\n",
                encoding="utf-8",
            )
            gateforge_rows = [
                {
                    "case_id": "case_a",
                    "final_verdict": "FAILED",
                    "submitted": False,
                    "step_count": 2,
                    "provider_error": "",
                    "steps": [
                        {
                            "tool_calls": [
                                {
                                    "name": "check_model",
                                    "arguments": {"model_text": "model M equation p[1].i = 0; end M;"},
                                }
                            ],
                            "tool_results": [
                                {
                                    "result": 'Class M has 2 equation(s) and 4 variable(s). resultFile = ""'
                                }
                            ]
                        }
                    ],
                }
            ]
            external_rows = [
                {
                    "case_id": "case_a",
                    "final_verdict": "PASS",
                    "submitted": True,
                    "omc_invocation_count": 3,
                    "final_model_path": str(final_model),
                }
            ]
            verification = {
                "provider_blocked_count": 0,
                "rows": [{"case_id": "case_a", "check_ok": True, "simulate_ok": True}],
            }
            summary = build_external_agent_attribution_summary(
                gateforge_rows=gateforge_rows,
                external_rows=external_rows,
                verification_summary=verification,
            )
        self.assertTrue(summary["conclusion_allowed"])
        self.assertEqual(summary["gateforge_pass_count"], 0)
        self.assertEqual(summary["external_verified_pass_count"], 1)
        self.assertEqual(summary["paired_difference_case_ids"], ["case_a"])
        self.assertEqual(
            summary["gateforge_failure_attribution_counts"]["zero_flow_pattern_underfit"],
            1,
        )

    def test_build_summary_detects_successful_candidate_not_submitted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            final_model = root / "final.mo"
            final_model.write_text("model M\n Real x;\nequation\n x = 1;\nend M;\n", encoding="utf-8")
            summary = build_external_agent_attribution_summary(
                gateforge_rows=[
                    {
                        "case_id": "case_a",
                        "final_verdict": "FAILED",
                        "submitted": False,
                        "provider_error": "",
                        "steps": [
                            {
                                "tool_results": [
                                    {"result": 'record SimulationResult resultFile = "/workspace/M_res.mat"'}
                                ]
                            }
                        ],
                    }
                ],
                external_rows=[
                    {
                        "case_id": "case_a",
                        "final_verdict": "PASS",
                        "submitted": True,
                        "final_model_path": str(final_model),
                    }
                ],
                verification_summary={
                    "provider_blocked_count": 0,
                    "rows": [{"case_id": "case_a", "check_ok": True, "simulate_ok": True}],
                },
            )
        self.assertEqual(
            summary["gateforge_failure_attribution_counts"]["successful_candidate_not_submitted"],
            1,
        )

    def test_run_external_agent_attribution_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gf_path = root / "gateforge.jsonl"
            ext_dir = root / "external"
            out_dir = root / "out"
            ext_dir.mkdir()
            final_model = ext_dir / "case_a_final.mo"
            final_model.write_text("model M\n Real x;\nequation\n x = 1;\nend M;\n", encoding="utf-8")
            gf_path.write_text(
                json.dumps({"case_id": "case_a", "final_verdict": "PASS", "submitted": True})
                + "\n",
                encoding="utf-8",
            )
            (ext_dir / "case_a.json").write_text(
                json.dumps(
                    {
                        "case_id": "case_a",
                        "final_verdict": "PASS",
                        "submitted": True,
                        "omc_invocation_count": 1,
                        "final_model_path": str(final_model),
                    }
                ),
                encoding="utf-8",
            )
            verification_path = root / "verification.json"
            verification_path.write_text(
                json.dumps(
                    {
                        "provider_blocked_count": 0,
                        "rows": [{"case_id": "case_a", "check_ok": True, "simulate_ok": True}],
                    }
                ),
                encoding="utf-8",
            )
            summary = run_external_agent_attribution(
                gateforge_results_path=gf_path,
                external_results_dir=ext_dir,
                external_verification_path=verification_path,
                out_dir=out_dir,
            )
            self.assertEqual(summary["case_count"], 1)
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertTrue((out_dir / "paired_rows.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
