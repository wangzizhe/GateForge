import tempfile
import unittest
from pathlib import Path

from gateforge.invariant_repair import (
    build_invariant_repair_plan,
    load_profile,
    resolve_invariant_repair_profile_path,
)


class InvariantRepairTests(unittest.TestCase):
    def test_build_plan_detects_invariant_reasons(self) -> None:
        source = {
            "proposal_id": "p1",
            "status": "FAIL",
            "policy_reasons": [
                "physical_invariant_range_violated:steady_state_error",
                "runtime_regression:1.0s>0.8s",
            ],
            "risk_level": "high",
            "checker_config": {
                "invariant_guard": {
                    "invariants": [
                        {"type": "range", "metric": "steady_state_error", "min": 0.0, "max": 0.08}
                    ]
                }
            },
        }
        plan = build_invariant_repair_plan(source)
        self.assertTrue(plan["invariant_repair_detected"])
        self.assertTrue(plan["invariant_repair_applied"])
        self.assertEqual(plan["invariant_reason_count"], 1)
        self.assertEqual(plan["context_json"]["risk_level"], "medium")
        self.assertIn("physical_invariants", plan["context_json"])
        self.assertIn("examples/openmodelica/MinimalProbe.mo", plan["planner_change_plan_allowed_files"])

    def test_build_plan_no_invariant_reason(self) -> None:
        source = {
            "proposal_id": "p2",
            "status": "FAIL",
            "policy_reasons": ["runtime_regression:1.0s>0.8s"],
            "risk_level": "low",
        }
        plan = build_invariant_repair_plan(source, allowed_files=["examples/openmodelica/MediumProbe.mo"])
        self.assertFalse(plan["invariant_repair_detected"])
        self.assertFalse(plan["invariant_repair_applied"])
        self.assertEqual(plan["invariant_reason_count"], 0)
        self.assertEqual(plan["planner_change_plan_allowed_files"], ["examples/openmodelica/MediumProbe.mo"])

    def test_profile_resolution_and_load(self) -> None:
        path = resolve_invariant_repair_profile_path("default", None)
        profile = load_profile(path)
        self.assertEqual(profile.get("name"), "default")
        self.assertIn("planner_change_plan_confidence_min", profile)

    def test_profile_path_override(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "profile.json"
            p.write_text(
                '{"name":"custom","version":"x","planner_change_plan_confidence_min":0.95,"allowed_files":["a.mo"]}',
                encoding="utf-8",
            )
            path = resolve_invariant_repair_profile_path(None, str(p))
            self.assertEqual(path, str(p))
            profile = load_profile(path)
            self.assertEqual(profile.get("name"), "custom")


if __name__ == "__main__":
    unittest.main()
