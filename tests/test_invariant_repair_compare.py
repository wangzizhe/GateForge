import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class InvariantRepairCompareTests(unittest.TestCase):
    def _write_source(self, path: Path, *, risk_level: str = "high") -> None:
        path.write_text(
            json.dumps(
                {
                    "proposal_id": "inv-compare-source-001",
                    "risk_level": risk_level,
                    "status": "FAIL",
                    "policy_decision": "FAIL",
                    "policy_reasons": ["physical_invariant_range_violated:steady_state_error"],
                    "checker_config": {
                        "invariant_guard": {
                            "invariants": [{"type": "range", "metric": "steady_state_error", "min": 0.0, "max": 0.08}]
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

    def _write_baseline(self, path: Path, backend: str) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "run_id": "baseline-invariant-compare-1",
                    "backend": backend,
                    "model_script": "examples/openmodelica/minimal_probe.mos",
                    "status": "success",
                    "gate": "PASS",
                    "check_ok": True,
                    "simulate_ok": True,
                    "metrics": {"runtime_seconds": 0.1},
                }
            ),
            encoding="utf-8",
        )

    def test_compare_selects_default_over_strict_for_high_risk_invariant_case(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source.json"
            baseline = root / "baseline.json"
            out = root / "summary.json"
            self._write_source(source, risk_level="high")
            self._write_baseline(baseline, backend="mock")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.invariant_repair_compare",
                    "--source",
                    str(source),
                    "--profiles",
                    "default",
                    "industrial_strict",
                    "--baseline",
                    str(baseline),
                    "--out-dir",
                    str(root / "out"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("best_profile"), "default")
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertEqual(len(payload.get("ranking", [])), 2)

    def test_compare_fails_when_all_profiles_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source.json"
            baseline = root / "baseline_bad.json"
            out = root / "summary.json"
            self._write_source(source, risk_level="high")
            self._write_baseline(baseline, backend="openmodelica_docker")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.invariant_repair_compare",
                    "--source",
                    str(source),
                    "--profiles",
                    "default",
                    "industrial_strict",
                    "--baseline",
                    str(baseline),
                    "--out-dir",
                    str(root / "out"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")
            self.assertEqual(len(payload.get("profile_results", [])), 2)


if __name__ == "__main__":
    unittest.main()
