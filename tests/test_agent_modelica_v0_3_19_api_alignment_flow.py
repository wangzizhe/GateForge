from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_19_closeout import build_v0319_closeout
from gateforge.agent_modelica_v0_3_19_family_spec import build_v0319_family_spec
from gateforge.agent_modelica_v0_3_19_live_evidence import build_v0319_live_evidence
from gateforge.agent_modelica_v0_3_19_preview_admission import build_v0319_preview_admission
from gateforge.agent_modelica_v0_3_19_taskset import build_v0319_taskset


def _fixture_detail(first_error: str, second_error: str | None, *, final_pass: bool) -> dict:
    attempts = [
        {
            "round": 1,
            "reason": "model check failed",
            "log_excerpt": first_error,
            "diagnostic_ir": {
                "dominant_stage_subtype": "stage_2_structural_balance_reference",
                "error_subtype": "undefined_symbol",
            },
        }
    ]
    if second_error is not None:
        attempts.append(
            {
                "round": 2,
                "reason": "model check failed" if not final_pass else "",
                "log_excerpt": second_error,
                "diagnostic_ir": {
                    "dominant_stage_subtype": ("stage_0_none" if final_pass and "Error:" not in second_error else "stage_2_structural_balance_reference"),
                    "error_subtype": ("none" if final_pass and "Error:" not in second_error else ("compile_failure_unknown" if "compile_failure_unknown" in second_error else "undefined_symbol")),
                },
            }
        )
    return {
        "executor_status": "PASS" if final_pass else "FAILED",
        "rounds_used": 3 if final_pass and second_error and "Error:" in second_error else (2 if second_error is not None else 1),
        "resolution_path": "llm_only" if final_pass else "unresolved",
        "executor_runtime_hygiene": {"planner_event_count": 2 if final_pass and second_error and "Error:" in second_error else 1},
        "attempts": attempts,
    }


class AgentModelicaV0319ApiAlignmentFlowTests(unittest.TestCase):
    def test_family_spec_and_taskset_freeze_same_component_lane(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            spec = build_v0319_family_spec(out_dir=str(root / "spec"))
            self.assertEqual(spec.get("status"), "PASS")
            self.assertEqual(spec.get("primary_placement_kind"), "same_component_dual_mismatch")
            taskset = build_v0319_taskset(out_dir=str(root / "taskset"))
            self.assertEqual(taskset.get("status"), "PASS")
            self.assertGreaterEqual(int(taskset.get("task_count") or 0), 4)
            self.assertEqual(int(taskset.get("neighbor_component_task_count") or 0), 0)
            self.assertEqual(int(taskset.get("same_component_task_count") or 0), int(taskset.get("task_count") or 0))

    def test_preview_admission_requires_undefined_symbol_second_residual(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            taskset = {
                "tasks": [
                    {
                        "task_id": "admitted_case",
                        "complexity_tier": "simple",
                        "v0_3_19_placement_kind": "same_component_dual_mismatch",
                        "v0_3_19_mutation_shape": "class_path_surface_mismatch+parameter_surface_mismatch",
                        "source_model_text": "model A\nend A;",
                        "mutated_model_text": "model A\nend A;",
                        "v0_3_19_fixture_one_step_detail": _fixture_detail(
                            'Error: Class Sine not found in package Source.',
                            'Error: Modified element freqHz not found in class Sine.',
                            final_pass=False,
                        ),
                    },
                    {
                        "task_id": "drift_case",
                        "complexity_tier": "medium",
                        "v0_3_19_placement_kind": "same_component_dual_mismatch",
                        "v0_3_19_mutation_shape": "class_path_surface_mismatch+parameter_surface_mismatch",
                        "source_model_text": "model B\nend B;",
                        "mutated_model_text": "model B\nend B;",
                        "v0_3_19_fixture_one_step_detail": _fixture_detail(
                            'Error: Class Step not found in package Source.',
                            'compile_failure_unknown',
                            final_pass=False,
                        ),
                    },
                ]
            }
            taskset_path = root / "taskset.json"
            taskset_path.write_text(json.dumps(taskset), encoding="utf-8")
            payload = build_v0319_preview_admission(
                taskset_path=str(taskset_path),
                out_dir=str(root / "preview"),
            )
            summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
            admitted = payload.get("admitted_taskset") if isinstance(payload.get("admitted_taskset"), dict) else {}
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(summary.get("admitted_task_count"), 1)
            self.assertEqual(admitted.get("task_ids"), ["admitted_case"])
            self.assertEqual(summary.get("signature_changed_count"), 1)

    def test_live_evidence_and_closeout_detect_multiround_ready_lane(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            family_spec = build_v0319_family_spec(out_dir=str(root / "spec"))
            build_v0319_taskset(out_dir=str(root / "taskset"))
            admitted_payload = {
                "tasks": [
                    {
                        "task_id": "multiround_case",
                        "complexity_tier": "simple",
                        "v0_3_19_placement_kind": "same_component_dual_mismatch",
                        "source_model_text": "model A\nend A;",
                        "mutated_model_text": "model A\nend A;",
                        "v0_3_19_fixture_live_detail": {
                            "executor_status": "PASS",
                            "rounds_used": 3,
                            "resolution_path": "llm_only",
                            "executor_runtime_hygiene": {"planner_event_count": 2},
                            "attempts": [
                                {
                                    "round": 1,
                                    "reason": "model check failed",
                                    "log_excerpt": "Error: Class Step not found in package Source.",
                                    "diagnostic_ir": {"dominant_stage_subtype": "stage_2_structural_balance_reference", "error_subtype": "undefined_symbol"},
                                },
                                {
                                    "round": 2,
                                    "reason": "model check failed",
                                    "log_excerpt": "Error: Modified element startT not found in class Step.",
                                    "diagnostic_ir": {"dominant_stage_subtype": "stage_2_structural_balance_reference", "error_subtype": "undefined_symbol"},
                                },
                                {
                                    "round": 3,
                                    "reason": "",
                                    "log_excerpt": "",
                                    "diagnostic_ir": {"dominant_stage_subtype": "stage_0_none", "error_subtype": "none"},
                                },
                            ],
                        },
                    },
                    {
                        "task_id": "single_fix_case",
                        "complexity_tier": "medium",
                        "v0_3_19_placement_kind": "same_component_dual_mismatch",
                        "source_model_text": "model B\nend B;",
                        "mutated_model_text": "model B\nend B;",
                        "v0_3_19_fixture_live_detail": {
                            "executor_status": "PASS",
                            "rounds_used": 2,
                            "resolution_path": "llm_only",
                            "executor_runtime_hygiene": {"planner_event_count": 1},
                            "attempts": [
                                {
                                    "round": 1,
                                    "reason": "model check failed",
                                    "log_excerpt": "Error: Modified element amp not found in class Sine.",
                                    "diagnostic_ir": {"dominant_stage_subtype": "stage_2_structural_balance_reference", "error_subtype": "undefined_symbol"},
                                },
                                {
                                    "round": 2,
                                    "reason": "",
                                    "log_excerpt": "",
                                    "diagnostic_ir": {"dominant_stage_subtype": "stage_0_none", "error_subtype": "none"},
                                },
                            ],
                        },
                    },
                ]
            }
            admitted_path = root / "preview" / "admitted_taskset.json"
            admitted_path.parent.mkdir(parents=True, exist_ok=True)
            admitted_path.write_text(json.dumps(admitted_payload), encoding="utf-8")
            (root / "preview" / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "admitted_task_count": 2,
                        "signature_changed_count": 1,
                    }
                ),
                encoding="utf-8",
            )
            live = build_v0319_live_evidence(admitted_taskset_path=str(admitted_path), out_dir=str(root / "live"))
            self.assertEqual(live.get("status"), "PASS")
            self.assertEqual(live.get("multiround_success_count"), 1)
            self.assertEqual(live.get("single_fix_success_count"), 1)
            closeout = build_v0319_closeout(
                family_spec_path=str(root / "spec" / "summary.json"),
                taskset_path=str(root / "taskset" / "taskset.json"),
                preview_path=str(root / "preview" / "summary.json"),
                live_evidence_path=str(root / "live" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(closeout.get("closeout_status"), "STAGE2_API_ALIGNMENT_CLOSEOUT_READY")
            self.assertEqual((closeout.get("conclusion") or {}).get("version_decision"), "stage2_api_alignment_family_ready")


if __name__ == "__main__":
    unittest.main()
