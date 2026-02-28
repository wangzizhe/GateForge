import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationCoverageMatrixV2Tests(unittest.TestCase):
    def test_matrix_pass_when_full_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            manifest = root / "manifest.json"
            observations = root / "observations.json"
            out = root / "summary.json"
            registry.write_text(json.dumps({"models": [{"model_id": "m1", "suggested_scale": "large"}]}), encoding="utf-8")
            manifest.write_text(json.dumps({"mutations": [{"mutation_id": "mut_1", "target_model_id": "m1", "expected_failure_type": "solver_non_convergence", "mutation_type": "equation_flip"}]}), encoding="utf-8")
            observations.write_text(json.dumps({"observations": [{"mutation_id": "mut_1", "observed_failure_types": ["solver_non_convergence"]}]}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_coverage_matrix_v2",
                    "--real-model-registry",
                    str(registry),
                    "--validated-mutation-manifest",
                    str(manifest),
                    "--replay-observations",
                    str(observations),
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

    def test_matrix_needs_review_on_high_risk_gap(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            manifest = root / "manifest.json"
            observations = root / "observations.json"
            out = root / "summary.json"
            registry.write_text(json.dumps({"models": [{"model_id": "m1", "suggested_scale": "large"}]}), encoding="utf-8")
            manifest.write_text(json.dumps({"mutations": [{"mutation_id": "mut_1", "target_model_id": "m1", "expected_failure_type": "solver_non_convergence", "mutation_type": "equation_flip"}]}), encoding="utf-8")
            observations.write_text(json.dumps({"observations": []}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_coverage_matrix_v2",
                    "--real-model-registry",
                    str(registry),
                    "--validated-mutation-manifest",
                    str(manifest),
                    "--replay-observations",
                    str(observations),
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
            self.assertIn("matrix_high_risk_uncovered_cells_present", payload.get("alerts", []))


if __name__ == "__main__":
    unittest.main()
