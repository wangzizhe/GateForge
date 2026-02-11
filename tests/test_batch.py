import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class BatchTests(unittest.TestCase):
    def _write_mock_proposal(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "proposal_id": "proposal-batch-1",
                    "timestamp_utc": "2026-02-11T10:00:00Z",
                    "author_type": "human",
                    "backend": "mock",
                    "model_script": "examples/openmodelica/minimal_probe.mos",
                    "change_summary": "proposal-driven batch",
                    "requested_actions": ["check", "simulate"],
                    "risk_level": "low",
                }
            ),
            encoding="utf-8",
        )

    def test_batch_mock_generates_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "batch"
            summary = Path(d) / "summary.json"
            report = Path(d) / "summary.md"
            cmd = [
                "python3",
                "-m",
                "gateforge.batch",
                "--backend",
                "mock",
                "--out-dir",
                str(out_dir),
                "--summary-out",
                str(summary),
                "--report-out",
                str(report),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            self.assertTrue(summary.exists())
            self.assertTrue(report.exists())
            payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(payload["backend"], "mock")
            self.assertEqual(payload["total_runs"], 1)
            self.assertEqual(payload["fail_count"], 0)

    def test_batch_stops_on_first_failure_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "batch"
            summary = Path(d) / "summary.json"
            report = Path(d) / "summary.md"
            cmd = [
                "python3",
                "-m",
                "gateforge.batch",
                "--backend",
                "openmodelica_docker",
                "--script",
                "examples/openmodelica/failures/simulate_error.mos",
                "--script",
                "examples/openmodelica/minimal_probe.mos",
                "--out-dir",
                str(out_dir),
                "--summary-out",
                str(summary),
                "--report-out",
                str(report),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if "docker" in (proc.stderr + proc.stdout).lower() and proc.returncode != 0:
                self.skipTest("Docker/OpenModelica unavailable in this environment")
            payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(payload["total_runs"], 1)

    def test_batch_continue_on_fail_runs_all(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "batch"
            summary = Path(d) / "summary.json"
            report = Path(d) / "summary.md"
            cmd = [
                "python3",
                "-m",
                "gateforge.batch",
                "--backend",
                "openmodelica_docker",
                "--script",
                "examples/openmodelica/failures/simulate_error.mos",
                "--script",
                "examples/openmodelica/minimal_probe.mos",
                "--continue-on-fail",
                "--out-dir",
                str(out_dir),
                "--summary-out",
                str(summary),
                "--report-out",
                str(report),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if "docker" in (proc.stderr + proc.stdout).lower() and proc.returncode != 0:
                self.skipTest("Docker/OpenModelica unavailable in this environment")
            payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(payload["total_runs"], 2)

    def test_batch_pack_mock_generates_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            pack = Path(d) / "pack.json"
            pack.write_text(
                json.dumps(
                    {
                        "backend": "mock",
                        "continue_on_fail": True,
                        "scripts": ["ignored_a.mos", "ignored_b.mos"],
                    }
                ),
                encoding="utf-8",
            )
            out_dir = Path(d) / "batch"
            summary = Path(d) / "summary.json"
            report = Path(d) / "summary.md"
            cmd = [
                "python3",
                "-m",
                "gateforge.batch",
                "--pack",
                str(pack),
                "--out-dir",
                str(out_dir),
                "--summary-out",
                str(summary),
                "--report-out",
                str(report),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(payload["backend"], "mock")
            self.assertEqual(payload["total_runs"], 1)
            self.assertEqual(payload["fail_count"], 0)

    def test_batch_proposal_mock_generates_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proposal = Path(d) / "proposal.json"
            self._write_mock_proposal(proposal)
            out_dir = Path(d) / "batch"
            summary = Path(d) / "summary.json"
            report = Path(d) / "summary.md"
            cmd = [
                "python3",
                "-m",
                "gateforge.batch",
                "--proposal",
                str(proposal),
                "--out-dir",
                str(out_dir),
                "--summary-out",
                str(summary),
                "--report-out",
                str(report),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(payload["backend"], "mock")
            self.assertEqual(payload["total_runs"], 1)
            self.assertEqual(payload["fail_count"], 0)

    def test_batch_rejects_proposal_with_pack_or_script(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proposal = Path(d) / "proposal.json"
            self._write_mock_proposal(proposal)
            cmd = [
                "python3",
                "-m",
                "gateforge.batch",
                "--proposal",
                str(proposal),
                "--script",
                "examples/openmodelica/minimal_probe.mos",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("--proposal cannot be combined", proc.stderr)


if __name__ == "__main__":
    unittest.main()
