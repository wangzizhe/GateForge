import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class AgentModelicaWave2BaselineSummaryV1Tests(unittest.TestCase):
    def test_baseline_summary_groups_by_failure_type(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            challenge = root / "challenge.json"
            baseline_summary = root / "baseline_summary.json"
            baseline_results = root / "baseline_results.json"
            _write_json(
                taskset,
                {
                    "tasks": [
                        {"task_id": "t1", "failure_type": "overconstrained_system"},
                        {"task_id": "t2", "failure_type": "parameter_binding_error"},
                    ]
                },
            )
            _write_json(
                challenge,
                {
                    "taskset_frozen_path": str(taskset),
                    "total_tasks": 2,
                    "counts_by_library": {"liba": 2},
                    "counts_by_failure_type": {"overconstrained_system": 1, "parameter_binding_error": 1},
                    "counts_by_error_family": {"constraint_violation": 1, "model_check_error": 1},
                },
            )
            _write_json(baseline_summary, {"status": "PASS", "success_count": 1, "success_at_k_pct": 50.0})
            _write_json(
                baseline_results,
                {
                    "records": [
                        {"task_id": "t1", "passed": True, "repair_audit": {"diagnostic_error_type": "constraint_violation"}},
                        {"task_id": "t2", "passed": False, "error_message": "no_progress_stop", "repair_audit": {"diagnostic_error_type": "model_check_error"}},
                    ]
                },
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_wave2_baseline_summary_v1",
                    "--challenge-summary",
                    str(challenge),
                    "--baseline-summary",
                    str(baseline_summary),
                    "--baseline-results",
                    str(baseline_results),
                    "--out",
                    str(root / "out.json"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            out = json.loads((root / "out.json").read_text(encoding="utf-8"))
            self.assertEqual(out.get("success_by_failure_type", {}).get("overconstrained_system", {}).get("success_at_k_pct"), 100.0)
            self.assertEqual(out.get("hardest_failure_type"), "parameter_binding_error")


if __name__ == "__main__":
    unittest.main()
