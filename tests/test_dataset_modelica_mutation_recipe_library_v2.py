import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetModelicaMutationRecipeLibraryV2Tests(unittest.TestCase):
    def test_recipe_library_v2_generates_operator_families(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            executable = root / "executable.json"
            balance = root / "balance.json"
            recipes = root / "recipes.json"
            out = root / "summary.json"

            executable.write_text(
                json.dumps({"status": "PASS", "executable_unique_models": 20, "executable_large_models": 6}),
                encoding="utf-8",
            )
            balance.write_text(
                json.dumps({"missing_failure_types": ["semantic_regression", "constraint_violation"]}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_mutation_recipe_library_v2",
                    "--executable-pool-summary",
                    str(executable),
                    "--mutation-portfolio-balance-summary",
                    str(balance),
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
            payload = json.loads(recipes.read_text(encoding="utf-8"))
            rows = payload.get("recipes") if isinstance(payload.get("recipes"), list) else []
            self.assertEqual(summary.get("status"), "PASS")
            self.assertGreaterEqual(int(summary.get("operator_family_count", 0)), 5)
            self.assertGreaterEqual(int(summary.get("expected_failure_type_count", 0)), 5)
            self.assertGreaterEqual(int(summary.get("high_priority_recipes", 0)), 1)
            self.assertGreaterEqual(len(rows), 10)

    def test_recipe_library_v2_fail_when_executable_summary_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_modelica_mutation_recipe_library_v2",
                    "--executable-pool-summary",
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
