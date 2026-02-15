import unittest
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from gateforge.planner_output import validate_planner_output


class PlannerOutputTests(unittest.TestCase):
    def test_validate_pass_minimal(self) -> None:
        payload = {
            "intent": "demo_mock_pass",
            "proposal_id": "planner-output-1",
            "overrides": {"risk_level": "low", "change_summary": "demo"},
        }
        validate_planner_output(payload)

    def test_validate_pass_with_physical_invariants_override(self) -> None:
        payload = {
            "intent": "demo_mock_pass",
            "proposal_id": "planner-output-2",
            "overrides": {
                "risk_level": "medium",
                "change_summary": "demo invariants",
                "physical_invariants": [
                    {"type": "range", "metric": "steady_state_error", "min": 0.0, "max": 0.08}
                ],
            },
        }
        validate_planner_output(payload)

    def test_validate_fail_unknown_top_level(self) -> None:
        payload = {
            "intent": "demo_mock_pass",
            "overrides": {},
            "unsafe_key": "x",
        }
        with self.assertRaises(ValueError):
            validate_planner_output(payload, strict_top_level=True)

    def test_validate_fail_unknown_override_key(self) -> None:
        payload = {
            "intent": "demo_mock_pass",
            "overrides": {"malicious_override": True},
        }
        with self.assertRaises(ValueError):
            validate_planner_output(payload)

    def test_validate_fail_invalid_change_set(self) -> None:
        payload = {
            "intent": "demo_mock_pass",
            "overrides": {},
            "change_set_draft": {"schema_version": "0.1.0", "changes": [{"op": "bad"}]},
        }
        with self.assertRaises(ValueError):
            validate_planner_output(payload)

    def test_cli_validate_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "planner_output.json"
            p.write_text(
                json.dumps(
                    {
                        "intent": "demo_mock_pass",
                        "proposal_id": "p-1",
                        "overrides": {"change_summary": "demo"},
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, "-m", "gateforge.planner_output_validate", "--in", str(p)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

    def test_cli_validate_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "planner_output_bad.json"
            p.write_text(
                json.dumps(
                    {
                        "intent": "demo_mock_pass",
                        "overrides": {"bad_key": 1},
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, "-m", "gateforge.planner_output_validate", "--in", str(p)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("status", proc.stdout)


if __name__ == "__main__":
    unittest.main()
