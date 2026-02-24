import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class GovernancePolicyAdvisorTests(unittest.TestCase):
    def test_advisor_suggests_strict_for_high_risk(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            trend = root / "trend.json"
            out = root / "advisor.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "kpis": {
                            "risk_score": 80,
                            "latest_mismatch_count": 3,
                        },
                        "risks": ["replay_risk_level_high"],
                    }
                ),
                encoding="utf-8",
            )
            trend.write_text(
                json.dumps(
                    {
                        "trend": {
                            "kpi_delta": {
                                "history_mismatch_total_delta": 2,
                                "risk_score_delta": 10,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_advisor",
                    "--snapshot",
                    str(snapshot),
                    "--trend",
                    str(trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertEqual(advice.get("suggested_policy_profile"), "industrial_strict")
            self.assertGreaterEqual(float(advice.get("confidence", 0.0)), 0.8)
            self.assertIn("high_replay_risk_score", advice.get("reasons", []))
            self.assertIsInstance(advice.get("why_now"), dict)
            self.assertIsInstance(advice.get("recommendation_scorecard"), dict)
            self.assertIn(advice.get("recommendation_scorecard", {}).get("priority"), {"normal", "high", "urgent"})

    def test_advisor_suggests_default_for_stable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            trend = root / "trend.json"
            out = root / "advisor.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "kpis": {
                            "risk_score": 5,
                            "latest_mismatch_count": 0,
                        },
                        "risks": [],
                    }
                ),
                encoding="utf-8",
            )
            trend.write_text(
                json.dumps(
                    {
                        "trend": {
                            "kpi_delta": {
                                "history_mismatch_total_delta": -1,
                                "risk_score_delta": -5,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_advisor",
                    "--snapshot",
                    str(snapshot),
                    "--trend",
                    str(trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertEqual(advice.get("suggested_policy_profile"), "default")
            self.assertIn("stable_replay_signals", advice.get("reasons", []))

    def test_advisor_uses_compare_and_apply_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            trend = root / "trend.json"
            compare = root / "compare.json"
            apply = root / "apply.json"
            out = root / "advisor.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "kpis": {
                            "risk_score": 20,
                            "latest_mismatch_count": 0,
                        },
                        "risks": [],
                    }
                ),
                encoding="utf-8",
            )
            trend.write_text(json.dumps({"trend": {"kpi_delta": {"history_mismatch_total_delta": 0, "risk_score_delta": 0}}}), encoding="utf-8")
            compare.write_text(json.dumps({"top_score_margin": 1, "explanation_completeness": 80}), encoding="utf-8")
            apply.write_text(json.dumps({"final_status": "NEEDS_REVIEW"}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_advisor",
                    "--snapshot",
                    str(snapshot),
                    "--trend",
                    str(trend),
                    "--compare-summary",
                    str(compare),
                    "--apply-summary",
                    str(apply),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertIn("compare_top_score_margin_low", advice.get("reasons", []))
            self.assertIn("compare_explanation_completeness_low", advice.get("reasons", []))
            self.assertIn("apply_status_needs_review", advice.get("reasons", []))
            self.assertIsInstance(advice.get("evidence_sources"), list)
            self.assertGreaterEqual(len(advice.get("evidence_sources") or []), 2)
            self.assertIn(type(advice.get("ranking_driver_signal")), {dict, type(None)})

    def test_advisor_uses_compare_pairwise_net_margin(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            trend = root / "trend.json"
            compare = root / "compare.json"
            out = root / "advisor.json"
            snapshot.write_text(
                json.dumps({"kpis": {"risk_score": 10, "latest_mismatch_count": 0}, "risks": []}),
                encoding="utf-8",
            )
            trend.write_text(
                json.dumps({"trend": {"kpi_delta": {"history_mismatch_total_delta": 0, "risk_score_delta": 0}}}),
                encoding="utf-8",
            )
            compare.write_text(
                json.dumps({"decision_explanation_leaderboard": [{"pairwise_net_margin": 1}]}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_advisor",
                    "--snapshot",
                    str(snapshot),
                    "--trend",
                    str(trend),
                    "--compare-summary",
                    str(compare),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertIn("compare_pairwise_net_margin_low", advice.get("reasons", []))
            patch = advice.get("threshold_patch", {})
            self.assertEqual(patch.get("require_min_pairwise_net_margin"), 2)
            self.assertGreaterEqual(float(advice.get("confidence") or 0.0), 0.66)

    def test_advisor_uses_mutation_summary_signals(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            trend = root / "trend.json"
            mutation = root / "mutation.json"
            out = root / "advisor.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "kpis": {"risk_score": 10, "latest_mismatch_count": 0},
                        "risks": [],
                    }
                ),
                encoding="utf-8",
            )
            trend.write_text(
                json.dumps({"trend": {"kpi_delta": {"history_mismatch_total_delta": 0, "risk_score_delta": 0}}}),
                encoding="utf-8",
            )
            mutation.write_text(
                json.dumps(
                    {
                        "trend_status": "NEEDS_REVIEW",
                        "compare_decision": "FAIL",
                        "latest_match_rate": 0.95,
                        "latest_gate_pass_rate": 0.96,
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_advisor",
                    "--snapshot",
                    str(snapshot),
                    "--trend",
                    str(trend),
                    "--mutation-summary",
                    str(mutation),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertEqual(advice.get("suggested_policy_profile"), "industrial_strict")
            self.assertIn("mutation_trend_needs_review", advice.get("reasons", []))
            self.assertIn("mutation_compare_regressed", advice.get("reasons", []))
            self.assertIn("mutation_match_rate_below_target", advice.get("reasons", []))
            self.assertIn("mutation_gate_pass_rate_below_target", advice.get("reasons", []))

    def test_advisor_uses_ranking_driver_signal_from_compare(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            snapshot = root / "snapshot.json"
            trend = root / "trend.json"
            compare = root / "compare.json"
            out = root / "advisor.json"
            snapshot.write_text(
                json.dumps({"kpis": {"risk_score": 15, "latest_mismatch_count": 0}, "risks": []}),
                encoding="utf-8",
            )
            trend.write_text(
                json.dumps({"trend": {"kpi_delta": {"history_mismatch_total_delta": 0, "risk_score_delta": 0}}}),
                encoding="utf-8",
            )
            compare.write_text(
                json.dumps(
                    {
                        "top_score_margin": 1,
                        "decision_explanation_ranking_details": {
                            "top_driver": "component_delta:recommended_component",
                            "numeric_reason_count": 1,
                            "drivers": [
                                {
                                    "rank": 1,
                                    "reason": "component_delta:recommended_component",
                                    "weight": 90,
                                    "value": 3,
                                    "impact_score": 270,
                                    "impact_share_pct": 72.2,
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.governance_policy_advisor",
                    "--snapshot",
                    str(snapshot),
                    "--trend",
                    str(trend),
                    "--compare-summary",
                    str(compare),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            advice = payload.get("advice", {})
            self.assertIn("compare_recommended_component_dominant", advice.get("reasons", []))
            self.assertEqual(advice.get("suggested_policy_profile"), "industrial_strict")
            self.assertEqual(advice.get("threshold_patch", {}).get("require_min_top_score_margin"), 2)
            self.assertEqual(advice.get("threshold_patch", {}).get("require_min_pairwise_net_margin"), 2)
            signal = advice.get("ranking_driver_signal", {})
            self.assertEqual(signal.get("top_driver"), "component_delta:recommended_component")


if __name__ == "__main__":
    unittest.main()
