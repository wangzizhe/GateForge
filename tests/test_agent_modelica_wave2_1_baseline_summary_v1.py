import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class AgentModelicaWave21BaselineSummaryV1Tests(unittest.TestCase):
    def test_summarizes_dynamic_failure_types(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = root / "taskset.json"
            challenge = root / "challenge.json"
            _write_json(taskset, {"tasks": [{"task_id": "t1", "failure_type": "solver_sensitive_simulate_failure"}]})
            _write_json(challenge, {"taskset_frozen_path": str(taskset), "total_tasks": 1, "counts_by_library": {"liba": 1}, "counts_by_failure_type": {"solver_sensitive_simulate_failure": 1}})
            _write_json(root / "baseline_summary.json", {"status": "PASS", "success_count": 1, "success_at_k_pct": 100.0})
            _write_json(root / "baseline_results.json", {"records": [{"task_id": "t1", "passed": True, "repair_audit": {"diagnostic_error_type": "numerical_instability"}}]})
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_wave2_1_baseline_summary_v1",
                    "--challenge-summary",
                    str(challenge),
                    "--baseline-summary",
                    str(root / "baseline_summary.json"),
                    "--baseline-results",
                    str(root / "baseline_results.json"),
                    "--out",
                    str(root / "summary.json"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("hardest_failure_type"), "solver_sensitive_simulate_failure")


if __name__ == "__main__":
    unittest.main()
