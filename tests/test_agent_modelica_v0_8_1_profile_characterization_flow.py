from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gateforge.agent_modelica_v0_8_1_closeout import build_v081_closeout
from gateforge.agent_modelica_v0_8_1_handoff_integrity import build_v081_handoff_integrity
from gateforge.agent_modelica_v0_8_1_profile_replay_pack import build_v081_profile_replay_pack
from gateforge.agent_modelica_v0_8_1_workflow_profile_characterization import (
    build_v081_workflow_profile_characterization,
    derive_primary_barrier_label,
)


class AgentModelicaV081ProfileCharacterizationFlowTests(unittest.TestCase):
    def _write_v080_ready(self, root: Path) -> tuple[Path, Path, Path]:
        closeout = {
            "conclusion": {
                "version_decision": "v0_8_0_workflow_proximal_substrate_ready",
                "v0_8_1_handoff_mode": "characterize_workflow_readiness_profile_on_frozen_substrate",
            }
        }
        substrate = {
            "task_count": 4,
            "workflow_proximity_audit_pass_rate_pct": 100.0,
            "task_rows": [
                {
                    "task_id": "v080_case_05",
                    "workflow_task_template_id": "recover_medium_goal",
                    "family_id": "medium_redeclare_alignment",
                    "complexity_tier": "medium",
                    "workflow_acceptance_checks": [
                        {"type": "check_model_pass"},
                        {"type": "simulate_pass"},
                        {
                            "type": "expected_goal_artifact_present",
                            "artifact_key": "pressure_note",
                            "artifact_path": "workflow_reports/v080_case_05_pressure_note.json",
                        },
                    ],
                },
                {
                    "task_id": "v080_case_06",
                    "workflow_task_template_id": "recover_medium_goal",
                    "family_id": "medium_redeclare_alignment",
                    "complexity_tier": "simple",
                    "workflow_acceptance_checks": [
                        {"type": "check_model_pass"},
                        {"type": "simulate_pass"},
                        {
                            "type": "expected_goal_artifact_present",
                            "artifact_key": "note",
                            "artifact_path": "workflow_reports/v080_case_06_note.json",
                        },
                    ],
                },
                {
                    "task_id": "v080_case_07",
                    "workflow_task_template_id": "restore_nominal_supply_chain",
                    "family_id": "component_api_alignment",
                    "complexity_tier": "complex",
                    "workflow_acceptance_checks": [
                        {"type": "check_model_pass"},
                        {"type": "simulate_pass"},
                        {
                            "type": "named_result_invariant_pass",
                            "signal_name": "workflow.physics_contract_pass",
                            "comparison_operator": "gt",
                            "threshold": 0.5,
                        },
                    ],
                },
                {
                    "task_id": "v080_case_08",
                    "workflow_task_template_id": "recover_reporting_chain",
                    "family_id": "component_api_alignment",
                    "complexity_tier": "complex",
                    "workflow_acceptance_checks": [
                        {"type": "check_model_pass"},
                        {"type": "simulate_pass"},
                        {
                            "type": "expected_goal_artifact_present",
                            "artifact_key": "workflow_report",
                            "artifact_path": "workflow_reports/v080_case_08_report.json",
                        },
                    ],
                },
            ],
        }
        pilot = {
            "execution_source": "gateforge_run_contract_live_path",
            "goal_level_resolution_criterion_frozen": True,
        }
        closeout_path = root / "v080_closeout.json"
        substrate_path = root / "v080_substrate.json"
        pilot_path = root / "v080_pilot.json"
        closeout_path.write_text(json.dumps(closeout), encoding="utf-8")
        substrate_path.write_text(json.dumps(substrate), encoding="utf-8")
        pilot_path.write_text(json.dumps(pilot), encoding="utf-8")
        return closeout_path, substrate_path, pilot_path

    def _profile(self) -> dict:
        return {
            "status": "PASS",
            "execution_source": "gateforge_run_contract_live_path",
            "workflow_resolution_rate_pct": 0.0,
            "goal_alignment_rate_pct": 50.0,
            "surface_fix_only_rate_pct": 50.0,
            "unresolved_rate_pct": 50.0,
            "case_result_table": [
                {
                    "task_id": "v080_case_05",
                    "pilot_outcome": "surface_fix_only",
                    "legacy_bucket_after_live_run": "covered_but_fragile",
                    "acceptance_check_results": {
                        "1:check_model_pass": True,
                        "2:simulate_pass": True,
                        "3:expected_goal_artifact_present": False,
                    },
                },
                {
                    "task_id": "v080_case_06",
                    "pilot_outcome": "surface_fix_only",
                    "legacy_bucket_after_live_run": "covered_but_fragile",
                    "acceptance_check_results": {
                        "1:check_model_pass": True,
                        "2:simulate_pass": True,
                        "3:expected_goal_artifact_present": False,
                    },
                },
                {
                    "task_id": "v080_case_07",
                    "pilot_outcome": "unresolved",
                    "legacy_bucket_after_live_run": "dispatch_or_policy_limited",
                    "acceptance_check_results": {
                        "1:check_model_pass": False,
                        "2:simulate_pass": False,
                        "3:named_result_invariant_pass": False,
                    },
                },
                {
                    "task_id": "v080_case_08",
                    "pilot_outcome": "unresolved",
                    "legacy_bucket_after_live_run": "topology_or_open_world_spillover",
                    "acceptance_check_results": {
                        "1:check_model_pass": False,
                        "2:simulate_pass": False,
                        "3:expected_goal_artifact_present": False,
                    },
                },
            ],
        }

    def test_barrier_derivation_matches_frozen_rules(self) -> None:
        substrate_row_artifact = {
            "workflow_acceptance_checks": [
                {"type": "check_model_pass"},
                {"type": "simulate_pass"},
                {"type": "expected_goal_artifact_present"},
            ]
        }
        artifact_case = {
            "pilot_outcome": "surface_fix_only",
            "legacy_bucket_after_live_run": "covered_but_fragile",
            "acceptance_check_results": {
                "1:check_model_pass": True,
                "2:simulate_pass": True,
                "3:expected_goal_artifact_present": False,
            },
        }
        self.assertEqual(
            derive_primary_barrier_label(artifact_case, substrate_row_artifact),
            "goal_artifact_missing_after_surface_fix",
        )
        unresolved_case = {
            "pilot_outcome": "unresolved",
            "legacy_bucket_after_live_run": "dispatch_or_policy_limited",
            "acceptance_check_results": {},
        }
        self.assertEqual(
            derive_primary_barrier_label(unresolved_case, {"workflow_acceptance_checks": []}),
            "dispatch_or_policy_limited_unresolved",
        )

    def test_replay_pack_tracks_controlled_flip_without_losing_execution_source(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v080_ready(root)
            run1 = self._profile()
            run2 = copy.deepcopy(run1)
            run2["case_result_table"][2]["pilot_outcome"] = "goal_level_resolved"
            run2["case_result_table"][2]["legacy_bucket_after_live_run"] = "covered_success"
            run2["workflow_resolution_rate_pct"] = 25.0
            run2["goal_alignment_rate_pct"] = 75.0
            run2["surface_fix_only_rate_pct"] = 50.0
            run2["unresolved_rate_pct"] = 25.0
            run3 = copy.deepcopy(run1)
            runs = [run1, run2, run3]
            with mock.patch(
                "gateforge.agent_modelica_v0_8_1_profile_replay_pack.build_v080_pilot_workflow_profile",
                side_effect=runs,
            ):
                payload = build_v081_profile_replay_pack(
                    substrate_path=str(root / "v080_substrate.json"),
                    out_dir=str(root / "replay"),
                    profile_run_count=3,
                )
            self.assertEqual(payload["execution_source"], "gateforge_run_contract_live_path")
            self.assertFalse(payload["mock_executor_path_used"])
            self.assertEqual(payload["case_outcome_flip_count"], 1)
            self.assertLess(payload["per_case_outcome_consistency_rate_pct"], 100.0)

    def test_closeout_reaches_characterized_with_explained_profile(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            closeout_path, substrate_path, pilot_path = self._write_v080_ready(root)
            build_v081_handoff_integrity(
                v080_closeout_path=str(closeout_path),
                v080_substrate_path=str(substrate_path),
                v080_pilot_profile_path=str(pilot_path),
                out_dir=str(root / "integrity"),
            )
            stable_profile = self._profile()
            with mock.patch(
                "gateforge.agent_modelica_v0_8_1_profile_replay_pack.build_v080_pilot_workflow_profile",
                side_effect=[stable_profile, copy.deepcopy(stable_profile), copy.deepcopy(stable_profile)],
            ):
                payload = build_v081_closeout(
                    handoff_integrity_path=str(root / "integrity" / "summary.json"),
                    replay_pack_path=str(root / "replay" / "summary.json"),
                    characterization_path=str(root / "characterization" / "summary.json"),
                    v080_closeout_path=str(closeout_path),
                    v080_substrate_path=str(substrate_path),
                    v080_pilot_profile_path=str(pilot_path),
                    out_dir=str(root / "closeout"),
                    profile_run_count=3,
                )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_8_1_workflow_readiness_profile_characterized",
            )
            characterization = payload["workflow_profile_characterization"]
            self.assertEqual(characterization["barrier_label_coverage_rate_pct"], 100.0)
            self.assertEqual(characterization["surface_fix_only_explained_rate_pct"], 100.0)
            self.assertEqual(characterization["unresolved_explained_rate_pct"], 100.0)
            self.assertEqual(characterization["profile_barrier_unclassified_count"], 0)

    def test_closeout_returns_handoff_invalid_when_v080_chain_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bad_closeout = {
                "conclusion": {
                    "version_decision": "v0_8_0_workflow_proximal_substrate_partial",
                    "v0_8_1_handoff_mode": "repair_workflow_proximal_substrate_gaps_first",
                }
            }
            substrate = {"task_rows": []}
            pilot = {
                "execution_source": "gateforge_run_contract_live_path",
                "goal_level_resolution_criterion_frozen": True,
            }
            (root / "closeout.json").write_text(json.dumps(bad_closeout), encoding="utf-8")
            (root / "substrate.json").write_text(json.dumps(substrate), encoding="utf-8")
            (root / "pilot.json").write_text(json.dumps(pilot), encoding="utf-8")
            payload = build_v081_closeout(
                v080_closeout_path=str(root / "closeout.json"),
                v080_substrate_path=str(root / "substrate.json"),
                v080_pilot_profile_path=str(root / "pilot.json"),
                out_dir=str(root / "closeout_out"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_8_1_handoff_profile_invalid",
            )


if __name__ == "__main__":
    unittest.main()
