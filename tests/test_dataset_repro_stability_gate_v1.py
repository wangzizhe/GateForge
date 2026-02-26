import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetReproStabilityGateV1Tests(unittest.TestCase):
    def test_stability_gate_pass_when_ratio_high(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            obs = root / "obs.json"
            out = root / "summary.json"

            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "mutation_manifest_v1",
                        "mutations": [
                            {"mutation_id": "m1"},
                            {"mutation_id": "m2"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            obs.write_text(
                json.dumps(
                    {
                        "observations": [
                            {"mutation_id": "m1", "observed_failure_types": ["a", "a", "a"]},
                            {"mutation_id": "m2", "observed_failure_types": ["b", "b", "b"]},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_repro_stability_gate_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--replay-observations",
                    str(obs),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")

    def test_stability_gate_fail_when_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_repro_stability_gate_v1",
                    "--mutation-manifest",
                    str(root / "missing_manifest.json"),
                    "--replay-observations",
                    str(root / "missing_obs.json"),
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
