from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_19_2_capability_profile import (
    VALID_PROFILE_CLASSES,
    _assign_profile_class,
    build_v192_capability_profile,
)
from gateforge.agent_modelica_v0_19_2_closeout import build_v192_closeout
from gateforge.agent_modelica_v0_19_2_handoff_integrity import build_v192_handoff_integrity
from gateforge.agent_modelica_v0_19_2_metric_report import build_v192_metric_report
from gateforge.agent_modelica_v0_19_2_trajectory_runner import build_v192_trajectory_runner
from gateforge.trajectory_schema_v0_19_0 import SCHEMA_VERSION_SUMMARY, SCHEMA_VERSION_TURN


def _write_v190_closeout(path: Path, *, alignment_ok: bool = True) -> None:
    payload = {
        "status": "PASS" if alignment_ok else "FAIL",
        "conclusion": {
            "version_decision": "v0_19_0_foundation_ready",
            "distribution_alignment_status": "PASS" if alignment_ok else "FAIL",
        },
        "distribution_alignment_check": {
            "threshold_passed": alignment_ok,
            "sample_count": 30 if alignment_ok else 20,
            "summary_path": "/Users/meow/Documents/GateForge/artifacts/distribution_alignment_v0_19_0/summary.json",
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v191_closeout(path: Path, *, benchmark_pass_count: int = 50, handoff_mode: str = "run_first_real_multiturn_trajectory_dataset", runnable: bool = True) -> None:
    fixture_root = path.parent / "models"
    fixture_root.mkdir(parents=True, exist_ok=True)
    admitted_cases = []
    for i in range(1, benchmark_pass_count + 1):
        case = {"candidate_id": f"cmp_{i:03d}"}
        if runnable:
            source_path = fixture_root / f"source_{i:03d}.mo"
            mutated_path = fixture_root / f"mutated_{i:03d}.mo"
            source_path.write_text(f"model Source{i:03d}\nend Source{i:03d};\n", encoding="utf-8")
            mutated_path.write_text(f"model Mutated{i:03d}\nend Mutated{i:03d};\n", encoding="utf-8")
            case.update(
                {
                    "mutated_model_path": str(mutated_path),
                    "source_model_path": str(source_path),
                    "failure_type": "model_check_error",
                    "expected_stage": "check",
                    "workflow_goal": "repair_model",
                    "planner_backend": "rule",
                    "backend": "auto",
                }
            )
        admitted_cases.append(case)
    payload = {
        "status": "PASS",
        "conclusion": {
            "version_decision": "v0_19_1_first_benchmark_batch_ready",
            "frontier_agent_id": "gateforge_frontier_agent_v0_19_1_reference",
            "benchmark_pass_count": benchmark_pass_count,
            "difficulty_calibration_status": "PASS",
            "v0_19_2_handoff_mode": handoff_mode,
        },
        "generator": {
            "rows": [
                {
                    "candidate_id": f"cmp_{i:03d}",
                    "surface_layer_taxonomy_id": "T1" if i % 2 == 0 else "T3",
                    "residual_layer_taxonomy_id": "T5" if i % 2 == 0 else "T6",
                    "optional_third_layer_taxonomy_id": "T4" if i % 5 == 0 else "",
                }
                for i in range(1, benchmark_pass_count + 1)
            ]
        },
        "benchmark": {
            "admitted_cases": admitted_cases
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV192FirstTrajectoryDatasetFlowTests(unittest.TestCase):
    def test_handoff_integrity_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v190 = root / "v190" / "summary.json"
            v191 = root / "v191" / "summary.json"
            _write_v190_closeout(v190)
            _write_v191_closeout(v191)
            payload = build_v192_handoff_integrity(v190_closeout_path=str(v190), v191_closeout_path=str(v191), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_fail_when_benchmark_too_small(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v190 = root / "v190" / "summary.json"
            v191 = root / "v191" / "summary.json"
            _write_v190_closeout(v190)
            _write_v191_closeout(v191, benchmark_pass_count=49)
            payload = build_v192_handoff_integrity(v190_closeout_path=str(v190), v191_closeout_path=str(v191), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_runner_emits_one_loop_summary_per_case(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v191 = root / "v191" / "summary.json"
            _write_v191_closeout(v191)
            payload = build_v192_trajectory_runner(
                v191_closeout_path=str(v191),
                out_dir=str(root / "trajectory"),
                executor_cmd=[sys.executable, "-m", "gateforge.agent_modelica_live_executor_mock_v0"],
            )
            self.assertEqual(payload["loop_summary_count"], payload["complete_case_count"])

    def test_runner_rejects_silent_case_drop(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v191 = root / "v191" / "summary.json"
            _write_v191_closeout(v191, benchmark_pass_count=2)
            raw = json.loads(v191.read_text(encoding="utf-8"))
            raw["generator"]["rows"] = raw["generator"]["rows"][:-1]
            v191.write_text(json.dumps(raw), encoding="utf-8")
            payload = build_v192_trajectory_runner(
                v191_closeout_path=str(v191),
                out_dir=str(root / "trajectory"),
                executor_cmd=[sys.executable, "-m", "gateforge.agent_modelica_live_executor_mock_v0"],
            )
            self.assertEqual(payload["infrastructure_failure_count"], 1)
            self.assertEqual(payload["complete_case_count"], 1)

    def test_runner_rejects_schema_version_drift(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v191 = root / "v191" / "summary.json"
            _write_v191_closeout(v191, benchmark_pass_count=1)
            payload = build_v192_trajectory_runner(
                v191_closeout_path=str(v191),
                out_dir=str(root / "trajectory"),
                executor_cmd=[sys.executable, "-m", "gateforge.agent_modelica_live_executor_mock_v0"],
            )
            self.assertEqual(payload["turn_records"][0]["schema_version"], SCHEMA_VERSION_TURN)
            self.assertEqual(payload["loop_summaries"][0]["schema_version"], SCHEMA_VERSION_SUMMARY)

    def test_metric_report_computes_recovery_rate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v191 = root / "v191" / "summary.json"
            _write_v191_closeout(v191)
            build_v192_trajectory_runner(
                v191_closeout_path=str(v191),
                out_dir=str(root / "trajectory"),
                executor_cmd=[sys.executable, "-m", "gateforge.agent_modelica_live_executor_mock_v0"],
            )
            payload = build_v192_metric_report(trajectory_summary_path=str(root / "trajectory" / "summary.json"), out_dir=str(root / "metrics"))
            self.assertIn("recovery_rate", payload)
            self.assertFalse(payload["recovery_rate_defined"])

    def test_capability_profile_assigns_thresholds(self) -> None:
        self.assertEqual(_assign_profile_class(4, 1.0, 1.0), "insufficient_data")
        self.assertEqual(_assign_profile_class(5, 0.70, 0.20), "strong_handled_pattern")
        self.assertEqual(_assign_profile_class(5, 0.50, 0.10), "mixed_but_recoverable_pattern")
        self.assertEqual(_assign_profile_class(5, 0.20, 0.00), "weak_residual_pattern")

    def test_capability_profile_rejects_unsupported_enum_value(self) -> None:
        self.assertNotIn("unsupported", VALID_PROFILE_CLASSES)

    def test_closeout_ready_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v190 = root / "v190" / "summary.json"
            v191 = root / "v191" / "summary.json"
            _write_v190_closeout(v190)
            _write_v191_closeout(v191)
            payload = build_v192_closeout(
                v190_closeout_path=str(v190),
                v191_closeout_path=str(v191),
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                trajectory_summary_path=str(root / "trajectory" / "summary.json"),
                metric_summary_path=str(root / "metrics" / "summary.json"),
                profile_summary_path=str(root / "profile" / "summary.json"),
                out_dir=str(root / "closeout"),
                executor_cmd=[sys.executable, "-m", "gateforge.agent_modelica_live_executor_mock_v0"],
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_19_2_first_real_multiturn_trajectory_dataset_ready")

    def test_closeout_partial_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v190 = root / "v190" / "summary.json"
            v191 = root / "v191" / "summary.json"
            _write_v190_closeout(v190)
            _write_v191_closeout(v191)
            build_v192_closeout(
                v190_closeout_path=str(v190),
                v191_closeout_path=str(v191),
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                trajectory_summary_path=str(root / "trajectory" / "summary.json"),
                metric_summary_path=str(root / "metrics" / "summary.json"),
                profile_summary_path=str(root / "profile" / "summary.json"),
                out_dir=str(root / "closeout"),
                executor_cmd=[sys.executable, "-m", "gateforge.agent_modelica_live_executor_mock_v0"],
            )
            trajectory_path = root / "trajectory" / "summary.json"
            trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
            trajectory["complete_case_count"] = 40
            trajectory["trajectory_case_count"] = 40
            trajectory["loop_summary_count"] = 40
            trajectory_path.write_text(json.dumps(trajectory), encoding="utf-8")
            payload = build_v192_closeout(
                v190_closeout_path=str(v190),
                v191_closeout_path=str(v191),
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                trajectory_summary_path=str(trajectory_path),
                metric_summary_path=str(root / "metrics" / "summary.json"),
                profile_summary_path=str(root / "profile" / "summary.json"),
                out_dir=str(root / "closeout_partial"),
                executor_cmd=[sys.executable, "-m", "gateforge.agent_modelica_live_executor_mock_v0"],
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_19_2_trajectory_dataset_partial")

    def test_closeout_invalid_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v190 = root / "v190" / "summary.json"
            v191 = root / "v191" / "summary.json"
            _write_v190_closeout(v190, alignment_ok=False)
            _write_v191_closeout(v191)
            payload = build_v192_closeout(
                v190_closeout_path=str(v190),
                v191_closeout_path=str(v191),
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                trajectory_summary_path=str(root / "trajectory" / "summary.json"),
                metric_summary_path=str(root / "metrics" / "summary.json"),
                profile_summary_path=str(root / "profile" / "summary.json"),
                out_dir=str(root / "closeout"),
                executor_cmd=[sys.executable, "-m", "gateforge.agent_modelica_live_executor_mock_v0"],
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_19_2_foundation_inputs_invalid")

    def test_handoff_integrity_fail_when_benchmark_has_no_runnable_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v190 = root / "v190" / "summary.json"
            v191 = root / "v191" / "summary.json"
            _write_v190_closeout(v190)
            _write_v191_closeout(v191, runnable=False)
            payload = build_v192_handoff_integrity(v190_closeout_path=str(v190), v191_closeout_path=str(v191), out_dir=str(root / "handoff"))
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_cross_case_readout_null_when_no_eligible_category_exists(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            trajectory_path = root / "trajectory" / "summary.json"
            trajectory_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "trajectories": [
                    {
                        "task_id": "t1",
                        "candidate_id": "cmp_001",
                        "taxonomy_chain": ["T1"],
                        "final_outcome": "success",
                        "termination_reason": "success",
                        "progressive_solve": False,
                    },
                    {
                        "task_id": "t2",
                        "candidate_id": "cmp_002",
                        "taxonomy_chain": ["T3"],
                        "final_outcome": "failure",
                        "termination_reason": "stalled",
                        "progressive_solve": False,
                    },
                ]
            }
            trajectory_path.write_text(json.dumps(payload), encoding="utf-8")
            profile = build_v192_capability_profile(trajectory_summary_path=str(trajectory_path), out_dir=str(root / "profile"))
            self.assertFalse(profile["cross_case_readout_sufficient_data"])
            self.assertIsNone(profile["strongest_handled_taxonomy_category_id"])
            self.assertIsNone(profile["weakest_residual_taxonomy_category_id"])


if __name__ == "__main__":
    unittest.main()
