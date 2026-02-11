import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class BenchmarkTests(unittest.TestCase):
    def _write_mock_proposal(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "proposal_id": "proposal-benchmark-1",
                    "timestamp_utc": "2026-02-11T10:00:00Z",
                    "author_type": "human",
                    "backend": "mock",
                    "model_script": "examples/openmodelica/minimal_probe.mos",
                    "change_summary": "benchmark with proposal trace",
                    "requested_actions": ["check", "benchmark"],
                    "risk_level": "low",
                }
            ),
            encoding="utf-8",
        )

    def test_benchmark_pack_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            pack = Path(d) / "pack.json"
            pack.write_text(
                json.dumps(
                    {
                        "pack_id": "mock_pack",
                        "cases": [
                            {
                                "name": "mock_pass",
                                "backend": "mock",
                                "expected": {
                                    "gate": "PASS",
                                    "failure_type": "none",
                                    "check_ok": True,
                                    "simulate_ok": True,
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            out_dir = Path(d) / "out"
            summary = Path(d) / "summary.json"
            report = Path(d) / "summary.md"
            cmd = [
                "python3",
                "-m",
                "gateforge.benchmark",
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
            self.assertEqual(payload["pack_id"], "mock_pack")
            self.assertEqual(payload["total_cases"], 1)
            self.assertEqual(payload["fail_count"], 0)

    def test_benchmark_pack_fail_on_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            pack = Path(d) / "pack.json"
            pack.write_text(
                json.dumps(
                    {
                        "pack_id": "mock_pack_fail",
                        "cases": [
                            {
                                "name": "mock_expected_fail",
                                "backend": "mock",
                                "expected": {
                                    "gate": "FAIL"
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            out_dir = Path(d) / "out"
            summary = Path(d) / "summary.json"
            cmd = [
                "python3",
                "-m",
                "gateforge.benchmark",
                "--pack",
                str(pack),
                "--out-dir",
                str(out_dir),
                "--summary-out",
                str(summary),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(payload["fail_count"], 1)

    def test_benchmark_with_proposal_propagates_proposal_id(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proposal = root / "proposal.json"
            self._write_mock_proposal(proposal)
            pack = root / "pack.json"
            pack.write_text(
                json.dumps(
                    {
                        "pack_id": "mock_pack_proposal",
                        "cases": [
                            {
                                "name": "mock_pass",
                                "backend": "mock",
                                "expected": {
                                    "gate": "PASS",
                                    "failure_type": "none",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            out_dir = root / "out"
            summary = root / "summary.json"
            cmd = [
                "python3",
                "-m",
                "gateforge.benchmark",
                "--pack",
                str(pack),
                "--proposal",
                str(proposal),
                "--out-dir",
                str(out_dir),
                "--summary-out",
                str(summary),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(payload["proposal_id"], "proposal-benchmark-1")
            self.assertEqual(payload["cases"][0]["proposal_id"], "proposal-benchmark-1")


if __name__ == "__main__":
    unittest.main()
