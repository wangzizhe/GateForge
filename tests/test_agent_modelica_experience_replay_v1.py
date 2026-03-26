from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_experience_replay_v1 import (
    build_rule_priority_context,
    summarize_signal_coverage,
)


class AgentModelicaExperienceReplayV1Tests(unittest.TestCase):
    def _experience_payload(self) -> dict:
        return {
            "records": [
                {
                    "task_id": "t1",
                    "failure_type": "model_check_error",
                    "repair_quality_score": 0.92,
                    "action_contributions": [
                        {
                            "rule_id": "rule_parse_error_pre_repair",
                            "action_key": "repair|parse_error_pre_repair|rule_engine_v1",
                            "rule_tier": "domain_general_rule",
                            "replay_eligible": True,
                            "failure_type": "model_check_error",
                            "contribution": "advancing",
                        },
                        {
                            "rule_id": "rule_wave2_marker_repair",
                            "action_key": "repair|wave2_marker_repair|rule_engine_v1",
                            "rule_tier": "mutation_contract_rule",
                            "replay_eligible": False,
                            "failure_type": "model_check_error",
                            "contribution": "advancing",
                        },
                    ],
                },
                {
                    "task_id": "t2",
                    "failure_type": "model_check_error",
                    "repair_quality_score": 0.81,
                    "action_contributions": [
                        {
                            "rule_id": "rule_parse_error_pre_repair",
                            "action_key": "repair|parse_error_pre_repair|rule_engine_v1",
                            "rule_tier": "domain_general_rule",
                            "replay_eligible": True,
                            "failure_type": "model_check_error",
                            "contribution": "neutral",
                        },
                        {
                            "rule_id": "rule_multi_round_layered_repair",
                            "action_key": "repair|multi_round_layered_repair|rule_engine_v1",
                            "rule_tier": "domain_general_rule",
                            "replay_eligible": True,
                            "failure_type": "model_check_error",
                            "contribution": "regressing",
                        },
                    ],
                },
                {
                    "task_id": "t3",
                    "failure_type": "simulate_error",
                    "repair_quality_score": 0.3,
                    "action_contributions": [
                        {
                            "rule_id": "rule_multi_round_layered_repair",
                            "action_key": "repair|multi_round_layered_repair|rule_engine_v1",
                            "rule_tier": "domain_general_rule",
                            "replay_eligible": True,
                            "failure_type": "simulate_error",
                            "contribution": "advancing",
                        }
                    ],
                },
            ]
        }

    def test_summarize_signal_coverage_flags_insufficient_when_below_threshold(self) -> None:
        payload = {"records": [{"action_contributions": [{"rule_id": "r1", "replay_eligible": False} for _ in range(20)]}]}
        summary = summarize_signal_coverage(payload)
        self.assertEqual(summary.get("signal_coverage_status"), "insufficient_signal_coverage")
        self.assertEqual(summary.get("replay_eligible_action_count"), 0)

    def test_summarize_signal_coverage_reports_replay_eligible_rate(self) -> None:
        summary = summarize_signal_coverage(self._experience_payload())
        self.assertEqual(summary.get("total_action_count"), 5)
        self.assertEqual(summary.get("replay_eligible_action_count"), 4)
        self.assertEqual(summary.get("signal_coverage_status"), "sufficient_signal_coverage")
        self.assertIn("rule_parse_error_pre_repair", summary.get("replay_eligible_rule_ids") or [])

    def test_build_rule_priority_context_filters_non_eligible_and_low_quality(self) -> None:
        context = build_rule_priority_context(
            self._experience_payload(),
            failure_type="model_check_error",
            min_quality_score=0.6,
        )
        order = context.get("recommended_rule_order") or []
        self.assertEqual(order[0], "rule_parse_error_pre_repair")
        self.assertNotIn("rule_wave2_marker_repair", order)
        self.assertIn("rule_multi_round_layered_repair", order)
        ranked = context.get("ranked_rules") or []
        self.assertEqual(len(ranked), 2)

    def test_build_rule_priority_context_returns_empty_for_signal_gap(self) -> None:
        context = build_rule_priority_context(
            self._experience_payload(),
            failure_type="simulate_error",
            min_quality_score=0.6,
        )
        self.assertEqual(context.get("recommended_rule_order"), [])

    def test_build_rule_priority_context_supports_repair_memory_payload_shape(self) -> None:
        payload = {"experience_records": self._experience_payload()["records"]}
        context = build_rule_priority_context(payload, failure_type="model_check_error", min_quality_score=0.6)
        self.assertEqual((context.get("recommended_rule_order") or [None])[0], "rule_parse_error_pre_repair")

    def test_cli_writes_priority_context(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            experience = root / "experience.json"
            out = root / "replay.json"
            experience.write_text(json.dumps(self._experience_payload()), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_experience_replay_v1",
                    "--experience",
                    str(experience),
                    "--failure-type",
                    "model_check_error",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual((payload.get("recommended_rule_order") or [None])[0], "rule_parse_error_pre_repair")


if __name__ == "__main__":
    unittest.main()
