import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetMutationModelSelectionPlanV1Tests(unittest.TestCase):
    def test_selection_plan_builds_balanced_set(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {
                                "model_id": "m_l_fluid",
                                "asset_type": "model_source",
                                "name": "FluidPlant",
                                "source_path": str(root / "fluid" / "FluidPlant.mo"),
                                "source_name": "pool_a",
                                "source_repo": "repo_a",
                                "suggested_scale": "large",
                                "complexity_score": 180,
                            },
                            {
                                "model_id": "m_l_thermal",
                                "asset_type": "model_source",
                                "name": "ThermalLoop",
                                "source_path": str(root / "thermal" / "ThermalLoop.mo"),
                                "source_name": "pool_b",
                                "source_repo": "repo_b",
                                "suggested_scale": "large",
                                "complexity_score": 175,
                            },
                            {
                                "model_id": "m_m_control",
                                "asset_type": "model_source",
                                "name": "ControlBench",
                                "source_path": str(root / "control" / "ControlBench.mo"),
                                "source_name": "pool_a",
                                "source_repo": "repo_a",
                                "suggested_scale": "medium",
                                "complexity_score": 95,
                            },
                            {
                                "model_id": "m_m_mech",
                                "asset_type": "model_source",
                                "name": "MechanicalRig",
                                "source_path": str(root / "mechanical" / "MechanicalRig.mo"),
                                "source_name": "pool_c",
                                "source_repo": "repo_c",
                                "suggested_scale": "medium",
                                "complexity_score": 90,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            plan_out = root / "plan.json"
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_model_selection_plan_v1",
                    "--executable-registry",
                    str(registry),
                    "--target-scales",
                    "large,medium",
                    "--max-models",
                    "3",
                    "--min-large-ratio-pct",
                    "30",
                    "--min-covered-families",
                    "2",
                    "--min-source-buckets",
                    "2",
                    "--plan-out",
                    str(plan_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            plan = json.loads(plan_out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertEqual(int(payload.get("selected_models", 0)), 3)
            self.assertGreaterEqual(float(payload.get("selected_large_ratio_pct", 0.0)), 30.0)
            self.assertEqual(len(plan.get("selected_model_ids", [])), 3)

    def test_selection_plan_can_require_scale_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {
                                "model_id": "m_s",
                                "asset_type": "model_source",
                                "name": "SmallModel",
                                "source_path": str(root / "small" / "SmallModel.mo"),
                                "source_name": "pool_a",
                                "source_repo": "repo_a",
                                "suggested_scale": "small",
                                "complexity_score": 20,
                            },
                            {
                                "model_id": "m_m",
                                "asset_type": "model_source",
                                "name": "MediumModel",
                                "source_path": str(root / "medium" / "MediumModel.mo"),
                                "source_name": "pool_b",
                                "source_repo": "repo_b",
                                "suggested_scale": "medium",
                                "complexity_score": 90,
                            },
                            {
                                "model_id": "m_l",
                                "asset_type": "model_source",
                                "name": "LargeModel",
                                "source_path": str(root / "large" / "LargeModel.mo"),
                                "source_name": "pool_c",
                                "source_repo": "repo_c",
                                "suggested_scale": "large",
                                "complexity_score": 180,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            plan_out = root / "plan.json"
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_model_selection_plan_v1",
                    "--executable-registry",
                    str(registry),
                    "--target-scales",
                    "small,medium,large",
                    "--max-models",
                    "3",
                    "--min-covered-scales",
                    "3",
                    "--min-covered-families",
                    "1",
                    "--min-source-buckets",
                    "1",
                    "--plan-out",
                    str(plan_out),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            plan = json.loads(plan_out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            scales = {str(x.get("suggested_scale") or "") for x in (plan.get("selected_models") or [])}
            self.assertEqual(scales, {"small", "medium", "large"})

    def test_selection_plan_fail_when_registry_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_model_selection_plan_v1",
                    "--executable-registry",
                    str(root / "missing_registry.json"),
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
