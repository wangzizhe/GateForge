import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelicaMutationRecipeLibraryV1Tests(unittest.TestCase):
    def test_recipe_library_generates_recipes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            saturation = root / "saturation.json"
            out = root / "summary.json"
            recipes = root / "recipes.json"
            saturation.write_text(json.dumps({"target_failure_types": ["simulate_error", "semantic_regression"]}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_mutation_recipe_library_v1",
                    "--failure-corpus-saturation-summary",
                    str(saturation),
                    "--recipes-out",
                    str(recipes),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertGreaterEqual(int(summary.get("total_recipes", 0)), 1)

    def test_recipe_library_fail_when_saturation_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_mutation_recipe_library_v1",
                    "--failure-corpus-saturation-summary",
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
