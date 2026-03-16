import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class AgentModelicaWave21EvidenceV1Tests(unittest.TestCase):
    def _run(self, root: Path, *, baseline: float, deterministic: float, retrieval: float) -> subprocess.CompletedProcess[str]:
        taskset = root / "taskset.json"
        challenge = root / "challenge.json"
        _write_json(taskset, {"tasks": [{"task_id": "t1", "failure_type": "event_logic_error"}]})
        _write_json(challenge, {"taskset_frozen_path": str(taskset), "total_tasks": 1, "counts_by_library": {"liba": 1}, "counts_by_failure_type": {"event_logic_error": 1}})
        _write_json(root / "baseline_summary.json", {"status": "PASS", "success_at_k_pct": baseline})
        _write_json(root / "deterministic_summary.json", {"status": "PASS", "success_at_k_pct": deterministic})
        _write_json(root / "retrieval_summary_stage.json", {"status": "PASS", "success_at_k_pct": retrieval})
        _write_json(root / "baseline_results.json", {"records": [{"task_id": "t1", "passed": baseline >= 100.0}]})
        _write_json(root / "deterministic_results.json", {"records": [{"task_id": "t1", "passed": deterministic >= 100.0}]})
        _write_json(root / "retrieval_results.json", {"records": [{"task_id": "t1", "passed": retrieval >= 100.0}]})
        _write_json(root / "retrieval_audit.json", {"retrieval_coverage_pct": 100.0, "match_signal_coverage_pct": 100.0})
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "gateforge.agent_modelica_wave2_1_evidence_v1",
                "--challenge-summary",
                str(challenge),
                "--baseline-summary",
                str(root / "baseline_summary.json"),
                "--baseline-results",
                str(root / "baseline_results.json"),
                "--deterministic-summary",
                str(root / "deterministic_summary.json"),
                "--deterministic-results",
                str(root / "deterministic_results.json"),
                "--retrieval-summary",
                str(root / "retrieval_summary_stage.json"),
                "--retrieval-results",
                str(root / "retrieval_results.json"),
                "--retrieval-audit-summary",
                str(root / "retrieval_audit.json"),
                "--out",
                str(root / "evidence.json"),
                "--gate-out",
                str(root / "gate.json"),
                "--decision-out",
                str(root / "decision.json"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_detects_baseline_saturation(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proc = self._run(root, baseline=100.0, deterministic=100.0, retrieval=100.0)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            decision = json.loads((root / "decision.json").read_text(encoding="utf-8"))
            self.assertEqual(decision.get("retrieval_uplift_status"), "baseline_already_saturated")

    def test_detects_deterministic_uplift(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proc = self._run(root, baseline=50.0, deterministic=100.0, retrieval=100.0)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            decision = json.loads((root / "decision.json").read_text(encoding="utf-8"))
            self.assertEqual(decision.get("retrieval_uplift_status"), "deterministic_uplift_observed")


if __name__ == "__main__":
    unittest.main()
