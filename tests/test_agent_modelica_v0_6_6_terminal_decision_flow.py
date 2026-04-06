from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_6_6_closeout import build_v066_closeout
from gateforge.agent_modelica_v0_6_6_complex_gap_recheck import build_v066_complex_gap_recheck
from gateforge.agent_modelica_v0_6_6_handoff_integrity import build_v066_handoff_integrity
from gateforge.agent_modelica_v0_6_6_terminal_decision import build_v066_terminal_decision


class AgentModelicaV066TerminalDecisionFlowTests(unittest.TestCase):
    def _write_inputs(self, root: Path, *, invalid: bool = False, ready: bool = False) -> None:
        v062 = {"conclusion": {"version_decision": "v0_6_2_authority_profile_stable" if not invalid else "v0_6_2_authority_profile_partial"}}
        v064 = {"conclusion": {"version_decision": "v0_6_4_phase_decision_input_partial"}}
        if ready:
            v065 = {
                "conclusion": {
                    "version_decision": "v0_6_5_phase_decision_partial",
                    "dominant_remaining_authority_gap": "complex_tier_pressure_under_representative_logic",
                    "fluid_network_still_not_blocking": True,
                    "do_not_reopen_v0_5_boundary_pressure_by_default": True,
                    "open_world_margin_vs_floor_pct": -0.8,
                },
                "open_world_recheck": {
                    "complex_tier_pressure_rechecked": {
                        "stable_coverage_complex": 18.0,
                        "stable_coverage_medium": 45.5,
                        "stable_coverage_simple": 100.0,
                        "complex_pressure_count": 8,
                        "total_pressure_case_count": 19,
                    },
                    "fluid_network_subprofile_rechecked": {
                        "case_count": 5,
                        "bucket_counts": {"covered_but_fragile": 1, "dispatch_or_policy_limited": 2, "bounded_uncovered_subtype_candidate": 2},
                        "systemic_failure_case_count": 4,
                        "failures_cleanly_explained_by_legacy_buckets": True,
                    },
                    "legacy_taxonomy_still_sufficient": True,
                    "representative_logic_delta": "none",
                    "open_world_candidate_supported_after_recheck": True,
                    "open_world_margin_vs_floor_pct": -0.8,
                    "dominant_remaining_authority_gap": "none",
                    "complex_tier_pressure_is_primary_gap": False,
                    "fluid_network_still_not_blocking": True,
                },
            }
        else:
            v065 = {
                "conclusion": {
                    "version_decision": "v0_6_5_phase_decision_partial",
                    "dominant_remaining_authority_gap": "complex_tier_pressure_under_representative_logic",
                    "fluid_network_still_not_blocking": True,
                    "do_not_reopen_v0_5_boundary_pressure_by_default": True,
                    "open_world_margin_vs_floor_pct": -2.8,
                },
                "open_world_recheck": {
                    "complex_tier_pressure_rechecked": {
                        "stable_coverage_complex": 7.1,
                        "stable_coverage_medium": 45.5,
                        "stable_coverage_simple": 100.0,
                        "complex_pressure_count": 13,
                        "total_pressure_case_count": 19,
                    },
                    "fluid_network_subprofile_rechecked": {
                        "case_count": 5,
                        "bucket_counts": {"covered_but_fragile": 1, "dispatch_or_policy_limited": 2, "bounded_uncovered_subtype_candidate": 2},
                        "systemic_failure_case_count": 4,
                        "failures_cleanly_explained_by_legacy_buckets": True,
                    },
                    "legacy_taxonomy_still_sufficient": True,
                    "representative_logic_delta": "none",
                    "open_world_candidate_supported_after_recheck": False,
                    "open_world_margin_vs_floor_pct": -2.8,
                    "dominant_remaining_authority_gap": "complex_tier_pressure_under_representative_logic",
                    "complex_tier_pressure_is_primary_gap": True,
                    "fluid_network_still_not_blocking": True,
                },
            }

        for rel, payload in [("v062.json", v062), ("v064.json", v064), ("v065.json", v065)]:
            (root / rel).write_text(json.dumps(payload), encoding="utf-8")

    def test_v066_reaches_phase_closeout_supported_when_gap_is_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_inputs(root, ready=False)
            build_v066_handoff_integrity(
                v062_closeout_path=str(root / "v062.json"),
                v064_closeout_path=str(root / "v064.json"),
                v065_closeout_path=str(root / "v065.json"),
                out_dir=str(root / "integrity"),
            )
            build_v066_complex_gap_recheck(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                v064_closeout_path=str(root / "v064.json"),
                v065_closeout_path=str(root / "v065.json"),
                out_dir=str(root / "recheck"),
            )
            build_v066_terminal_decision(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                complex_gap_recheck_path=str(root / "recheck" / "summary.json"),
                out_dir=str(root / "terminal"),
            )
            payload = build_v066_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                complex_gap_recheck_path=str(root / "recheck" / "summary.json"),
                terminal_decision_path=str(root / "terminal" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_6_phase_closeout_supported")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_6_7_handoff_mode"), "run_v0_6_phase_synthesis")

    def test_v066_reaches_ready_when_open_world_candidate_crosses_floor(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_inputs(root, ready=True)
            build_v066_handoff_integrity(
                v062_closeout_path=str(root / "v062.json"),
                v064_closeout_path=str(root / "v064.json"),
                v065_closeout_path=str(root / "v065.json"),
                out_dir=str(root / "integrity"),
            )
            build_v066_complex_gap_recheck(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                v064_closeout_path=str(root / "v064.json"),
                v065_closeout_path=str(root / "v065.json"),
                out_dir=str(root / "recheck"),
            )
            build_v066_terminal_decision(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                complex_gap_recheck_path=str(root / "recheck" / "summary.json"),
                out_dir=str(root / "terminal"),
            )
            payload = build_v066_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                complex_gap_recheck_path=str(root / "recheck" / "summary.json"),
                terminal_decision_path=str(root / "terminal" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_6_phase_decision_ready")

    def test_v066_becomes_invalid_when_chain_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_inputs(root, invalid=True)
            build_v066_handoff_integrity(
                v062_closeout_path=str(root / "v062.json"),
                v064_closeout_path=str(root / "v064.json"),
                v065_closeout_path=str(root / "v065.json"),
                out_dir=str(root / "integrity"),
            )
            payload = build_v066_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                complex_gap_recheck_path=str(root / "recheck" / "summary.json"),
                terminal_decision_path=str(root / "terminal" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_6_handoff_substrate_invalid")


if __name__ == "__main__":
    unittest.main()
