import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunPrivateModelMutationScaleBatchV1Tests(unittest.TestCase):
    def test_run_private_batch_script(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_private_model_mutation_scale_batch_v1.sh"

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model_dir = root / "private_models"
            model_dir.mkdir(parents=True, exist_ok=True)

            (model_dir / "MediumA.mo").write_text(
                "\n".join(
                    [
                        "model MediumA",
                        "  Real x;",
                    ]
                    + [f"  parameter Real k{i}={i};" for i in range(1, 90)]
                    + [
                        "equation",
                        "  der(x)=k1-k2+k3-k4+k5;",
                        "end MediumA;",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (model_dir / "LargeA.mo").write_text(
                "\n".join(
                    [
                        "model LargeA",
                        "  Real x;",
                        "  Real y;",
                    ]
                    + [f"  parameter Real p{i}={i};" for i in range(1, 180)]
                    + [
                        "equation",
                        "  der(x)=p1-p2+p3-p4+p5-p6+p7;",
                        "  der(y)=p8-p9+p10-p11+p12-p13+p14;",
                        "end LargeA;",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            out_dir = root / "batch_out"
            env = {
                **os.environ,
                "GATEFORGE_PRIVATE_MODEL_ROOTS": str(model_dir),
                "GATEFORGE_PRIVATE_BATCH_OUT_DIR": str(out_dir),
                "GATEFORGE_MIN_DISCOVERED_MODELS": "2",
                "GATEFORGE_MIN_ACCEPTED_MODELS": "2",
                "GATEFORGE_MIN_ACCEPTED_LARGE_MODELS": "1",
                "GATEFORGE_MIN_GENERATED_MUTATIONS": "20",
                "GATEFORGE_MIN_MUTATION_PER_MODEL": "6",
                "GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS": "10",
            }

            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=180,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("bundle_status"), "PASS")
            self.assertGreaterEqual(int(summary.get("accepted_models", 0)), 2)
            self.assertGreaterEqual(int(summary.get("generated_mutations", 0)), 20)
            self.assertGreaterEqual(int(summary.get("mutations_per_failure_type", 0)), 2)
            self.assertGreaterEqual(int(summary.get("executable_unique_models", 0) or 0), 2)
            self.assertGreaterEqual(int(summary.get("materialized_mutations", 0) or 0), 20)
            self.assertGreaterEqual(int(summary.get("canonical_total_models", 0) or 0), 2)
            self.assertIn(summary.get("mutation_recipe_library_v2_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_selection_plan_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_selection_balance_guard_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_selection_history_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_selection_history_trend_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_repro_depth_guard_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_repro_depth_history_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_repro_depth_history_trend_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_execution_authenticity_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_execution_authenticity_history_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_execution_authenticity_history_trend_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertGreaterEqual(float(summary.get("mutation_execution_authenticity_solver_command_ratio_pct", 0.0) or 0.0), 0.0)
            self.assertIn(summary.get("mutation_failure_signal_authenticity_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_failure_signal_authenticity_history_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_failure_signal_authenticity_history_trend_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertGreaterEqual(float(summary.get("mutation_failure_signal_authenticity_failure_signal_ratio_pct", 0.0) or 0.0), 0.0)
            self.assertIn(summary.get("large_model_executable_truth_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("large_model_executable_truth_history_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("large_model_executable_truth_history_trend_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_validation_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("validation_v2_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("failure_distribution_guard_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mismatch_triage_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("coverage_backfill_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("ingest_source_channel_planner_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("hard_moat_target_profile_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("hard_moat_target_profile_strictness_level"), {"standard", "strict", "adaptive"})
            self.assertIn(summary.get("real_model_net_growth_authenticity_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("real_model_net_growth_authenticity_history_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("real_model_net_growth_authenticity_history_trend_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("hard_moat_gates_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertGreaterEqual(float(summary.get("hard_moat_hardness_score", 0.0) or 0.0), 0.0)
            self.assertIn(summary.get("scale_history_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("scale_target_gap_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("scale_execution_board_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertGreaterEqual(int(summary.get("scale_execution_board_task_count", 0) or 0), 0)
            self.assertIn(summary.get("real_model_pool_audit_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_artifact_inventory_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("asset_locator_manifest_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("reproducible_sample_pack_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("real_model_family_coverage_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("real_model_source_diversity_guard_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("real_model_source_diversity_history_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("real_model_source_diversity_history_trend_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("joint_moat_strength_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("joint_moat_strength_history_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("joint_moat_strength_history_trend_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertGreaterEqual(float(summary.get("joint_moat_strength_score", 0.0) or 0.0), 0.0)
            self.assertIn(summary.get("mutation_signature_uniqueness_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_signature_uniqueness_history_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_signature_uniqueness_history_trend_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertGreaterEqual(float(summary.get("mutation_signature_uniqueness_unique_signature_ratio_pct", 0.0) or 0.0), 0.0)
            self.assertIn(summary.get("mutation_effective_scale_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_effective_scale_history_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("mutation_effective_scale_history_trend_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertGreaterEqual(float(summary.get("mutation_effective_scale_authenticity_multiplier", 0.0) or 0.0), 0.0)
            self.assertIn(summary.get("failure_type_balance_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("weekly_scale_milestone_checkpoint_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("scale_velocity_forecast_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("family_gap_action_plan_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("failure_balance_backfill_plan_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("action_backlog_history_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("action_backlog_trend_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("checkpoint_feedback_gate_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertIn(summary.get("scale_evidence_stamp_status"), {"PASS", "NEEDS_REVIEW", "FAIL"})
            self.assertGreaterEqual(float(summary.get("scale_evidence_stamp_score", 0.0) or 0.0), 0.0)
            self.assertIn(summary.get("validation_backend_used"), {"syntax", "omc"})

            manifest = json.loads((out_dir / "mutation_manifest.json").read_text(encoding="utf-8"))
            mutations = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
            self.assertTrue(mutations)
            sample_mut_path = Path(str(mutations[0].get("mutated_model_path") or ""))
            self.assertTrue(sample_mut_path.exists(), msg=str(sample_mut_path))
            validation = json.loads((out_dir / "mutation_validation_summary.json").read_text(encoding="utf-8"))
            self.assertIn(validation.get("status"), {"PASS", "NEEDS_REVIEW", "FAIL"})

    def test_run_private_batch_script_large_first_profile(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_private_model_mutation_scale_batch_v1.sh"

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model_dir = root / "private_models"
            model_dir.mkdir(parents=True, exist_ok=True)

            for idx in range(1, 4):
                (model_dir / f"Large{idx}.mo").write_text(
                    "\n".join(
                        [f"model Large{idx}", "  Real x;", "  Real y;"]
                        + [f"  parameter Real p{i}={i};" for i in range(1, 170)]
                        + [
                            "equation",
                            "  der(x)=p1-p2+p3-p4+p5-p6+p7;",
                            "  der(y)=p8-p9+p10-p11+p12-p13+p14;",
                            f"end Large{idx};",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
            (model_dir / "MediumA.mo").write_text(
                "\n".join(
                    ["model MediumA", "  Real x;"]
                    + [f"  parameter Real k{i}={i};" for i in range(1, 90)]
                    + [
                        "equation",
                        "  der(x)=k1-k2+k3-k4+k5;",
                        "end MediumA;",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            out_dir = root / "batch_out_large_first"
            env = {
                **os.environ,
                "GATEFORGE_PRIVATE_MODEL_ROOTS": str(model_dir),
                "GATEFORGE_PRIVATE_BATCH_OUT_DIR": str(out_dir),
                "GATEFORGE_MODEL_SCALE_PROFILE": "large_first",
                "GATEFORGE_MIN_DISCOVERED_MODELS": "4",
                "GATEFORGE_MIN_ACCEPTED_MODELS": "4",
                "GATEFORGE_MIN_ACCEPTED_LARGE_MODELS": "3",
                "GATEFORGE_MIN_ACCEPTED_LARGE_RATIO_PCT": "70",
                "GATEFORGE_MIN_GENERATED_MUTATIONS": "40",
                "GATEFORGE_MIN_MUTATION_PER_MODEL": "6",
                "GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS": "30",
            }

            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=180,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            profile = json.loads((out_dir / "profile_config.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("bundle_status"), "PASS")
            self.assertEqual(summary.get("model_scale_profile"), "large_first")
            self.assertGreaterEqual(float(summary.get("accepted_large_ratio_pct", 0.0)), 70.0)
            self.assertEqual((summary.get("result_flags") or {}).get("accepted_large_ratio_gate"), "PASS")
            self.assertEqual(profile.get("model_scale_profile"), "large_first")
            self.assertEqual(profile.get("target_scales"), ["large", "medium"])

    def test_run_private_batch_script_honors_max_mutation_models_cap(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_private_model_mutation_scale_batch_v1.sh"

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            model_dir = root / "private_models"
            model_dir.mkdir(parents=True, exist_ok=True)

            for idx in range(1, 7):
                (model_dir / f"Large{idx}.mo").write_text(
                    "\n".join(
                        [f"model Large{idx}", "  Real x;", "  Real y;"]
                        + [f"  parameter Real p{i}={i};" for i in range(1, 170)]
                        + [
                            "equation",
                            "  der(x)=p1-p2+p3-p4+p5-p6+p7;",
                            "  der(y)=p8-p9+p10-p11+p12-p13+p14;",
                            f"end Large{idx};",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )

            out_dir = root / "batch_out_cap"
            env = {
                **os.environ,
                "GATEFORGE_PRIVATE_MODEL_ROOTS": str(model_dir),
                "GATEFORGE_PRIVATE_BATCH_OUT_DIR": str(out_dir),
                "GATEFORGE_MODEL_SCALE_PROFILE": "large_first",
                "GATEFORGE_MAX_MUTATION_MODELS": "3",
                "GATEFORGE_MIN_DISCOVERED_MODELS": "6",
                "GATEFORGE_MIN_ACCEPTED_MODELS": "6",
                "GATEFORGE_MIN_ACCEPTED_LARGE_MODELS": "3",
                "GATEFORGE_MIN_ACCEPTED_LARGE_RATIO_PCT": "50",
                "GATEFORGE_MIN_GENERATED_MUTATIONS": "30",
                "GATEFORGE_MIN_MUTATION_PER_MODEL": "1",
                "GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS": "20",
            }

            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=180,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("bundle_status"), "PASS")
            self.assertEqual(int(summary.get("max_mutation_models", 0) or 0), 3)
            self.assertLessEqual(int(summary.get("selected_mutation_models", 0) or 0), 3)
            self.assertGreaterEqual(
                int(summary.get("selected_mutation_models_total", 0) or 0),
                int(summary.get("selected_mutation_models", 0) or 0),
            )


if __name__ == "__main__":
    unittest.main()
