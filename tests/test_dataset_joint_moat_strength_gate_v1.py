import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetJointMoatStrengthGateV1Tests(unittest.TestCase):
    def test_joint_gate_pass_or_review(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            family = root / "family.json"
            source = root / "source.json"
            repro = root / "repro.json"
            large = root / "large.json"
            growth = root / "growth.json"
            hard = root / "hard.json"
            out = root / "summary.json"
            family.write_text(json.dumps({"status": "PASS", "family_entropy": 1.8}), encoding="utf-8")
            source.write_text(json.dumps({"status": "PASS", "max_source_bucket_share_pct": 35.0}), encoding="utf-8")
            repro.write_text(json.dumps({"status": "PASS", "models_meeting_depth_ratio_pct": 85.0}), encoding="utf-8")
            large.write_text(json.dumps({"status": "PASS", "large_executable_real_rate_pct": 82.0}), encoding="utf-8")
            growth.write_text(json.dumps({"status": "PASS", "true_growth_ratio_pct": 78.0}), encoding="utf-8")
            hard.write_text(json.dumps({"status": "PASS", "moat_hardness_score": 88.0}), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_joint_moat_strength_gate_v1",
                    "--real-model-family-coverage-summary",
                    str(family),
                    "--real-model-source-diversity-summary",
                    str(source),
                    "--mutation-repro-depth-summary",
                    str(repro),
                    "--large-model-executable-truth-summary",
                    str(large),
                    "--real-model-net-growth-authenticity-summary",
                    str(growth),
                    "--hard-moat-gates-summary",
                    str(hard),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            self.assertGreaterEqual(float(payload.get("moat_strength_score", 0.0)), 0.0)

    def test_joint_gate_fail_when_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "summary.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_joint_moat_strength_gate_v1",
                    "--real-model-family-coverage-summary",
                    str(root / "missing_family.json"),
                    "--real-model-source-diversity-summary",
                    str(root / "missing_source.json"),
                    "--mutation-repro-depth-summary",
                    str(root / "missing_repro.json"),
                    "--large-model-executable-truth-summary",
                    str(root / "missing_large.json"),
                    "--real-model-net-growth-authenticity-summary",
                    str(root / "missing_growth.json"),
                    "--hard-moat-gates-summary",
                    str(root / "missing_hard.json"),
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

    def test_joint_gate_ingests_execution_authenticity_when_provided(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            family = root / "family.json"
            source = root / "source.json"
            repro = root / "repro.json"
            large = root / "large.json"
            growth = root / "growth.json"
            hard = root / "hard.json"
            auth = root / "auth.json"
            failure_auth = root / "failure_auth.json"
            effective_depth = root / "effective_depth.json"
            source_prov = root / "source_prov.json"
            authentic_scale = root / "authentic_scale.json"
            large_auth = root / "large_auth.json"
            source_bucket = root / "source_bucket.json"
            authentic_scale_trend = root / "authentic_scale_trend.json"
            large_auth_trend = root / "large_auth_trend.json"
            source_bucket_trend = root / "source_bucket_trend.json"
            out = root / "summary.json"
            family.write_text(json.dumps({"status": "PASS", "family_entropy": 1.8}), encoding="utf-8")
            source.write_text(json.dumps({"status": "PASS", "max_source_bucket_share_pct": 35.0}), encoding="utf-8")
            repro.write_text(json.dumps({"status": "PASS", "models_meeting_depth_ratio_pct": 85.0}), encoding="utf-8")
            large.write_text(json.dumps({"status": "PASS", "large_executable_real_rate_pct": 82.0}), encoding="utf-8")
            growth.write_text(json.dumps({"status": "PASS", "true_growth_ratio_pct": 78.0}), encoding="utf-8")
            hard.write_text(json.dumps({"status": "PASS", "moat_hardness_score": 88.0}), encoding="utf-8")
            auth.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "solver_command_ratio_pct": 0.0,
                        "probe_only_command_ratio_pct": 98.0,
                        "failure_signal_ratio_pct": 0.0,
                    }
                ),
                encoding="utf-8",
            )
            failure_auth.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "failure_signal_ratio_pct": 0.0,
                        "expected_failure_type_signal_coverage_pct": 0.0,
                        "observed_coverage_ratio_pct": 100.0,
                    }
                ),
                encoding="utf-8",
            )
            effective_depth.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "models_meeting_effective_depth_ratio_pct": 10.0,
                        "large_models_meeting_effective_depth_ratio_pct": 0.0,
                        "p10_effective_mutations_per_model": 0.0,
                    }
                ),
                encoding="utf-8",
            )
            source_prov.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "existing_source_path_ratio_pct": 50.0,
                        "allowed_root_ratio_pct": 40.0,
                        "registry_match_ratio_pct": 20.0,
                    }
                ),
                encoding="utf-8",
            )
            authentic_scale.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "authentic_scale_score": 12.0,
                    }
                ),
                encoding="utf-8",
            )
            large_auth.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "large_model_authenticity_score": 22.0,
                    }
                ),
                encoding="utf-8",
            )
            source_bucket.write_text(
                json.dumps(
                    {
                        "status": "NEEDS_REVIEW",
                        "source_bucket_count": 1,
                        "max_bucket_share_pct": 95.0,
                        "weighted_effective_mutations": 3.0,
                    }
                ),
                encoding="utf-8",
            )
            authentic_scale_trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"alerts": ["authentic_scale_status_worsened"]}}),
                encoding="utf-8",
            )
            large_auth_trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"alerts": ["large_model_authenticity_score_decreasing"]}}),
                encoding="utf-8",
            )
            source_bucket_trend.write_text(
                json.dumps({"status": "NEEDS_REVIEW", "trend": {"alerts": ["source_bucket_concentration_increasing"]}}),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_joint_moat_strength_gate_v1",
                    "--real-model-family-coverage-summary",
                    str(family),
                    "--real-model-source-diversity-summary",
                    str(source),
                    "--mutation-repro-depth-summary",
                    str(repro),
                    "--large-model-executable-truth-summary",
                    str(large),
                    "--real-model-net-growth-authenticity-summary",
                    str(growth),
                    "--hard-moat-gates-summary",
                    str(hard),
                    "--mutation-execution-authenticity-summary",
                    str(auth),
                    "--mutation-failure-signal-authenticity-summary",
                    str(failure_auth),
                    "--mutation-effective-depth-summary",
                    str(effective_depth),
                    "--mutation-source-provenance-summary",
                    str(source_prov),
                    "--mutation-authentic-scale-score-summary",
                    str(authentic_scale),
                    "--large-model-authenticity-gate-summary",
                    str(large_auth),
                    "--mutation-source-bucket-effective-scale-summary",
                    str(source_bucket),
                    "--mutation-authentic-scale-score-trend-summary",
                    str(authentic_scale_trend),
                    "--large-model-authenticity-trend-summary",
                    str(large_auth_trend),
                    "--mutation-source-bucket-effective-scale-trend-summary",
                    str(source_bucket_trend),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            scores = payload.get("component_scores") if isinstance(payload.get("component_scores"), dict) else {}
            self.assertIn("mutation_execution_authenticity_score", scores)
            self.assertIn("mutation_failure_signal_authenticity_score", scores)
            self.assertIn("mutation_effective_depth_score", scores)
            self.assertIn("mutation_source_provenance_score", scores)
            self.assertIn("mutation_authentic_scale_score", scores)
            self.assertIn("large_model_authenticity_score", scores)
            self.assertIn("mutation_source_bucket_effective_scale_score", scores)
            self.assertIn("mutation_execution_authenticity_not_pass", payload.get("warning_reasons") or [])
            self.assertIn("mutation_failure_signal_authenticity_not_pass", payload.get("warning_reasons") or [])
            self.assertIn("mutation_effective_depth_not_pass", payload.get("warning_reasons") or [])
            self.assertIn("mutation_source_provenance_not_pass", payload.get("warning_reasons") or [])
            self.assertIn("mutation_authentic_scale_score_not_pass", payload.get("warning_reasons") or [])
            self.assertIn("large_model_authenticity_not_pass", payload.get("warning_reasons") or [])
            self.assertIn("mutation_source_bucket_effective_scale_not_pass", payload.get("warning_reasons") or [])
            self.assertIn("mutation_authentic_scale_trend_worsening", payload.get("warning_reasons") or [])
            self.assertIn("large_model_authenticity_trend_worsening", payload.get("warning_reasons") or [])
            self.assertIn("mutation_source_bucket_effective_scale_trend_worsening", payload.get("warning_reasons") or [])


if __name__ == "__main__":
    unittest.main()
