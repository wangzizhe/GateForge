from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateforge.agent_modelica_v0_9_3_closeout import build_v093_closeout
from gateforge.agent_modelica_v0_9_3_expanded_profile_replay_pack import build_v093_expanded_profile_replay_pack
from gateforge.agent_modelica_v0_9_3_expanded_profile_replay_pack import _replay_expanded_substrate_run as replay_expanded_substrate_run
from gateforge.agent_modelica_v0_9_3_handoff_integrity import build_v093_handoff_integrity


def _substrate_row(
    task_id: str,
    source_id: str,
    current_outcome: str,
    current_barrier: str,
    priority_barrier: str,
    family: str,
    complexity: str,
    template: str,
    goal_mode: str,
) -> dict:
    return {
        "task_id": task_id,
        "base_task_id": task_id,
        "source_id": source_id,
        "family_id": family,
        "workflow_task_template_id": template,
        "complexity_tier": complexity,
        "goal_specific_check_mode": goal_mode,
        "current_pilot_outcome": current_outcome,
        "current_primary_barrier_label": current_barrier,
        "priority_barrier_label": priority_barrier,
        "expanded_substrate_admission_pass": True,
    }


def _write_v092_closeout(path: Path, *, version_decision: str = "v0_9_2_first_expanded_authentic_workflow_substrate_ready") -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "expanded_substrate_status": "ready" if version_decision.endswith("_ready") else "partial",
            "expanded_substrate_size": 19,
            "priority_barrier_coverage_table": {
                "goal_artifact_missing_after_surface_fix": 5,
                "dispatch_or_policy_limited_unresolved": 5,
                "workflow_spillover_unresolved": 5,
            },
            "v0_9_3_handoff_mode": "characterize_expanded_workflow_profile",
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v092_builder(path: Path) -> None:
    rows = [
        _substrate_row("v080_case_01", "v080_real_frozen_workflow_proximal_substrate", "goal_level_resolved", "profile_barrier_unclassified", "", "component_api_alignment", "complex", "restore_nominal_supply_chain", "invariant_only"),
        _substrate_row("v080_case_02", "v080_real_frozen_workflow_proximal_substrate", "goal_level_resolved", "profile_barrier_unclassified", "", "component_api_alignment", "complex", "recover_reporting_chain", "invariant_only"),
        _substrate_row("v080_case_03", "v080_real_frozen_workflow_proximal_substrate", "goal_level_resolved", "profile_barrier_unclassified", "", "local_interface_alignment", "medium", "restore_boundary_signal_integrity", "mixed"),
        _substrate_row("v080_case_04", "v080_real_frozen_workflow_proximal_substrate", "goal_level_resolved", "profile_barrier_unclassified", "", "local_interface_alignment", "medium", "restore_boundary_signal_integrity", "mixed"),
        _substrate_row("v080_case_05", "v080_real_frozen_workflow_proximal_substrate", "surface_fix_only", "goal_artifact_missing_after_surface_fix", "goal_artifact_missing_after_surface_fix", "medium_redeclare_alignment", "medium", "recover_medium_goal", "artifact_only"),
        _substrate_row("v080_case_06", "v080_real_frozen_workflow_proximal_substrate", "surface_fix_only", "goal_artifact_missing_after_surface_fix", "goal_artifact_missing_after_surface_fix", "medium_redeclare_alignment", "simple", "recover_medium_goal", "artifact_only"),
        _substrate_row("v080_case_07", "v080_real_frozen_workflow_proximal_substrate", "unresolved", "dispatch_or_policy_limited_unresolved", "dispatch_or_policy_limited_unresolved", "component_api_alignment", "complex", "restore_nominal_supply_chain", "invariant_only"),
        _substrate_row("v080_case_08", "v080_real_frozen_workflow_proximal_substrate", "unresolved", "workflow_spillover_unresolved", "workflow_spillover_unresolved", "component_api_alignment", "complex", "recover_reporting_chain", "invariant_only"),
        _substrate_row("v080_case_09", "v080_real_frozen_workflow_proximal_substrate", "unresolved", "dispatch_or_policy_limited_unresolved", "dispatch_or_policy_limited_unresolved", "local_interface_alignment", "medium", "restore_boundary_signal_integrity", "mixed"),
        _substrate_row("v080_case_10", "v080_real_frozen_workflow_proximal_substrate", "unresolved", "workflow_spillover_unresolved", "workflow_spillover_unresolved", "medium_redeclare_alignment", "simple", "recover_medium_goal", "artifact_only"),
    ]
    for idx in range(3):
        rows.append(_substrate_row(f"u_goal_{idx}", "l4_uplift_challenge_frozen", "candidate_only_not_yet_executed", "profile_barrier_unclassified", "goal_artifact_missing_after_surface_fix", "medium_redeclare_alignment", "medium", "recover_medium_goal", "artifact_only"))
        rows.append(_substrate_row(f"u_dispatch_{idx}", "l4_uplift_challenge_frozen", "candidate_only_not_yet_executed", "profile_barrier_unclassified", "dispatch_or_policy_limited_unresolved", "component_api_alignment", "medium", "restore_nominal_supply_chain", "invariant_only"))
        rows.append(_substrate_row(f"u_spill_{idx}", "l4_uplift_challenge_frozen", "candidate_only_not_yet_executed", "profile_barrier_unclassified", "workflow_spillover_unresolved", "medium_redeclare_alignment", "medium", "recover_reporting_chain", "invariant_only"))
    payload = {
        "expanded_substrate_candidate_count": len(rows),
        "expanded_substrate_candidate_table": rows,
        "priority_barrier_coverage_table": {
            "goal_artifact_missing_after_surface_fix": 5,
            "dispatch_or_policy_limited_unresolved": 5,
            "workflow_spillover_unresolved": 5,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV093ExpandedProfileFlowTests(unittest.TestCase):
    def test_handoff_integrity_passes_on_expected_v092_ready_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v092_closeout = root / "v092" / "closeout.json"
            v092_builder = root / "v092" / "builder.json"
            _write_v092_closeout(v092_closeout)
            _write_v092_builder(v092_builder)
            payload = build_v093_handoff_integrity(
                v092_closeout_path=str(v092_closeout),
                v092_expanded_substrate_builder_path=str(v092_builder),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_closeout_routes_to_characterized_on_stable_expanded_profile(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v092_closeout = root / "v092" / "closeout.json"
            v092_builder = root / "v092" / "builder.json"
            _write_v092_closeout(v092_closeout)
            _write_v092_builder(v092_builder)
            payload = build_v093_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                replay_pack_path=str(root / "replay" / "summary.json"),
                characterization_path=str(root / "characterization" / "summary.json"),
                v092_closeout_path=str(v092_closeout),
                v092_expanded_substrate_builder_path=str(v092_builder),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_9_3_expanded_workflow_profile_characterized")
            self.assertEqual(payload["conclusion"]["v0_9_4_handoff_mode"], "freeze_expanded_workflow_thresholds")

    def test_closeout_routes_to_partial_when_replay_pack_has_two_flips(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v092_closeout = root / "v092" / "closeout.json"
            v092_builder = root / "v092" / "builder.json"
            _write_v092_closeout(v092_closeout)
            _write_v092_builder(v092_builder)

            def _patched_replay(substrate_rows: list[dict], *, run_index: int) -> dict:
                payload = replay_expanded_substrate_run(substrate_rows, run_index=run_index)
                if run_index == 2:
                    payload["case_result_table"][0]["pilot_outcome"] = "surface_fix_only"
                    payload["case_result_table"][0]["primary_barrier_label"] = "goal_artifact_missing_after_surface_fix"
                    payload["case_result_table"][1]["pilot_outcome"] = "unresolved"
                    payload["case_result_table"][1]["primary_barrier_label"] = "dispatch_or_policy_limited_unresolved"
                return payload

            with patch("gateforge.agent_modelica_v0_9_3_expanded_profile_replay_pack._replay_expanded_substrate_run", side_effect=_patched_replay):
                payload = build_v093_closeout(
                    handoff_integrity_path=str(root / "handoff" / "summary.json"),
                    replay_pack_path=str(root / "replay" / "summary.json"),
                    characterization_path=str(root / "characterization" / "summary.json"),
                    v092_closeout_path=str(v092_closeout),
                    v092_expanded_substrate_builder_path=str(v092_builder),
                    out_dir=str(root / "closeout"),
                )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_9_3_expanded_workflow_profile_partial")
            self.assertEqual(payload["expanded_profile_replay_pack"]["unexplained_case_flip_count"], 2)

    def test_closeout_returns_invalid_when_upstream_ready_handoff_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v092_closeout = root / "v092" / "closeout.json"
            v092_builder = root / "v092" / "builder.json"
            _write_v092_closeout(v092_closeout, version_decision="v0_9_2_first_expanded_authentic_workflow_substrate_partial")
            _write_v092_builder(v092_builder)
            payload = build_v093_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                replay_pack_path=str(root / "replay" / "summary.json"),
                characterization_path=str(root / "characterization" / "summary.json"),
                v092_closeout_path=str(v092_closeout),
                v092_expanded_substrate_builder_path=str(v092_builder),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_9_3_profile_inputs_invalid")

    def test_replay_pack_exercises_flip_detection_logic(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v092_builder = root / "v092" / "builder.json"
            _write_v092_builder(v092_builder)

            def _patched_replay(substrate_rows: list[dict], *, run_index: int) -> dict:
                payload = replay_expanded_substrate_run(substrate_rows, run_index=run_index)
                if run_index == 3:
                    payload["case_result_table"][2]["pilot_outcome"] = "surface_fix_only"
                    payload["case_result_table"][2]["primary_barrier_label"] = "goal_artifact_missing_after_surface_fix"
                return payload

            with patch("gateforge.agent_modelica_v0_9_3_expanded_profile_replay_pack._replay_expanded_substrate_run", side_effect=_patched_replay):
                payload = build_v093_expanded_profile_replay_pack(
                    v092_expanded_substrate_builder_path=str(v092_builder),
                    out_dir=str(root / "replay"),
                )
            self.assertEqual(payload["unexplained_case_flip_count"], 1)


if __name__ == "__main__":
    unittest.main()
