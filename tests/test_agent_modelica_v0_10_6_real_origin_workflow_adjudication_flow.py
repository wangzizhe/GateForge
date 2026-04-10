from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_10_6_closeout import build_v106_closeout
from gateforge.agent_modelica_v0_10_6_first_real_origin_workflow_adjudication import (
    build_v106_first_real_origin_workflow_adjudication,
)
from gateforge.agent_modelica_v0_10_6_handoff_integrity import build_v106_handoff_integrity
from gateforge.agent_modelica_v0_10_6_real_origin_adjudication_input_table import (
    build_v106_real_origin_adjudication_input_table,
)


class AgentModelicaV106RealOriginWorkflowAdjudicationFlowTests(unittest.TestCase):
    def _write_upstream_chain(self, root: Path) -> tuple[Path, Path, Path]:
        v105_closeout = {
            "conclusion": {
                "version_decision": "v0_10_5_first_real_origin_workflow_thresholds_frozen",
                "workflow_resolution_case_count": 4,
                "goal_alignment_case_count": 6,
                "surface_fix_only_case_count": 2,
                "unresolved_case_count": 6,
                "baseline_classification_under_frozen_pack": "real_origin_workflow_readiness_partial_but_interpretable",
                "anti_tautology_pass": True,
                "integer_safe_pass": True,
                "v0_10_6_handoff_mode": "adjudicate_first_real_origin_workflow_readiness_against_frozen_thresholds",
            },
            "first_real_origin_threshold_pack": {
                "execution_posture_semantics_preserved": True,
                "fallback_definition": {
                    "trigger_conditions": [
                        "baseline fails the frozen partial band",
                        "replay-floor semantics from v0.10.4 are no longer preserved",
                    ]
                },
                "supported_thresholds": {
                    "workflow_resolution_case_count": 6,
                    "goal_alignment_case_count": 8,
                },
                "partial_thresholds": {
                    "workflow_resolution_case_count": 3,
                    "goal_alignment_case_count": 5,
                },
            },
            "real_origin_threshold_input_table": {
                "real_origin_substrate_case_count": 12,
                "workflow_resolution_case_count": 4,
                "goal_alignment_case_count": 6,
                "surface_fix_only_case_count": 2,
                "unresolved_case_count": 6,
                "replay_floor_sidecar": {
                    "execution_source": "frozen_real_origin_substrate_deterministic_replay",
                },
            },
        }
        v104_closeout = {
            "conclusion": {
                "profile_non_success_unclassified_count": 0,
            },
            "real_origin_workflow_profile_characterization": {
                "non_success_label_distribution": {
                    "extractive_conversion_chain_unresolved": 3,
                    "multibody_constraint_chain_unresolved": 1,
                    "library_validation_chain_unresolved": 2,
                    "interface_fragility_after_surface_fix": 1,
                    "artifact_gap_after_surface_fix": 1,
                },
            },
        }
        v105_threshold_input = {
            "real_origin_substrate_case_count": 12,
            "workflow_resolution_case_count": 4,
            "goal_alignment_case_count": 6,
            "surface_fix_only_case_count": 2,
            "unresolved_case_count": 6,
            "replay_floor_sidecar": {
                "execution_source": "frozen_real_origin_substrate_deterministic_replay",
            },
        }
        v105_closeout_path = root / "v105_closeout.json"
        v104_closeout_path = root / "v104_closeout.json"
        v105_threshold_input_path = root / "v105_threshold_input.json"
        v105_closeout_path.write_text(json.dumps(v105_closeout), encoding="utf-8")
        v104_closeout_path.write_text(json.dumps(v104_closeout), encoding="utf-8")
        v105_threshold_input_path.write_text(json.dumps(v105_threshold_input), encoding="utf-8")
        return v105_closeout_path, v104_closeout_path, v105_threshold_input_path

    def test_handoff_integrity_passes_on_frozen_real_origin_threshold_pack(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v105_closeout_path, _, _ = self._write_upstream_chain(root)
            payload = build_v106_handoff_integrity(
                v105_closeout_path=str(v105_closeout_path),
                out_dir=str(root / "integrity"),
            )
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(
                payload["v105_closeout_summary"]["baseline_classification_under_frozen_pack"],
                "real_origin_workflow_readiness_partial_but_interpretable",
            )

    def test_real_origin_adjudication_input_table_collects_frozen_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v105_closeout_path, v104_closeout_path, v105_threshold_input_path = self._write_upstream_chain(root)
            payload = build_v106_real_origin_adjudication_input_table(
                v105_closeout_path=str(v105_closeout_path),
                v105_threshold_input_table_path=str(v105_threshold_input_path),
                v104_closeout_path=str(v104_closeout_path),
                out_dir=str(root / "inputs"),
            )
            self.assertEqual(payload["frozen_baseline_metrics"]["workflow_resolution_case_count"], 4)
            self.assertTrue(payload["execution_posture_compatibility"]["compatible"])

    def test_real_origin_workflow_adjudication_observes_partial(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v105_closeout_path, v104_closeout_path, v105_threshold_input_path = self._write_upstream_chain(root)
            build_v106_real_origin_adjudication_input_table(
                v105_closeout_path=str(v105_closeout_path),
                v105_threshold_input_table_path=str(v105_threshold_input_path),
                v104_closeout_path=str(v104_closeout_path),
                out_dir=str(root / "inputs"),
            )
            payload = build_v106_first_real_origin_workflow_adjudication(
                real_origin_adjudication_input_table_path=str(root / "inputs" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            self.assertEqual(
                payload["final_adjudication_label"],
                "real_origin_workflow_readiness_partial_but_interpretable",
            )
            self.assertEqual(payload["adjudication_route_count"], 1)

    def test_supported_path_is_executable_with_stronger_synthetic_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v105_closeout_path, v104_closeout_path, v105_threshold_input_path = self._write_upstream_chain(root)
            build_v106_real_origin_adjudication_input_table(
                v105_closeout_path=str(v105_closeout_path),
                v105_threshold_input_table_path=str(v105_threshold_input_path),
                v104_closeout_path=str(v104_closeout_path),
                out_dir=str(root / "inputs"),
            )
            input_payload = json.loads((root / "inputs" / "summary.json").read_text(encoding="utf-8"))
            input_payload["frozen_baseline_metrics"]["workflow_resolution_case_count"] = 6
            input_payload["frozen_baseline_metrics"]["goal_alignment_case_count"] = 8
            (root / "inputs" / "summary.json").write_text(json.dumps(input_payload), encoding="utf-8")
            verdict = build_v106_first_real_origin_workflow_adjudication(
                real_origin_adjudication_input_table_path=str(root / "inputs" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            self.assertEqual(verdict["final_adjudication_label"], "real_origin_workflow_readiness_supported")

    def test_fallback_path_is_executable_with_weaker_synthetic_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v105_closeout_path, v104_closeout_path, v105_threshold_input_path = self._write_upstream_chain(root)
            build_v106_real_origin_adjudication_input_table(
                v105_closeout_path=str(v105_closeout_path),
                v105_threshold_input_table_path=str(v105_threshold_input_path),
                v104_closeout_path=str(v104_closeout_path),
                out_dir=str(root / "inputs"),
            )
            input_payload = json.loads((root / "inputs" / "summary.json").read_text(encoding="utf-8"))
            input_payload["frozen_baseline_metrics"]["workflow_resolution_case_count"] = 2
            input_payload["frozen_baseline_metrics"]["goal_alignment_case_count"] = 4
            (root / "inputs" / "summary.json").write_text(json.dumps(input_payload), encoding="utf-8")
            verdict = build_v106_first_real_origin_workflow_adjudication(
                real_origin_adjudication_input_table_path=str(root / "inputs" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            self.assertEqual(verdict["final_adjudication_label"], "real_origin_workflow_readiness_fallback")

    def test_closeout_reaches_partial_but_interpretable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v105_closeout_path, v104_closeout_path, v105_threshold_input_path = self._write_upstream_chain(root)
            payload = build_v106_closeout(
                v105_closeout_path=str(v105_closeout_path),
                v105_threshold_input_table_path=str(v105_threshold_input_path),
                v104_closeout_path=str(v104_closeout_path),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                real_origin_adjudication_input_table_path=str(root / "inputs" / "summary.json"),
                first_real_origin_workflow_adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_10_6_first_real_origin_workflow_readiness_partial_but_interpretable",
            )
            self.assertEqual(
                payload["conclusion"]["v0_10_7_handoff_mode"],
                "decide_whether_one_more_bounded_real_origin_step_is_still_worth_it",
            )

    def test_closeout_returns_invalid_on_bad_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v105_closeout_path, v104_closeout_path, v105_threshold_input_path = self._write_upstream_chain(root)
            bad_v105 = json.loads(v105_closeout_path.read_text(encoding="utf-8"))
            bad_v105["conclusion"]["version_decision"] = "v0_10_5_first_real_origin_workflow_thresholds_partial"
            bad_v105["conclusion"]["v0_10_6_handoff_mode"] = "repair_threshold_pack_before_adjudication"
            bad_v105_closeout_path = root / "bad_v105_closeout.json"
            bad_v105_closeout_path.write_text(json.dumps(bad_v105), encoding="utf-8")
            payload = build_v106_closeout(
                v105_closeout_path=str(bad_v105_closeout_path),
                v105_threshold_input_table_path=str(v105_threshold_input_path),
                v104_closeout_path=str(v104_closeout_path),
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                real_origin_adjudication_input_table_path=str(root / "inputs" / "summary.json"),
                first_real_origin_workflow_adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_10_6_real_origin_adjudication_inputs_invalid",
            )


if __name__ == "__main__":
    unittest.main()
