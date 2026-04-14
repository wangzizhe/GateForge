from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_19_1_closeout import build_v191_closeout
from gateforge.agent_modelica_v0_19_1_handoff_integrity import build_v191_handoff_integrity
from gateforge.composite_mutation_generator_v0_19_1 import build_composite_mutation_generator_v191
from gateforge.trajectory_preview_filter_v0_19_1 import build_trajectory_preview_filter_v191
from gateforge.empirical_difficulty_filter_v0_19_1 import build_empirical_difficulty_filter_v191


def _write_v190_closeout(path: Path, *, distribution_ok: bool = True, taxonomy_frozen: bool = True) -> None:
    payload = {
        "status": "PASS" if distribution_ok and taxonomy_frozen else "FAIL",
        "conclusion": {
            "version_decision": "v0_19_0_foundation_ready",
            "taxonomy_frozen": taxonomy_frozen,
            "stop_signal_frozen": True,
            "trajectory_schema_frozen": True,
            "distribution_alignment_status": "PASS" if distribution_ok else "FAIL",
        },
        "distribution_alignment_check": {
            "threshold_passed": distribution_ok,
            "sample_count": 30 if distribution_ok else 20,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV191BenchmarkConstructionFlowTests(unittest.TestCase):
    def test_handoff_integrity_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v190 = root / "v190" / "summary.json"
            _write_v190_closeout(v190)
            payload = build_v191_handoff_integrity(v190_closeout_path=str(v190), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_fail_without_frozen_taxonomy(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v190 = root / "v190" / "summary.json"
            _write_v190_closeout(v190, taxonomy_frozen=False)
            payload = build_v191_handoff_integrity(v190_closeout_path=str(v190), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_generator_rejects_single_mutation_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            payload = build_composite_mutation_generator_v191(out_dir=str(root / "generator"))
            self.assertTrue(all(int(row["mutation_count"]) in {2, 3} for row in payload["rows"]))

    def test_preview_pass_requires_all_four_conditions(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            generator = build_composite_mutation_generator_v191(out_dir=str(root / "generator"))
            payload = build_trajectory_preview_filter_v191(
                generator_summary_path=str(root / "generator" / "summary.json"),
                out_dir=str(root / "preview"),
            )
            passing = next(row for row in payload["rows"] if row["preview_admission"])
            self.assertTrue(passing["surface_fixable_by_rule"])
            self.assertTrue(passing["post_rule_residual_present"])
            self.assertTrue(passing["post_rule_residual_non_terminal"])
            self.assertNotEqual(passing["post_rule_residual_signal_family"], "")
            self.assertEqual(generator["candidate_count"], payload["candidate_count"])

    def test_preview_fail_on_terminal_residual(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_composite_mutation_generator_v191(out_dir=str(root / "generator"))
            payload = build_trajectory_preview_filter_v191(
                generator_summary_path=str(root / "generator" / "summary.json"),
                out_dir=str(root / "preview"),
            )
            terminal_fail = next(row for row in payload["rows"] if row["preview_rejection_reason"] == "post_rule_residual_terminal")
            self.assertFalse(terminal_fail["preview_admission"])

    def test_empirical_filter_rejects_turn1_success(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_composite_mutation_generator_v191(out_dir=str(root / "generator"))
            build_trajectory_preview_filter_v191(
                generator_summary_path=str(root / "generator" / "summary.json"),
                out_dir=str(root / "preview"),
            )
            payload = build_empirical_difficulty_filter_v191(
                preview_summary_path=str(root / "preview" / "summary.json"),
                empirical_out_dir=str(root / "empirical"),
                benchmark_out_dir=str(root / "benchmark"),
            )
            row = next(row for row in payload["empirical"]["rows"] if row["difficulty_bucket"] == "too_easy")
            self.assertTrue(row["turn_1_success"])
            self.assertFalse(row["benchmark_admission"])

    def test_empirical_filter_rejects_early_exit_dead_case(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_composite_mutation_generator_v191(out_dir=str(root / "generator"))
            build_trajectory_preview_filter_v191(
                generator_summary_path=str(root / "generator" / "summary.json"),
                out_dir=str(root / "preview"),
            )
            payload = build_empirical_difficulty_filter_v191(
                preview_summary_path=str(root / "preview" / "summary.json"),
                empirical_out_dir=str(root / "empirical"),
                benchmark_out_dir=str(root / "benchmark"),
            )
            row = next(row for row in payload["empirical"]["rows"] if row["difficulty_bucket"] == "too_hard")
            self.assertFalse(row["benchmark_admission"])
            self.assertIn(row["termination_reason"], {"stalled", "cycling"})

    def test_empirical_filter_admits_target_difficulty_case(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            build_composite_mutation_generator_v191(out_dir=str(root / "generator"))
            build_trajectory_preview_filter_v191(
                generator_summary_path=str(root / "generator" / "summary.json"),
                out_dir=str(root / "preview"),
            )
            payload = build_empirical_difficulty_filter_v191(
                preview_summary_path=str(root / "preview" / "summary.json"),
                empirical_out_dir=str(root / "empirical"),
                benchmark_out_dir=str(root / "benchmark"),
            )
            row = next(row for row in payload["empirical"]["rows"] if row["difficulty_bucket"] == "target_difficulty")
            self.assertTrue(row["benchmark_admission"])
            self.assertFalse(row["turn_1_success"])
            self.assertTrue(row["eventual_success"])

    def test_benchmark_gate_fails_below_50_cases(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v190 = root / "v190" / "summary.json"
            _write_v190_closeout(v190)
            handoff = build_v191_handoff_integrity(v190_closeout_path=str(v190), out_dir=str(root / "handoff"))
            benchmark_summary = {
                "candidate_count_total": 40,
                "preview_pass_count": 40,
                "benchmark_pass_count": 40,
                "turn_1_success_rate": 0.2,
                "turn_n_success_rate": 0.6,
                "frontier_agent_id": "agent",
                "difficulty_calibration_status": "FAIL",
            }
            benchmark_path = root / "benchmark" / "summary.json"
            benchmark_path.parent.mkdir(parents=True, exist_ok=True)
            benchmark_path.write_text(json.dumps(benchmark_summary), encoding="utf-8")
            generator_path = root / "generator" / "summary.json"
            generator_path.parent.mkdir(parents=True, exist_ok=True)
            generator_path.write_text(json.dumps({"status": "PASS", "candidate_count": 40}), encoding="utf-8")
            preview_path = root / "preview" / "summary.json"
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            preview_path.write_text(json.dumps({"status": "PASS", "preview_pass_count": 40}), encoding="utf-8")
            empirical_path = root / "empirical" / "summary.json"
            empirical_path.parent.mkdir(parents=True, exist_ok=True)
            empirical_path.write_text(json.dumps({"status": "PASS", "frontier_agent_id": "agent"}), encoding="utf-8")
            payload = build_v191_closeout(
                v190_closeout_path=str(v190),
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                generator_summary_path=str(generator_path),
                preview_summary_path=str(preview_path),
                empirical_summary_path=str(empirical_path),
                benchmark_summary_path=str(benchmark_path),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_19_1_benchmark_construction_partial")

    def test_benchmark_gate_fails_outside_calibration_band(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v190 = root / "v190" / "summary.json"
            _write_v190_closeout(v190)
            generator_path = root / "generator" / "summary.json"
            generator_path.parent.mkdir(parents=True, exist_ok=True)
            generator_path.write_text(json.dumps({"status": "PASS", "candidate_count": 60}), encoding="utf-8")
            preview_path = root / "preview" / "summary.json"
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            preview_path.write_text(json.dumps({"status": "PASS", "preview_pass_count": 60}), encoding="utf-8")
            empirical_path = root / "empirical" / "summary.json"
            empirical_path.parent.mkdir(parents=True, exist_ok=True)
            empirical_path.write_text(json.dumps({"status": "PASS", "frontier_agent_id": "agent"}), encoding="utf-8")
            benchmark_path = root / "benchmark" / "summary.json"
            benchmark_path.parent.mkdir(parents=True, exist_ok=True)
            benchmark_path.write_text(json.dumps({
                "candidate_count_total": 60,
                "preview_pass_count": 60,
                "benchmark_pass_count": 55,
                "turn_1_success_rate": 0.05,
                "turn_n_success_rate": 0.90,
                "frontier_agent_id": "agent",
                "difficulty_calibration_status": "FAIL",
            }), encoding="utf-8")
            payload = build_v191_closeout(
                v190_closeout_path=str(v190),
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                generator_summary_path=str(generator_path),
                preview_summary_path=str(preview_path),
                empirical_summary_path=str(empirical_path),
                benchmark_summary_path=str(benchmark_path),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_19_1_benchmark_construction_partial")

    def test_closeout_ready_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v190 = root / "v190" / "summary.json"
            _write_v190_closeout(v190)
            payload = build_v191_closeout(
                v190_closeout_path=str(v190),
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                generator_summary_path=str(root / "generator" / "summary.json"),
                preview_summary_path=str(root / "preview" / "summary.json"),
                empirical_summary_path=str(root / "empirical" / "summary.json"),
                benchmark_summary_path=str(root / "benchmark" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_19_1_first_benchmark_batch_ready")
            self.assertEqual(payload["conclusion"]["benchmark_pass_count"], 50)

    def test_closeout_partial_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v190 = root / "v190" / "summary.json"
            _write_v190_closeout(v190)
            build_v191_closeout(
                v190_closeout_path=str(v190),
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                generator_summary_path=str(root / "generator" / "summary.json"),
                preview_summary_path=str(root / "preview" / "summary.json"),
                empirical_summary_path=str(root / "empirical" / "summary.json"),
                benchmark_summary_path=str(root / "benchmark" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            benchmark_path = root / "benchmark" / "summary.json"
            benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
            benchmark["benchmark_pass_count"] = 49
            benchmark["difficulty_calibration_status"] = "FAIL"
            benchmark_path.write_text(json.dumps(benchmark), encoding="utf-8")
            payload = build_v191_closeout(
                v190_closeout_path=str(v190),
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                generator_summary_path=str(root / "generator" / "summary.json"),
                preview_summary_path=str(root / "preview" / "summary.json"),
                empirical_summary_path=str(root / "empirical" / "summary.json"),
                benchmark_summary_path=str(root / "benchmark" / "summary.json"),
                out_dir=str(root / "closeout_partial"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_19_1_benchmark_construction_partial")


if __name__ == "__main__":
    unittest.main()
