from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_10_8_closeout import build_v108_closeout
from gateforge.agent_modelica_v0_10_8_meaning_synthesis import build_v108_meaning_synthesis
from gateforge.agent_modelica_v0_10_8_phase_ledger import build_v108_phase_ledger
from gateforge.agent_modelica_v0_10_8_stop_condition import build_v108_stop_condition


def _write_closeout(path: Path, version_decision: str, extra: dict | None = None) -> None:
    payload = {"conclusion": {"version_decision": version_decision}}
    if extra:
        payload["conclusion"].update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_standard_chain(root: Path) -> dict[str, Path]:
    paths = {
        "v100": root / "v100" / "summary.json",
        "v101": root / "v101" / "summary.json",
        "v102": root / "v102" / "summary.json",
        "v103": root / "v103" / "summary.json",
        "v104": root / "v104" / "summary.json",
        "v105": root / "v105" / "summary.json",
        "v106": root / "v106" / "summary.json",
        "v107": root / "v107" / "summary.json",
    }
    _write_closeout(
        paths["v100"],
        "v0_10_0_real_origin_candidate_governance_partial",
        {"v0_10_1_handoff_mode": "expand_real_origin_candidate_pool_before_substrate_freeze"},
    )
    _write_closeout(
        paths["v101"],
        "v0_10_1_real_origin_source_expansion_partial",
        {"v0_10_2_handoff_mode": "continue_expanding_real_origin_candidate_pool"},
    )
    _write_closeout(
        paths["v102"],
        "v0_10_2_real_origin_source_expansion_ready",
        {
            "post_expansion_mainline_real_origin_candidate_count": 12,
            "max_single_source_share_pct": 33.3,
            "v0_10_3_handoff_mode": "freeze_first_real_origin_workflow_substrate",
        },
    )
    _write_closeout(
        paths["v103"],
        "v0_10_3_first_real_origin_workflow_substrate_ready",
        {
            "real_origin_substrate_size": 12,
            "max_single_source_share_pct": 33.3,
            "real_origin_substrate_admission_status": "ready",
            "v0_10_4_handoff_mode": "characterize_first_real_origin_workflow_profile",
        },
    )
    _write_closeout(
        paths["v104"],
        "v0_10_4_first_real_origin_workflow_profile_characterized",
        {
            "profile_non_success_unclassified_count": 0,
            "v0_10_5_handoff_mode": "freeze_first_real_origin_workflow_thresholds",
        },
    )
    _write_closeout(
        paths["v105"],
        "v0_10_5_first_real_origin_workflow_thresholds_frozen",
        {
            "anti_tautology_pass": True,
            "integer_safe_pass": True,
            "v0_10_6_handoff_mode": "adjudicate_first_real_origin_workflow_readiness_against_frozen_thresholds",
        },
    )
    _write_closeout(
        paths["v106"],
        "v0_10_6_first_real_origin_workflow_readiness_partial_but_interpretable",
        {
            "final_adjudication_label": "real_origin_workflow_readiness_partial_but_interpretable",
            "v0_10_7_handoff_mode": "decide_whether_one_more_bounded_real_origin_step_is_still_worth_it",
        },
    )
    _write_closeout(
        paths["v107"],
        "v0_10_7_more_bounded_real_origin_step_not_worth_it",
        {
            "remaining_uncertainty_status": "no_phase_relevant_uncertainty_remaining",
            "expected_information_gain": "marginal",
            "proposed_next_step_kind": "none",
            "v0_10_8_handoff_mode": "prepare_v0_10_phase_synthesis",
        },
    )
    return paths


class AgentModelicaV108PhaseSynthesisFlowTests(unittest.TestCase):
    def test_phase_ledger_passes_with_correct_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v108_phase_ledger(
                v100_closeout_path=str(paths["v100"]),
                v101_closeout_path=str(paths["v101"]),
                v102_closeout_path=str(paths["v102"]),
                v103_closeout_path=str(paths["v103"]),
                v104_closeout_path=str(paths["v104"]),
                v105_closeout_path=str(paths["v105"]),
                v106_closeout_path=str(paths["v106"]),
                v107_closeout_path=str(paths["v107"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["status"], "PASS")

    def test_stop_condition_nearly_complete_with_caveat_on_standard_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v108_stop_condition(
                v100_closeout_path=str(paths["v100"]),
                v101_closeout_path=str(paths["v101"]),
                v102_closeout_path=str(paths["v102"]),
                v103_closeout_path=str(paths["v103"]),
                v104_closeout_path=str(paths["v104"]),
                v105_closeout_path=str(paths["v105"]),
                v106_closeout_path=str(paths["v106"]),
                v107_closeout_path=str(paths["v107"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "nearly_complete_with_caveat")

    def test_stop_condition_met_is_reachable_with_supported_synthetic_input(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v106"],
                "v0_10_6_first_real_origin_workflow_readiness_partial_but_interpretable",
                {
                    "final_adjudication_label": "real_origin_workflow_readiness_supported",
                    "v0_10_7_handoff_mode": "decide_whether_one_more_bounded_real_origin_step_is_still_worth_it",
                },
            )
            payload = build_v108_stop_condition(
                v100_closeout_path=str(paths["v100"]),
                v101_closeout_path=str(paths["v101"]),
                v102_closeout_path=str(paths["v102"]),
                v103_closeout_path=str(paths["v103"]),
                v104_closeout_path=str(paths["v104"]),
                v105_closeout_path=str(paths["v105"]),
                v106_closeout_path=str(paths["v106"]),
                v107_closeout_path=str(paths["v107"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "met")

    def test_stop_condition_not_ready_when_chain_component_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(paths["v103"], "v0_10_3_first_real_origin_workflow_substrate_partial")
            payload = build_v108_stop_condition(
                v100_closeout_path=str(paths["v100"]),
                v101_closeout_path=str(paths["v101"]),
                v102_closeout_path=str(paths["v102"]),
                v103_closeout_path=str(paths["v103"]),
                v104_closeout_path=str(paths["v104"]),
                v105_closeout_path=str(paths["v105"]),
                v106_closeout_path=str(paths["v106"]),
                v107_closeout_path=str(paths["v107"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "not_ready_for_closeout")

    def test_meaning_synthesis_selects_workflow_to_product_gap(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v108_meaning_synthesis(
                v106_closeout_path=str(paths["v106"]),
                v107_closeout_path=str(paths["v107"]),
                out_dir=str(root / "meaning"),
            )
            self.assertTrue(payload["explicit_caveat_present"])
            self.assertEqual(payload["next_primary_phase_question"], "workflow_to_product_gap_evaluation")

    def test_closeout_reaches_nearly_complete_with_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v108_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v100_closeout_path=str(paths["v100"]),
                v101_closeout_path=str(paths["v101"]),
                v102_closeout_path=str(paths["v102"]),
                v103_closeout_path=str(paths["v103"]),
                v104_closeout_path=str(paths["v104"]),
                v105_closeout_path=str(paths["v105"]),
                v106_closeout_path=str(paths["v106"]),
                v107_closeout_path=str(paths["v107"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_phase_nearly_complete_with_explicit_caveat")
            self.assertEqual(payload["conclusion"]["next_primary_phase_question"], "workflow_to_product_gap_evaluation")
            self.assertTrue(payload["conclusion"]["do_not_continue_v0_10_same_real_origin_refinement_by_default"])

    def test_closeout_returns_invalid_on_bad_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(paths["v105"], "v0_10_5_first_real_origin_workflow_thresholds_partial")
            payload = build_v108_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v100_closeout_path=str(paths["v100"]),
                v101_closeout_path=str(paths["v101"]),
                v102_closeout_path=str(paths["v102"]),
                v103_closeout_path=str(paths["v103"]),
                v104_closeout_path=str(paths["v104"]),
                v105_closeout_path=str(paths["v105"]),
                v106_closeout_path=str(paths["v106"]),
                v107_closeout_path=str(paths["v107"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_8_handoff_phase_inputs_invalid")

    def test_closeout_met_without_caveat_is_intentionally_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v106"],
                "v0_10_6_first_real_origin_workflow_readiness_partial_but_interpretable",
                {
                    "final_adjudication_label": "real_origin_workflow_readiness_supported",
                    "v0_10_7_handoff_mode": "decide_whether_one_more_bounded_real_origin_step_is_still_worth_it",
                },
            )
            payload = build_v108_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v100_closeout_path=str(paths["v100"]),
                v101_closeout_path=str(paths["v101"]),
                v102_closeout_path=str(paths["v102"]),
                v103_closeout_path=str(paths["v103"]),
                v104_closeout_path=str(paths["v104"]),
                v105_closeout_path=str(paths["v105"]),
                v106_closeout_path=str(paths["v106"]),
                v107_closeout_path=str(paths["v107"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_10_8_handoff_phase_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
