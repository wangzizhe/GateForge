import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationExecutionAuthenticityGuardV1Tests(unittest.TestCase):
    def test_guard_needs_review_for_probe_dominance(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            raw = root / "raw.json"
            out = root / "summary.json"
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {
                                "mutation_id": "m1",
                                "repro_command": "python3 -c \"from pathlib import Path; p=Path('a.mo'); txt=p.read_text(); print('ok' if p.exists() else 'x')\"",
                            },
                            {
                                "mutation_id": "m2",
                                "repro_command": "python3 -c \"from pathlib import Path; p=Path('b.mo'); txt=p.read_text(); print('ok' if p.exists() else 'x')\"",
                            },
                            {"mutation_id": "m3", "repro_command": "omc model.mo"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            raw.write_text(
                json.dumps(
                    {
                        "observations": [
                            {"mutation_id": "m1", "execution_status": "EXECUTED", "final_return_code": 0, "attempts": [{"stderr": ""}]},
                            {"mutation_id": "m2", "execution_status": "EXECUTED", "final_return_code": 0, "attempts": [{"stderr": ""}]},
                            {"mutation_id": "m3", "execution_status": "EXECUTED", "final_return_code": 2, "attempts": [{"stderr": "solver failed"}]},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_execution_authenticity_guard_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--mutation-raw-observations",
                    str(raw),
                    "--max-probe-only-command-ratio-pct",
                    "50",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertGreater(float(payload.get("probe_only_command_ratio_pct", 0.0)), 50.0)

    def test_guard_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_execution_authenticity_guard_v1",
                    "--mutation-manifest",
                    str(root / "missing_manifest.json"),
                    "--mutation-raw-observations",
                    str(root / "missing_raw.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
