import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationCoverageDepthV1Tests(unittest.TestCase):
    def test_coverage_needs_review_on_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            manifest = root / "manifest.json"
            obs = root / "obs.json"
            out = root / "summary.json"

            registry.write_text(
                json.dumps({"models": [{"model_id": "mdl_large", "suggested_scale": "large"}]}),
                encoding="utf-8",
            )
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {
                                "mutation_id": "m1",
                                "target_model_id": "mdl_large",
                                "expected_failure_type": "solver_non_convergence",
                                "expected_stage": "simulate",
                            },
                            {
                                "mutation_id": "m2",
                                "target_model_id": "mdl_large",
                                "expected_failure_type": "semantic_regression",
                                "expected_stage": "simulate",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            obs.write_text(
                json.dumps(
                    {
                        "observations": [
                            {"mutation_id": "m1", "observed_failure_types": ["solver_non_convergence", "solver_non_convergence"]}
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_coverage_depth_v1",
                    "--real-model-registry",
                    str(registry),
                    "--validated-mutation-manifest",
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
            self.assertEqual(payload.get("status"), "NEEDS_REVIEW")
            self.assertGreaterEqual(int(payload.get("high_risk_gaps_count", 0)), 1)

    def test_coverage_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_coverage_depth_v1",
                    "--real-model-registry",
                    str(root / "missing_registry.json"),
                    "--validated-mutation-manifest",
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
