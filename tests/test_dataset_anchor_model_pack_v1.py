import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetAnchorModelPackV1Tests(unittest.TestCase):
    def test_pack_selects_cases(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            manifest = root / "manifest.json"
            out = root / "summary.json"
            pack_out = root / "pack.json"
            registry.write_text(json.dumps({"models": [{"model_id": "m1", "suggested_scale": "large"}]}), encoding="utf-8")
            manifest.write_text(json.dumps({"mutations": [{"mutation_id": "c1", "target_model_id": "m1", "expected_failure_type": "solver_non_convergence", "mutation_type": "equation_flip"}]}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_anchor_model_pack_v1",
                    "--real-model-registry",
                    str(registry),
                    "--validated-mutation-manifest",
                    str(manifest),
                    "--target-cases",
                    "1",
                    "--min-large-cases",
                    "1",
                    "--out",
                    str(out),
                    "--pack-out",
                    str(pack_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("selected_cases"), 1)
            pack = json.loads(pack_out.read_text(encoding="utf-8"))
            self.assertEqual(len(pack.get("cases", [])), 1)


if __name__ == "__main__":
    unittest.main()
