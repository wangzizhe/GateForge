from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_11_0_closeout import build_v110_closeout
from gateforge.agent_modelica_v0_11_0_governance_pack import build_v110_governance_pack
from gateforge.agent_modelica_v0_11_0_handoff_integrity import build_v110_handoff_integrity


def _write_v103_closeout(path: Path, *, version_decision: str = "v0_10_3_first_real_origin_workflow_substrate_ready") -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "real_origin_substrate_size": 12,
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v104_closeout(path: Path, *, version_decision: str = "v0_10_4_first_real_origin_workflow_profile_characterized") -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "profile_run_count": 3,
            "profile_non_success_unclassified_count": 0,
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v106_closeout(path: Path, *, version_decision: str = "v0_10_6_first_real_origin_workflow_readiness_partial_but_interpretable") -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "final_adjudication_label": "real_origin_workflow_readiness_partial_but_interpretable",
            "partial_check_pass": True,
            "dominant_non_success_label_family": "extractive_conversion_chain_unresolved",
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v108_closeout(path: Path, *, next_primary_phase_question: str = "workflow_to_product_gap_evaluation") -> None:
    payload = {
        "conclusion": {
            "version_decision": "v0_10_phase_nearly_complete_with_explicit_caveat",
            "phase_status": "nearly_complete",
            "phase_stop_condition_status": "nearly_complete_with_caveat",
            "explicit_caveat_present": True,
            "explicit_caveat_label": "real_origin_workflow_readiness_remains_partial_rather_than_supported_even_after_real_origin_source_shift",
            "next_primary_phase_question": next_primary_phase_question,
            "do_not_continue_v0_10_same_real_origin_refinement_by_default": True,
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV110ProductGapGovernanceFlowTests(unittest.TestCase):
    def _write_upstream_chain(self, root: Path, *, next_primary_phase_question: str = "workflow_to_product_gap_evaluation") -> tuple[Path, Path, Path, Path]:
        v103 = root / "v103" / "summary.json"
        v104 = root / "v104" / "summary.json"
        v106 = root / "v106" / "summary.json"
        v108 = root / "v108" / "summary.json"
        _write_v103_closeout(v103)
        _write_v104_closeout(v104)
        _write_v106_closeout(v106)
        _write_v108_closeout(v108, next_primary_phase_question=next_primary_phase_question)
        return v103, v104, v106, v108

    def test_handoff_integrity_passes_on_expected_upstream_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v103, v104, v106, v108 = self._write_upstream_chain(root)
            payload = build_v110_handoff_integrity(
                v103_closeout_path=str(v103),
                v104_closeout_path=str(v104),
                v106_closeout_path=str(v106),
                v108_closeout_path=str(v108),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_fails_on_wrong_next_primary_question(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v103, v104, v106, v108 = self._write_upstream_chain(root, next_primary_phase_question="real_origin_workflow_readiness_evaluation")
            payload = build_v110_handoff_integrity(
                v103_closeout_path=str(v103),
                v104_closeout_path=str(v104),
                v106_closeout_path=str(v106),
                v108_closeout_path=str(v108),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_context_contract_minimum_form_validation_detects_missing_field(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v103, v104, v106, v108 = self._write_upstream_chain(root)
            payload = build_v110_governance_pack(
                v103_closeout_path=str(v103),
                v104_closeout_path=str(v104),
                v106_closeout_path=str(v106),
                v108_closeout_path=str(v108),
                context_contract={
                    "append_only_context_elements": ["workflow_goal"],
                    "recoverable_external_state_elements": ["artifact_json_paths"],
                    "non_compressible_trace_elements": ["full_omc_error_output"],
                    "forbidden_context_rewrites": [],
                    "goal_reanchoring_rule": "Restate workflow goal.",
                    "error_propagation_rule": "Keep full error output.",
                },
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["context_contract"]["context_contract_status"], "partial")
            self.assertIn("forbidden_context_rewrites", payload["context_contract"]["missing_fields"])

    def test_anti_reward_hacking_minimum_form_validation_detects_missing_field(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v103, v104, v106, v108 = self._write_upstream_chain(root)
            payload = build_v110_governance_pack(
                v103_closeout_path=str(v103),
                v104_closeout_path=str(v104),
                v106_closeout_path=str(v106),
                v108_closeout_path=str(v108),
                anti_reward_hacking_checklist={
                    "future_information_leakage_check": "x",
                    "fake_success_artifact_check": "x",
                    "evaluator_rule_exploitation_check": "x",
                    "prohibited_shortcut_retrieval_check": "x",
                },
                out_dir=str(root / "governance"),
            )
            self.assertEqual(payload["anti_reward_hacking_checklist"]["checklist_status"], "partial")
            self.assertIn(
                "prompt_injection_via_tool_or_env_output_check",
                payload["anti_reward_hacking_checklist"]["missing_fields"],
            )

    def test_baseline_anchor_passes_on_carried_v103_default_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v103, v104, v106, v108 = self._write_upstream_chain(root)
            payload = build_v110_governance_pack(
                v103_closeout_path=str(v103),
                v104_closeout_path=str(v104),
                v106_closeout_path=str(v106),
                v108_closeout_path=str(v108),
                out_dir=str(root / "governance"),
            )
            self.assertTrue(payload["baseline_anchor"]["baseline_anchor_pass"])
            self.assertEqual(
                payload["baseline_anchor"]["baseline_substrate_identity"],
                "same_v0_10_3_frozen_12_case_real_origin_substrate",
            )

    def test_closeout_routes_to_ready_on_default_governance_pack(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v103, v104, v106, v108 = self._write_upstream_chain(root)
            payload = build_v110_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v103_closeout_path=str(v103),
                v104_closeout_path=str(v104),
                v106_closeout_path=str(v106),
                v108_closeout_path=str(v108),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_0_product_gap_governance_ready")
            self.assertEqual(payload["conclusion"]["v0_11_1_handoff_mode"], "execute_first_product_gap_patch_pack")

    def test_closeout_routes_to_partial_when_one_minimum_object_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v103, v104, v106, v108 = self._write_upstream_chain(root)
            governance = build_v110_governance_pack(
                v103_closeout_path=str(v103),
                v104_closeout_path=str(v104),
                v106_closeout_path=str(v106),
                v108_closeout_path=str(v108),
                context_contract={
                    "append_only_context_elements": ["workflow_goal"],
                    "recoverable_external_state_elements": ["artifact_json_paths"],
                    "non_compressible_trace_elements": ["full_omc_error_output"],
                    "forbidden_context_rewrites": [],
                    "goal_reanchoring_rule": "Restate workflow goal.",
                    "error_propagation_rule": "Keep full error output.",
                },
                out_dir=str(root / "governance"),
            )
            self.assertEqual(governance["context_contract"]["context_contract_status"], "partial")
            payload = build_v110_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                governance_pack_path=str(root / "governance" / "summary.json"),
                v103_closeout_path=str(v103),
                v104_closeout_path=str(v104),
                v106_closeout_path=str(v106),
                v108_closeout_path=str(v108),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_0_product_gap_governance_partial")
            self.assertEqual(
                payload["conclusion"]["v0_11_1_handoff_mode"],
                "finish_product_gap_governance_minimums_first",
            )


if __name__ == "__main__":
    unittest.main()
