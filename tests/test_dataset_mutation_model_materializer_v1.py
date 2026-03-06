import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge import dataset_mutation_model_materializer_v1 as materializer_v1


class MutationModelMaterializerV1Tests(unittest.TestCase):
    def test_materialize_places_declarations_before_equation_section(self) -> None:
        source = "model A1\n  Real x;\nequation\n  der(x) = -x;\nend A1;\n"
        mutated, _ = materializer_v1._materialize_text(source, failure_type="simulate_error", token="123")
        self.assertIn("Real __gf_state_123", mutated)
        self.assertIn("der(__gf_state_123)", mutated)
        self.assertLess(mutated.find("Real __gf_state_123"), mutated.find("equation"))
        self.assertEqual(mutated.count("\nequation\n"), 1)

    def test_materialize_mutants_as_real_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            models_dir = root / "models"
            models_dir.mkdir(parents=True, exist_ok=True)

            large = models_dir / "LargePlant.mo"
            large.write_text(
                "\n".join(
                    ["model LargePlant", "  Real x;", "  Real y;"]
                    + [f"  parameter Real p{i}={i};" for i in range(1, 140)]
                    + ["equation", "  der(x)=p1-p2+p3;", "  der(y)=p4-p5+p6;", "end LargePlant;"]
                )
                + "\n",
                encoding="utf-8",
            )
            medium = models_dir / "MediumPlant.mo"
            medium.write_text(
                "model MediumPlant\n  Real x;\nequation\n  der(x)=-x;\nend MediumPlant;\n",
                encoding="utf-8",
            )

            registry = root / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "m_large", "asset_type": "model_source", "source_path": str(large), "suggested_scale": "large"},
                            {"model_id": "m_medium", "asset_type": "model_source", "source_path": str(medium), "suggested_scale": "medium"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            manifest = root / "mutation_manifest.json"
            out = root / "summary.json"
            mutant_root = root / "mutants"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_model_materializer_v1",
                    "--model-registry",
                    str(registry),
                    "--target-scales",
                    "large,medium",
                    "--failure-types",
                    "simulate_error,model_check_error",
                    "--mutations-per-failure-type",
                    "2",
                    "--max-models",
                    "2",
                    "--mutant-root",
                    str(mutant_root),
                    "--manifest-out",
                    str(manifest),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("selected_models", 0)), 2)
            self.assertEqual(int(summary.get("total_mutations", 0)), 8)
            self.assertEqual(int(summary.get("materialized_mutations", 0)), 8)

            rows = payload.get("mutations") if isinstance(payload.get("mutations"), list) else []
            self.assertEqual(len(rows), 8)
            for row in rows[:4]:
                mpath = Path(str(row.get("mutated_model_path") or ""))
                self.assertTrue(mpath.exists(), msg=str(mpath))
                text = mpath.read_text(encoding="utf-8")
                self.assertIn("GateForge mutation", text)
                self.assertTrue(str(row.get("repro_command") or "").startswith("python3 -c "))

    def test_materialize_with_recipe_library_v2(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            models_dir = root / "models"
            models_dir.mkdir(parents=True, exist_ok=True)

            large = models_dir / "LargePlant.mo"
            large.write_text(
                "\n".join(
                    ["model LargePlant", "  Real x;", "  Real y;"]
                    + [f"  parameter Real p{i}={i};" for i in range(1, 140)]
                    + ["equation", "  der(x)=p1-p2+p3;", "  der(y)=p4-p5+p6;", "end LargePlant;"]
                )
                + "\n",
                encoding="utf-8",
            )

            registry = root / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "m_large", "asset_type": "model_source", "source_path": str(large), "suggested_scale": "large"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            recipe_library = root / "recipes.json"
            recipe_library.write_text(
                json.dumps(
                    {
                        "schema_version": "modelica_mutation_recipe_library_v2",
                        "recipes": [
                            {
                                "recipe_id": "r1",
                                "target_scale": "large",
                                "operator_family": "semantic_shift",
                                "operator": "inject_parameter_bias_drift",
                                "expected_failure_type": "semantic_regression",
                                "expected_stage": "simulate",
                            },
                            {
                                "recipe_id": "r2",
                                "target_scale": "large",
                                "operator_family": "model_integrity",
                                "operator": "inject_bad_connector_equation",
                                "expected_failure_type": "model_check_error",
                                "expected_stage": "check",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            manifest = root / "mutation_manifest.json"
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_model_materializer_v1",
                    "--model-registry",
                    str(registry),
                    "--target-scales",
                    "large",
                    "--recipe-library",
                    str(recipe_library),
                    "--mutations-per-recipe",
                    "1",
                    "--max-models",
                    "1",
                    "--mutant-root",
                    str(root / "mutants"),
                    "--manifest-out",
                    str(manifest),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            rows = payload.get("mutations") if isinstance(payload.get("mutations"), list) else []
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("total_mutations", 0)), 2)
            self.assertGreaterEqual(int(summary.get("operator_family_count", 0)), 2)
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(str(x.get("recipe_id") or "") for x in rows))
            self.assertTrue(all(str(x.get("operator_family") or "") for x in rows))

    def test_recipe_materialization_respects_failure_type_filter(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model = root / "Plant.mo"
            model.write_text(
                "model Plant\n  Real x;\nequation\n  der(x) = -x;\nend Plant;\n",
                encoding="utf-8",
            )
            registry = root / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "m1", "asset_type": "model_source", "source_path": str(model), "suggested_scale": "small"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            recipes = root / "recipes.json"
            recipes.write_text(
                json.dumps(
                    {
                        "schema_version": "modelica_mutation_recipe_library_v2",
                        "recipes": [
                            {
                                "recipe_id": "r_sim",
                                "target_scale": "small",
                                "operator_family": "solver_failure",
                                "operator": "inject_divide_by_zero_dynamics",
                                "expected_failure_type": "simulate_error",
                                "expected_stage": "simulate",
                            },
                            {
                                "recipe_id": "r_check",
                                "target_scale": "small",
                                "operator_family": "model_integrity",
                                "operator": "inject_undefined_symbol_equation",
                                "expected_failure_type": "model_check_error",
                                "expected_stage": "check",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest = root / "mutation_manifest.json"
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_model_materializer_v1",
                    "--model-registry",
                    str(registry),
                    "--target-scales",
                    "small",
                    "--failure-types",
                    "model_check_error",
                    "--recipe-library",
                    str(recipes),
                    "--mutations-per-recipe",
                    "1",
                    "--mutant-root",
                    str(root / "mutants"),
                    "--manifest-out",
                    str(manifest),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            rows = payload.get("mutations") if isinstance(payload.get("mutations"), list) else []
            self.assertEqual(len(rows), 1)
            self.assertEqual(str(rows[0].get("expected_failure_type") or ""), "model_check_error")
            self.assertEqual(str(rows[0].get("recipe_id") or ""), "r_check")

    def test_materialize_honors_selection_plan(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            models_dir = root / "models"
            models_dir.mkdir(parents=True, exist_ok=True)

            large = models_dir / "LargePlant.mo"
            large.write_text(
                "\n".join(
                    ["model LargePlant", "  Real x;", "  Real y;"]
                    + [f"  parameter Real p{i}={i};" for i in range(1, 140)]
                    + ["equation", "  der(x)=p1-p2+p3;", "  der(y)=p4-p5+p6;", "end LargePlant;"]
                )
                + "\n",
                encoding="utf-8",
            )
            medium = models_dir / "MediumPlant.mo"
            medium.write_text(
                "model MediumPlant\n  Real x;\nequation\n  der(x)=-x;\nend MediumPlant;\n",
                encoding="utf-8",
            )

            registry = root / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "models": [
                            {"model_id": "m_large", "asset_type": "model_source", "source_path": str(large), "suggested_scale": "large"},
                            {"model_id": "m_medium", "asset_type": "model_source", "source_path": str(medium), "suggested_scale": "medium"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            selection_plan = root / "selection_plan.json"
            selection_plan.write_text(
                json.dumps(
                    {
                        "schema_version": "mutation_model_selection_plan_v1",
                        "selected_model_ids": ["m_medium"],
                    }
                ),
                encoding="utf-8",
            )

            manifest = root / "mutation_manifest.json"
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_mutation_model_materializer_v1",
                    "--model-registry",
                    str(registry),
                    "--selection-plan",
                    str(selection_plan),
                    "--target-scales",
                    "large,medium",
                    "--failure-types",
                    "simulate_error,model_check_error",
                    "--mutations-per-failure-type",
                    "1",
                    "--max-models",
                    "2",
                    "--mutant-root",
                    str(root / "mutants"),
                    "--manifest-out",
                    str(manifest),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads(out.read_text(encoding="utf-8"))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            rows = payload.get("mutations") if isinstance(payload.get("mutations"), list) else []
            self.assertTrue(summary.get("selection_plan_requested"))
            self.assertTrue(summary.get("selection_plan_applied"))
            self.assertEqual(int(summary.get("selected_models", 0)), 1)
            self.assertTrue(rows)
            self.assertTrue(all(str(x.get("target_model_id") or "") == "m_medium" for x in rows))


if __name__ == "__main__":
    unittest.main()
