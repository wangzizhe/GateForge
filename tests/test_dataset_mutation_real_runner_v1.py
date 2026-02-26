import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationRealRunnerV1Tests(unittest.TestCase):
    def test_runner_executes_manifest_commands(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            raw_out = root / "raw.json"
            out = root / "summary.json"

            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "validated_mutation_manifest_v1",
                        "mutations": [
                            {
                                "mutation_id": "m1",
                                "repro_command": "python3 -c \"print('ok')\"",
                            },
                            {
                                "mutation_id": "m2",
                                "repro_command": "python3 -c \"import sys; sys.exit(2)\"",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_real_runner_v1",
                    "--validated-mutation-manifest",
                    str(manifest),
                    "--raw-observations-out",
                    str(raw_out),
                    "--out",
                    str(out),
                    "--max-retries",
                    "0",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            raw = json.loads(raw_out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("executed_count", 0)), 2)
            self.assertEqual(len(raw.get("observations", [])), 2)

    def test_runner_fails_when_manifest_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_real_runner_v1",
                    "--validated-mutation-manifest",
                    str(root / "missing.json"),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "FAIL")


if __name__ == "__main__":
    unittest.main()
