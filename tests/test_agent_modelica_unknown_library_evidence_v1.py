import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class AgentModelicaUnknownLibraryEvidenceV1Tests(unittest.TestCase):
    def _run(self, root: Path, *, on_success: float, retrieval_cov: float, match_cov: float, diagnostic_cov: float) -> subprocess.CompletedProcess[str]:
        challenge = root / "challenge.json"
        off_summary = root / "off_summary.json"
        off_results = root / "off_results.json"
        on_summary = root / "on_summary.json"
        on_results = root / "on_results.json"
        retrieval_summary = root / "retrieval_summary.json"
        _write_json(challenge, {"total_tasks": 12, "provenance_completeness_pct": 100.0, "counts_by_library": {"liba": 6, "libb": 6}})
        _write_json(off_summary, {"success_at_k_pct": 75.0})
        _write_json(off_results, {"records": []})
        _write_json(on_summary, {"success_at_k_pct": on_success})
        _write_json(
            on_results,
            {
                "records": [
                    {
                        "task_id": "t1",
                        "passed": True,
                        "repair_audit": {
                            "retrieved_example_count": 1,
                            "diagnostic_error_type": "model_check_error"
                        }
                    }
                ]
            },
        )
        _write_json(
            retrieval_summary,
            {
                "retrieval_coverage_pct": retrieval_cov,
                "match_signal_coverage_pct": match_cov,
                "diagnostic_parse_coverage_pct": diagnostic_cov,
                "counts_by_library": {
                    "liba": {"match_signal_coverage_pct": 100.0, "fallback_ratio_pct": 0.0},
                    "libb": {"match_signal_coverage_pct": 0.0, "fallback_ratio_pct": 100.0}
                }
            },
        )
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "gateforge.agent_modelica_unknown_library_evidence_v1",
                "--challenge-summary",
                str(challenge),
                "--baseline-off-summary",
                str(off_summary),
                "--baseline-off-results",
                str(off_results),
                "--retrieval-on-summary",
                str(on_summary),
                "--retrieval-on-results",
                str(on_results),
                "--retrieval-summary",
                str(retrieval_summary),
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

    def test_gate_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proc = self._run(root, on_success=75.0, retrieval_cov=100.0, match_cov=100.0, diagnostic_cov=100.0)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            gate = json.loads((root / "gate.json").read_text(encoding="utf-8"))
            self.assertEqual(gate.get("status"), "PASS")
            self.assertEqual(gate.get("decision"), "promote")

    def test_gate_needs_review_when_coverage_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proc = self._run(root, on_success=75.0, retrieval_cov=25.0, match_cov=100.0, diagnostic_cov=100.0)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            gate = json.loads((root / "gate.json").read_text(encoding="utf-8"))
            self.assertEqual(gate.get("status"), "NEEDS_REVIEW")
            self.assertEqual(gate.get("primary_reason"), "retrieval_coverage_below_threshold")

    def test_gate_fail_on_regression(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proc = self._run(root, on_success=50.0, retrieval_cov=100.0, match_cov=100.0, diagnostic_cov=100.0)
            self.assertNotEqual(proc.returncode, 0)
            gate = json.loads((root / "gate.json").read_text(encoding="utf-8"))
            self.assertEqual(gate.get("status"), "FAIL")
            self.assertEqual(gate.get("primary_reason"), "retrieval_regression")


if __name__ == "__main__":
    unittest.main()

