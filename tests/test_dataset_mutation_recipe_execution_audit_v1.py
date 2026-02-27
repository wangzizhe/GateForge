import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationRecipeExecutionAuditV1Tests(unittest.TestCase):
    def test_recipe_execution_audit_pass_or_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            recipe = root / "recipe.json"
            matrix = root / "matrix.json"
            out = root / "summary.json"
            recipe.write_text(json.dumps({"status": "PASS", "total_recipes": 10}), encoding="utf-8")
            matrix.write_text(json.dumps({"status": "PASS", "matrix_execution_ratio_pct": 90.0, "missing_cells": []}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_recipe_execution_audit_v1",
                    "--mutation-recipe-library",
                    str(recipe),
                    "--mutation-execution-matrix-summary",
                    str(matrix),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("execution_coverage_pct", summary)

    def test_recipe_execution_audit_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_recipe_execution_audit_v1",
                    "--mutation-recipe-library",
                    str(root / "missing_recipe.json"),
                    "--mutation-execution-matrix-summary",
                    str(root / "missing_matrix.json"),
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
