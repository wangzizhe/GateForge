from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_9_7_closeout import build_v097_closeout
from gateforge.agent_modelica_v0_9_7_meaning_synthesis import build_v097_meaning_synthesis
from gateforge.agent_modelica_v0_9_7_phase_ledger import build_v097_phase_ledger
from gateforge.agent_modelica_v0_9_7_stop_condition import build_v097_stop_condition


def _write_closeout(path: Path, version_decision: str, extra: dict | None = None) -> None:
    payload = {"conclusion": {"version_decision": version_decision}}
    if extra:
        payload["conclusion"].update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_standard_chain(root: Path) -> dict[str, Path]:
    paths = {
        "v090": root / "v090" / "summary.json",
        "v091": root / "v091" / "summary.json",
        "v092": root / "v092" / "summary.json",
        "v093": root / "v093" / "summary.json",
        "v094": root / "v094" / "summary.json",
        "v095": root / "v095" / "summary.json",
        "v096": root / "v096" / "summary.json",
    }
    _write_closeout(
        paths["v090"],
        "v0_9_0_candidate_pool_governance_partial",
        {
            "needs_additional_real_sources": True,
            "v0_9_1_handoff_mode": "expand_real_candidate_pool_before_substrate_freeze",
        },
    )
    _write_closeout(
        paths["v091"],
        "v0_9_1_real_candidate_source_expansion_ready",
        {
            "post_expansion_candidate_pool_count": 28,
            "candidate_depth_by_priority_barrier": {
                "goal_artifact_missing_after_surface_fix": 8,
                "dispatch_or_policy_limited_unresolved": 8,
                "workflow_spillover_unresolved": 8,
            },
        },
    )
    _write_closeout(
        paths["v092"],
        "v0_9_2_first_expanded_authentic_workflow_substrate_ready",
        {
            "expanded_substrate_size": 19,
            "priority_barrier_coverage_table": {
                "goal_artifact_missing_after_surface_fix": 5,
                "dispatch_or_policy_limited_unresolved": 5,
                "workflow_spillover_unresolved": 5,
            },
        },
    )
    _write_closeout(
        paths["v093"],
        "v0_9_3_expanded_workflow_profile_characterized",
        {
            "profile_barrier_unclassified_count": 0,
            "workflow_resolution_rate_pct": 21.1,
            "goal_alignment_rate_pct": 47.4,
        },
    )
    _write_closeout(
        paths["v094"],
        "v0_9_4_expanded_workflow_thresholds_frozen",
        {
            "anti_tautology_pass": True,
            "integer_safe_pass": True,
        },
    )
    _write_closeout(
        paths["v095"],
        "v0_9_5_expanded_workflow_readiness_partial_but_interpretable",
        {
            "final_adjudication_label": "expanded_workflow_readiness_partial_but_interpretable",
            "adjudication_route_count": 1,
            "v0_9_6_handoff_mode": "decide_whether_more_authentic_expansion_is_still_worth_it",
        },
    )
    _write_closeout(
        paths["v096"],
        "v0_9_6_more_authentic_expansion_not_worth_it",
        {
            "remaining_uncertainty_status": "no_expansion_addressable_uncertainty_with_meaningful_expected_gain",
            "expected_information_gain": "marginal",
            "v0_9_7_handoff_mode": "prepare_v0_9_phase_synthesis",
        },
    )
    return paths


class AgentModelicaV097PhaseSynthesisFlowTests(unittest.TestCase):
    def test_phase_ledger_passes_with_correct_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v097_phase_ledger(
                v090_closeout_path=str(paths["v090"]),
                v091_closeout_path=str(paths["v091"]),
                v092_closeout_path=str(paths["v092"]),
                v093_closeout_path=str(paths["v093"]),
                v094_closeout_path=str(paths["v094"]),
                v095_closeout_path=str(paths["v095"]),
                v096_closeout_path=str(paths["v096"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["status"], "PASS")

    def test_stop_condition_met_with_standard_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v097_stop_condition(
                v090_closeout_path=str(paths["v090"]),
                v091_closeout_path=str(paths["v091"]),
                v092_closeout_path=str(paths["v092"]),
                v093_closeout_path=str(paths["v093"]),
                v094_closeout_path=str(paths["v094"]),
                v095_closeout_path=str(paths["v095"]),
                v096_closeout_path=str(paths["v096"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "met")

    def test_stop_condition_nearly_complete_with_caveat_is_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(
                paths["v095"],
                "v0_9_5_expanded_workflow_readiness_partial_but_interpretable",
                {
                    "final_adjudication_label": "expanded_workflow_readiness_supported",
                    "adjudication_route_count": 1,
                    "v0_9_6_handoff_mode": "decide_whether_more_authentic_expansion_is_still_worth_it",
                },
            )
            payload = build_v097_stop_condition(
                v090_closeout_path=str(paths["v090"]),
                v091_closeout_path=str(paths["v091"]),
                v092_closeout_path=str(paths["v092"]),
                v093_closeout_path=str(paths["v093"]),
                v094_closeout_path=str(paths["v094"]),
                v095_closeout_path=str(paths["v095"]),
                v096_closeout_path=str(paths["v096"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "nearly_complete_with_caveat")

    def test_stop_condition_not_ready_when_chain_component_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(paths["v091"], "v0_9_1_real_candidate_source_expansion_partial")
            payload = build_v097_stop_condition(
                v090_closeout_path=str(paths["v090"]),
                v091_closeout_path=str(paths["v091"]),
                v092_closeout_path=str(paths["v092"]),
                v093_closeout_path=str(paths["v093"]),
                v094_closeout_path=str(paths["v094"]),
                v095_closeout_path=str(paths["v095"]),
                v096_closeout_path=str(paths["v096"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "not_ready_for_closeout")

    def test_meaning_synthesis_selects_real_origin_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v097_meaning_synthesis(
                v095_closeout_path=str(paths["v095"]),
                v096_closeout_path=str(paths["v096"]),
                out_dir=str(root / "meaning"),
            )
            self.assertTrue(payload["explicit_caveat_present"])
            self.assertEqual(
                payload["next_primary_phase_question"],
                "real_origin_workflow_readiness_evaluation",
            )

    def test_closeout_reaches_nearly_complete_with_caveat(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v097_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v090_closeout_path=str(paths["v090"]),
                v091_closeout_path=str(paths["v091"]),
                v092_closeout_path=str(paths["v092"]),
                v093_closeout_path=str(paths["v093"]),
                v094_closeout_path=str(paths["v094"]),
                v095_closeout_path=str(paths["v095"]),
                v096_closeout_path=str(paths["v096"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_9_phase_nearly_complete_with_explicit_caveat",
            )
            self.assertEqual(
                payload["conclusion"]["next_primary_phase_question"],
                "real_origin_workflow_readiness_evaluation",
            )
            self.assertTrue(payload["conclusion"]["do_not_continue_v0_9_same_authentic_expansion_by_default"])

    def test_closeout_returns_invalid_on_bad_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            _write_closeout(paths["v094"], "v0_9_4_expanded_workflow_thresholds_partial")
            payload = build_v097_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "meaning" / "summary.json"),
                v090_closeout_path=str(paths["v090"]),
                v091_closeout_path=str(paths["v091"]),
                v092_closeout_path=str(paths["v092"]),
                v093_closeout_path=str(paths["v093"]),
                v094_closeout_path=str(paths["v094"]),
                v095_closeout_path=str(paths["v095"]),
                v096_closeout_path=str(paths["v096"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_9_7_handoff_phase_inputs_invalid",
            )


if __name__ == "__main__":
    unittest.main()
