from __future__ import annotations

import tempfile
import unittest

from gateforge.agent_modelica_v0_3_15_candidate_preview import build_candidate_preview
from gateforge.agent_modelica_v0_3_15_replay_sensitive_admission_spec import build_replay_sensitive_admission_spec
from gateforge.agent_modelica_v0_3_15_replay_sensitive_candidates import (
    apply_multi_value_collapse,
    build_replay_sensitive_candidate_lane,
)


class AgentModelicaV0315CandidateLaneTests(unittest.TestCase):
    def test_apply_multi_value_collapse_updates_all_requested_parameters(self) -> None:
        model_text = "\n".join(
            [
                "model Demo",
                "  parameter Real A = 1.0;",
                "  parameter Real B = 2.0;",
                "  parameter Real C = 3.0;",
                "equation",
                "end Demo;",
            ]
        )
        mutated, audit = apply_multi_value_collapse(model_text, target_param_names=["A", "C"])
        self.assertTrue(audit.get("applied"))
        self.assertIn("parameter Real A = 0.0;", mutated)
        self.assertIn("parameter Real C = 0.0;", mutated)

    def test_build_candidate_lane_has_expected_family_mix(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            payload = build_replay_sensitive_candidate_lane(out_dir=d)
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(payload.get("runtime_candidate_count"), 7)
            self.assertEqual(payload.get("initialization_candidate_count"), 3)
            self.assertEqual(payload.get("task_count"), 10)
            self.assertEqual(payload.get("offline_exact_match_ready_count"), 10)

    def test_preview_admits_runtime_and_initialization_harder_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            candidate = build_replay_sensitive_candidate_lane(out_dir=f"{d}/candidate")
            preview = build_candidate_preview(candidate_taskset_path=f"{d}/candidate/taskset.json", out_dir=f"{d}/preview")
            summary = preview["summary"]
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(int(summary.get("admitted_for_baseline_count") or 0), 1)

    def test_admission_spec_anchor_readiness_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            payload = build_replay_sensitive_admission_spec(out_dir=d)
            self.assertEqual(payload.get("status"), "PASS")
            readiness = payload.get("anchor_readiness") or {}
            self.assertTrue(readiness.get("runtime_primary_anchor_ready"))
            self.assertTrue(readiness.get("initialization_primary_anchor_ready"))


if __name__ == "__main__":
    unittest.main()
