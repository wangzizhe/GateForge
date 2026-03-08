import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_l5_eval_v1 import evaluate_l5_eval_v1


class AgentModelicaL5EvalV1Tests(unittest.TestCase):
    def _base_inputs(self) -> tuple[dict, dict, dict, dict, dict]:
        run_summary = {
            "status": "PASS",
            "success_at_k_pct": 80.0,
            "median_repair_rounds": 1.0,
            "median_time_to_pass_sec": 12.0,
        }
        run_results = {
            "records": [
                {
                    "task_id": "t1",
                    "passed": True,
                    "rounds_used": 1,
                    "elapsed_sec": 11.0,
                    "hard_checks": {"physics_contract_pass": True, "regression_pass": True},
                    "attempts": [
                        {
                            "reason": "ok",
                            "stderr_snippet": "",
                            "log_excerpt": "",
                        }
                    ],
                },
                {
                    "task_id": "t2",
                    "passed": True,
                    "rounds_used": 1,
                    "elapsed_sec": 13.0,
                    "hard_checks": {"physics_contract_pass": True, "regression_pass": True},
                    "attempts": [
                        {
                            "reason": "ok",
                            "stderr_snippet": "",
                            "log_excerpt": "",
                        }
                    ],
                },
            ]
        }
        l3_quality = {
            "parse_coverage_pct": 100.0,
            "canonical_type_match_rate_pct": 80.0,
            "stage_match_rate_pct": 80.0,
            "low_confidence_rate_pct": 5.0,
        }
        l3_gate = {
            "status": "PASS",
            "gate_result": "PASS",
        }
        l4_ab = {
            "on": {
                "success_at_k_pct": 80.0,
                "physics_fail_rate_pct": 5.0,
                "regression_fail_rate_pct": 10.0,
                "infra_failure_count": 0,
            },
            "off": {
                "success_at_k_pct": 70.0,
                "physics_fail_rate_pct": 4.0,
                "regression_fail_rate_pct": 9.0,
                "infra_failure_count": 0,
            },
            "delta": {
                "success_at_k_pp": 10.0,
            },
        }
        return run_summary, run_results, l3_quality, l3_gate, l4_ab

    def test_eval_passes_with_thresholds_met(self) -> None:
        run_summary, run_results, l3_quality, l3_gate, l4_ab = self._base_inputs()
        summary = evaluate_l5_eval_v1(
            run_summary=run_summary,
            run_results=run_results,
            l3_quality_summary=l3_quality,
            l3_gate_summary=l3_gate,
            l4_ab_compare_summary=l4_ab,
            gate_mode="strict",
        )
        self.assertEqual(summary.get("status"), "PASS")
        self.assertEqual(summary.get("gate_result"), "PASS")
        self.assertEqual(float(summary.get("delta_success_at_k_pp") or 0.0), 10.0)

    def test_eval_fails_when_delta_below_threshold(self) -> None:
        run_summary, run_results, l3_quality, l3_gate, l4_ab = self._base_inputs()
        l4_ab["delta"] = {"success_at_k_pp": 1.0}
        summary = evaluate_l5_eval_v1(
            run_summary=run_summary,
            run_results=run_results,
            l3_quality_summary=l3_quality,
            l3_gate_summary=l3_gate,
            l4_ab_compare_summary=l4_ab,
            gate_mode="strict",
        )
        self.assertEqual(summary.get("status"), "FAIL")
        self.assertIn("delta_success_at_k_below_threshold", set(summary.get("reasons") or []))

    def test_eval_observe_mode_downgrades_fail_to_needs_review(self) -> None:
        run_summary, run_results, l3_quality, l3_gate, l4_ab = self._base_inputs()
        l4_ab["delta"] = {"success_at_k_pp": 0.0}
        summary = evaluate_l5_eval_v1(
            run_summary=run_summary,
            run_results=run_results,
            l3_quality_summary=l3_quality,
            l3_gate_summary=l3_gate,
            l4_ab_compare_summary=l4_ab,
            gate_mode="observe",
        )
        self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
        self.assertEqual(summary.get("gate_result"), "NEEDS_REVIEW")

    def test_eval_allows_zero_delta_when_baseline_success_is_at_ceiling(self) -> None:
        run_summary, run_results, l3_quality, l3_gate, l4_ab = self._base_inputs()
        l4_ab["off"]["success_at_k_pct"] = 100.0
        l4_ab["on"]["success_at_k_pct"] = 100.0
        l4_ab["delta"] = {"success_at_k_pp": 0.0}
        summary = evaluate_l5_eval_v1(
            run_summary=run_summary,
            run_results=run_results,
            l3_quality_summary=l3_quality,
            l3_gate_summary=l3_gate,
            l4_ab_compare_summary=l4_ab,
            gate_mode="strict",
        )
        self.assertEqual(summary.get("status"), "PASS")
        self.assertEqual(float(summary.get("effective_min_delta_success_at_k_pp") or 0.0), 0.0)

    def test_cli_writes_effective_thresholds(self) -> None:
        run_summary, run_results, l3_quality, l3_gate, l4_ab = self._base_inputs()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_summary_path = root / "run_summary.json"
            run_results_path = root / "run_results.json"
            l3_quality_path = root / "l3_quality.json"
            l3_gate_path = root / "l3_gate.json"
            l4_ab_path = root / "l4_ab.json"
            out_path = root / "summary.json"

            run_summary_path.write_text(json.dumps(run_summary), encoding="utf-8")
            run_results_path.write_text(json.dumps(run_results), encoding="utf-8")
            l3_quality_path.write_text(json.dumps(l3_quality), encoding="utf-8")
            l3_gate_path.write_text(json.dumps(l3_gate), encoding="utf-8")
            l4_ab_path.write_text(json.dumps(l4_ab), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_l5_eval_v1",
                    "--run-summary",
                    str(run_summary_path),
                    "--run-results",
                    str(run_results_path),
                    "--l3-quality-summary",
                    str(l3_quality_path),
                    "--l3-gate-summary",
                    str(l3_gate_path),
                    "--l4-ab-compare-summary",
                    str(l4_ab_path),
                    "--min-delta-success-at-k-pp",
                    "12",
                    "--out",
                    str(out_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0, msg=proc.stdout)
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            thresholds = payload.get("thresholds") if isinstance(payload.get("thresholds"), dict) else {}
            self.assertEqual(float(thresholds.get("min_delta_success_at_k_pp") or 0.0), 12.0)
            self.assertEqual(payload.get("status"), "FAIL")

    def test_reason_enum_strict_mode_flags_unknown_reason(self) -> None:
        run_summary, run_results, l3_quality, l3_gate, l4_ab = self._base_inputs()
        summary = evaluate_l5_eval_v1(
            run_summary=run_summary,
            run_results=run_results,
            l3_quality_summary=l3_quality,
            l3_gate_summary=l3_gate,
            l4_ab_compare_summary=l4_ab,
            gate_mode="strict",
            additional_reasons=["custom_unknown_reason_x"],
        )
        self.assertEqual(summary.get("status"), "FAIL")
        reasons = set(summary.get("reasons") or [])
        self.assertIn("reason_enum_unknown", reasons)
        unknown = set(summary.get("unknown_reasons") or [])
        self.assertIn("custom_unknown_reason_x", unknown)

    def test_reason_enum_observe_mode_stays_needs_review(self) -> None:
        run_summary, run_results, l3_quality, l3_gate, l4_ab = self._base_inputs()
        summary = evaluate_l5_eval_v1(
            run_summary=run_summary,
            run_results=run_results,
            l3_quality_summary=l3_quality,
            l3_gate_summary=l3_gate,
            l4_ab_compare_summary=l4_ab,
            gate_mode="observe",
            additional_reasons=["custom_unknown_reason_x"],
        )
        self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
        self.assertIn("reason_enum_unknown", set(summary.get("reasons") or []))


if __name__ == "__main__":
    unittest.main()
