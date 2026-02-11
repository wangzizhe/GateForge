import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RunTests(unittest.TestCase):
    def _write_proposal(self, path: Path, actions: list[str]) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "proposal_id": "proposal-run-1",
                    "timestamp_utc": "2026-02-11T10:00:00Z",
                    "author_type": "human",
                    "backend": "mock",
                    "model_script": "examples/openmodelica/minimal_probe.mos",
                    "change_summary": "proposal-driven run",
                    "requested_actions": actions,
                    "risk_level": "low",
                }
            ),
            encoding="utf-8",
        )

    def _write_baseline(self, path: Path, backend: str = "mock") -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "run_id": "base-1",
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

    def test_run_proposal_check_simulate_regress_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            baseline = root / "baseline.json"
            out = root / "run_summary.json"
            candidate = root / "candidate.json"
            regression = root / "regression.json"

            self._write_proposal(proposal, ["check", "simulate", "regress"])
            self._write_baseline(baseline)

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
                    "--baseline",
                    str(baseline),
                    "--candidate-out",
                    str(candidate),
                    "--regression-out",
                    str(regression),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(summary["smoke_executed"])
            self.assertTrue(summary["regress_executed"])

    def test_run_proposal_regress_fails_on_baseline_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            baseline = root / "baseline.json"
            out = root / "run_summary.json"

            self._write_proposal(proposal, ["check", "simulate", "regress"])
            self._write_baseline(baseline, backend="openmodelica_docker")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
                    "--baseline",
                    str(baseline),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "FAIL")
            self.assertIn("regression_fail", summary["fail_reasons"])

    def test_run_proposal_auto_baseline_uses_index(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            baseline = root / "baseline.json"
            index = root / "index.json"
            out = root / "run_summary.json"

            self._write_proposal(proposal, ["check", "simulate", "regress"])
            self._write_baseline(baseline, backend="mock")
            index.write_text(
                json.dumps(
                    {
                        "version": "0.1.0",
                        "entries": [
                            {
                                "backend": "mock",
                                "model_script": "examples/openmodelica/minimal_probe.mos",
                                "baseline": str(baseline),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
                    "--baseline",
                    "auto",
                    "--baseline-index",
                    str(index),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["baseline_path"], str(baseline))

    def test_run_proposal_auto_baseline_missing_mapping_fails(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            index = root / "index.json"
            out = root / "run_summary.json"

            self._write_proposal(proposal, ["check", "simulate", "regress"])
            index.write_text(
                json.dumps({"version": "0.1.0", "entries": []}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.run",
                    "--proposal",
                    str(proposal),
                    "--baseline",
                    "auto",
                    "--baseline-index",
                    str(index),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("No baseline mapping found", proc.stderr + proc.stdout)


if __name__ == "__main__":
    unittest.main()
