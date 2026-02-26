import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetLargeModelBenchmarkPackV1Tests(unittest.TestCase):
    def test_pack_passes_with_good_large_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            manifest = root / "manifest.json"
            saturation = root / "saturation.json"
            push = root / "push.json"
            out = root / "summary.json"
            pack = root / "pack.json"

            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "mdl_l1", "asset_type": "model_source", "suggested_scale": "large", "complexity": {"complexity_score": 120}},
                            {"model_id": "mdl_l2", "asset_type": "model_source", "suggested_scale": "large", "complexity": {"complexity_score": 90}},
                            {"model_id": "mdl_m1", "asset_type": "model_source", "suggested_scale": "medium", "complexity": {"complexity_score": 40}},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            manifest.write_text(
                json.dumps(
                    {
                        "mutations": [
                            {"mutation_id": "m1", "target_model_id": "mdl_l1", "target_scale": "large", "expected_failure_type": "simulate_error"},
                            {"mutation_id": "m2", "target_model_id": "mdl_l1", "target_scale": "large", "expected_failure_type": "model_check_error"},
                            {"mutation_id": "m3", "target_model_id": "mdl_l2", "target_scale": "large", "expected_failure_type": "semantic_regression"},
                            {"mutation_id": "m4", "target_model_id": "mdl_l2", "target_scale": "large", "expected_failure_type": "numerical_instability"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            saturation.write_text(
                json.dumps({"target_failure_types": ["simulate_error", "model_check_error", "semantic_regression"], "total_gap_actions": 0}),
                encoding="utf-8",
            )
            push.write_text(json.dumps({"push_target_large_cases": 0}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_model_benchmark_pack_v1",
                    "--modelica-library-registry",
                    str(registry),
                    "--mutation-manifest",
                    str(manifest),
                    "--failure-corpus-saturation-summary",
                    str(saturation),
                    "--large-coverage-push-v1-summary",
                    str(push),
                    "--pack-out",
                    str(pack),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            pack_payload = json.loads(pack.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(pack_payload.get("models", [])), 2)

    def test_pack_needs_review_when_selection_is_weak(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            manifest = root / "manifest.json"
            saturation = root / "saturation.json"
            out = root / "summary.json"

            registry.write_text(json.dumps({"models": [{"model_id": "mdl_l1", "asset_type": "model_source", "suggested_scale": "large"}]}), encoding="utf-8")
            manifest.write_text(
                json.dumps({"mutations": [{"mutation_id": "m1", "target_model_id": "mdl_l1", "target_scale": "large", "expected_failure_type": "simulate_error"}]}),
                encoding="utf-8",
            )
            saturation.write_text(json.dumps({"target_failure_types": ["simulate_error", "model_check_error"]}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_model_benchmark_pack_v1",
                    "--modelica-library-registry",
                    str(registry),
                    "--mutation-manifest",
                    str(manifest),
                    "--failure-corpus-saturation-summary",
                    str(saturation),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "NEEDS_REVIEW")
            self.assertIn("selected_large_models_low", summary.get("alerts", []))

    def test_pack_fails_when_required_inputs_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_large_model_benchmark_pack_v1",
                    "--modelica-library-registry",
                    str(root / "missing_registry.json"),
                    "--mutation-manifest",
                    str(root / "missing_manifest.json"),
                    "--failure-corpus-saturation-summary",
                    str(root / "missing_saturation.json"),
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
