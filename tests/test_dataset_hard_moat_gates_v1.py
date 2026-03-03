import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DatasetHardMoatGatesV1Tests(unittest.TestCase):
    def test_hard_moat_gates_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            discovery = root / "discovery.json"
            runner = root / "runner.json"
            canonical = root / "canonical.json"
            pack = root / "pack.json"
            realrun = root / "realrun.json"
            validation_v2 = root / "validation_v2.json"
            guard = root / "guard.json"
            out = root / "summary.json"

            discovery.write_text(json.dumps({"total_candidates": 50}), encoding="utf-8")
            runner.write_text(json.dumps({"accepted_count": 20, "accepted_large_count": 8}), encoding="utf-8")
            canonical.write_text(json.dumps({"status": "PASS", "canonical_net_growth_models": 6}), encoding="utf-8")
            pack.write_text(json.dumps({"total_mutations": 200}), encoding="utf-8")
            realrun.write_text(json.dumps({"executed_count": 180}), encoding="utf-8")
            validation_v2.write_text(
                json.dumps({"status": "PASS", "overall": {"type_match_rate_pct": 72.0}}),
                encoding="utf-8",
            )
            guard.write_text(
                json.dumps({"status": "PASS", "failure_type_entropy": 2.0, "distribution_drift_tvd": 0.1}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_hard_moat_gates_v1",
                    "--asset-discovery-summary",
                    str(discovery),
                    "--intake-runner-summary",
                    str(runner),
                    "--canonical-registry-summary",
                    str(canonical),
                    "--mutation-pack-summary",
                    str(pack),
                    "--mutation-real-runner-summary",
                    str(realrun),
                    "--mutation-validation-matrix-v2-summary",
                    str(validation_v2),
                    "--failure-distribution-stability-guard-summary",
                    str(guard),
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
            self.assertEqual(int(payload.get("critical_failed_gate_count", 0)), 0)

    def test_hard_moat_gates_fail_on_critical(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            discovery = root / "discovery.json"
            runner = root / "runner.json"
            canonical = root / "canonical.json"
            pack = root / "pack.json"
            realrun = root / "realrun.json"
            validation_v2 = root / "validation_v2.json"
            guard = root / "guard.json"
            out = root / "summary.json"

            discovery.write_text(json.dumps({"total_candidates": 5}), encoding="utf-8")
            runner.write_text(json.dumps({"accepted_count": 0, "accepted_large_count": 0}), encoding="utf-8")
            canonical.write_text(json.dumps({"status": "PASS", "canonical_net_growth_models": 0}), encoding="utf-8")
            pack.write_text(json.dumps({"total_mutations": 0}), encoding="utf-8")
            realrun.write_text(json.dumps({"executed_count": 0}), encoding="utf-8")
            validation_v2.write_text(json.dumps({"status": "PASS", "overall": {"type_match_rate_pct": 10.0}}), encoding="utf-8")
            guard.write_text(json.dumps({"status": "PASS", "failure_type_entropy": 1.8, "distribution_drift_tvd": 0.1}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_hard_moat_gates_v1",
                    "--asset-discovery-summary",
                    str(discovery),
                    "--intake-runner-summary",
                    str(runner),
                    "--canonical-registry-summary",
                    str(canonical),
                    "--mutation-pack-summary",
                    str(pack),
                    "--mutation-real-runner-summary",
                    str(realrun),
                    "--mutation-validation-matrix-v2-summary",
                    str(validation_v2),
                    "--failure-distribution-stability-guard-summary",
                    str(guard),
                    "--min-accepted-models",
                    "2",
                    "--min-generated-mutations",
                    "20",
                    "--min-reproducible-mutations",
                    "10",
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
            self.assertGreaterEqual(int(payload.get("critical_failed_gate_count", 0)), 1)

    def test_hard_moat_gates_accepts_optional_authenticity_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            discovery = root / "discovery.json"
            runner = root / "runner.json"
            canonical = root / "canonical.json"
            pack = root / "pack.json"
            realrun = root / "realrun.json"
            validation_v2 = root / "validation_v2.json"
            guard = root / "guard.json"
            effective_scale = root / "effective_scale.json"
            effective_depth = root / "effective_depth.json"
            source_prov = root / "source_prov.json"
            authentic_scale = root / "authentic_scale.json"
            large_auth = root / "large_auth.json"
            source_bucket = root / "source_bucket.json"
            authentic_scale_trend = root / "authentic_scale_trend.json"
            large_auth_trend = root / "large_auth_trend.json"
            source_bucket_trend = root / "source_bucket_trend.json"
            out = root / "summary.json"

            discovery.write_text(json.dumps({"total_candidates": 50}), encoding="utf-8")
            runner.write_text(json.dumps({"accepted_count": 20, "accepted_large_count": 8}), encoding="utf-8")
            canonical.write_text(json.dumps({"status": "PASS", "canonical_net_growth_models": 6}), encoding="utf-8")
            pack.write_text(json.dumps({"total_mutations": 200}), encoding="utf-8")
            realrun.write_text(json.dumps({"executed_count": 180}), encoding="utf-8")
            validation_v2.write_text(
                json.dumps({"status": "PASS", "overall": {"type_match_rate_pct": 72.0}}),
                encoding="utf-8",
            )
            guard.write_text(
                json.dumps({"status": "PASS", "failure_type_entropy": 2.0, "distribution_drift_tvd": 0.1}),
                encoding="utf-8",
            )
            effective_scale.write_text(json.dumps({"status": "PASS", "effective_reproducible_mutations": 30}), encoding="utf-8")
            effective_depth.write_text(json.dumps({"status": "PASS", "p10_effective_mutations_per_model": 1.0}), encoding="utf-8")
            source_prov.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "existing_source_path_ratio_pct": 100.0,
                        "allowed_root_ratio_pct": 100.0,
                        "registry_match_ratio_pct": 95.0,
                    }
                ),
                encoding="utf-8",
            )
            authentic_scale.write_text(json.dumps({"status": "PASS", "authentic_scale_score": 74.0}), encoding="utf-8")
            large_auth.write_text(json.dumps({"status": "PASS", "large_model_authenticity_score": 78.0}), encoding="utf-8")
            source_bucket.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "source_bucket_count": 4,
                        "max_bucket_share_pct": 42.0,
                    }
                ),
                encoding="utf-8",
            )
            authentic_scale_trend.write_text(
                json.dumps({"status": "PASS", "trend": {"alerts": []}}),
                encoding="utf-8",
            )
            large_auth_trend.write_text(
                json.dumps({"status": "PASS", "trend": {"alerts": []}}),
                encoding="utf-8",
            )
            source_bucket_trend.write_text(
                json.dumps({"status": "PASS", "trend": {"alerts": []}}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.dataset_hard_moat_gates_v1",
                    "--asset-discovery-summary",
                    str(discovery),
                    "--intake-runner-summary",
                    str(runner),
                    "--canonical-registry-summary",
                    str(canonical),
                    "--mutation-pack-summary",
                    str(pack),
                    "--mutation-real-runner-summary",
                    str(realrun),
                    "--mutation-validation-matrix-v2-summary",
                    str(validation_v2),
                    "--failure-distribution-stability-guard-summary",
                    str(guard),
                    "--mutation-effective-scale-summary",
                    str(effective_scale),
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
            self.assertIn(payload.get("status"), {"PASS", "NEEDS_REVIEW"})
            signals = payload.get("signals") if isinstance(payload.get("signals"), dict) else {}
            self.assertIn("effective_reproducible_mutations", signals)
            self.assertIn("authentic_scale_score", signals)
            self.assertIn("large_model_authenticity_score", signals)
            self.assertIn("authentic_scale_trend_status", signals)


if __name__ == "__main__":
    unittest.main()
