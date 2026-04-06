from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_6_5_closeout import build_v065_closeout
from gateforge.agent_modelica_v0_6_5_decision_maturity import build_v065_decision_maturity
from gateforge.agent_modelica_v0_6_5_handoff_integrity import build_v065_handoff_integrity
from gateforge.agent_modelica_v0_6_5_open_world_recheck import build_v065_open_world_recheck


class AgentModelicaV065PhaseDecisionFlowTests(unittest.TestCase):
    def _write_inputs(self, root: Path, *, invalid: bool = False, ready: bool = False) -> None:
        v062 = {
            "conclusion": {
                "version_decision": "v0_6_2_authority_profile_stable" if not invalid else "v0_6_2_authority_profile_partial",
            }
        }
        v064 = {
            "conclusion": {
                "version_decision": "v0_6_4_phase_decision_input_partial",
                "near_miss_open_world_candidate": not invalid,
                "fluid_network_extension_blocking_open_world": False,
                "do_not_reopen_v0_5_boundary_pressure_by_default": True,
            },
            "profile_refinement": {
                "stable_coverage_by_complexity": {
                    "simple": 100.0,
                    "medium": 48.0 if ready else 45.5,
                    "complex": 12.0 if ready else 7.1,
                },
                "complexity_pressure_counts": {
                    "medium": 6,
                    "complex": 8 if ready else 13,
                },
                "total_pressure_case_count": 16 if ready else 19,
                "fluid_network_pressure_subprofile": {
                    "case_count": 5,
                    "bucket_counts": {"covered_but_fragile": 1, "dispatch_or_policy_limited": 2, "bounded_uncovered_subtype_candidate": 2},
                    "systemic_failure_case_count": 4,
                    "failures_cleanly_explained_by_legacy_buckets": True,
                },
                "representative_logic_delta": "none",
                "legacy_taxonomy_still_sufficient": True,
            },
            "candidate_pressure": {
                "stable_coverage_share_pct": 50.5 if ready else 47.2,
                "topology_or_open_world_spillover_share_pct": 0.0,
                "fluid_network_extension_blocking_open_world": False,
            },
        }
        for rel, payload in [("v062.json", v062), ("v064.json", v064)]:
            (root / rel).write_text(json.dumps(payload), encoding="utf-8")

    def test_v065_reaches_ready_when_open_world_floor_is_crossed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_inputs(root, ready=True)
            build_v065_handoff_integrity(
                v062_closeout_path=str(root / "v062.json"),
                v064_closeout_path=str(root / "v064.json"),
                out_dir=str(root / "integrity"),
            )
            build_v065_open_world_recheck(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                v064_closeout_path=str(root / "v064.json"),
                out_dir=str(root / "recheck"),
            )
            build_v065_decision_maturity(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                open_world_recheck_path=str(root / "recheck" / "summary.json"),
                out_dir=str(root / "maturity"),
            )
            payload = build_v065_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                open_world_recheck_path=str(root / "recheck" / "summary.json"),
                decision_maturity_path=str(root / "maturity" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_5_phase_decision_ready")

    def test_v065_reaches_partial_when_single_gap_remains(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_inputs(root, ready=False)
            build_v065_handoff_integrity(
                v062_closeout_path=str(root / "v062.json"),
                v064_closeout_path=str(root / "v064.json"),
                out_dir=str(root / "integrity"),
            )
            build_v065_open_world_recheck(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                v064_closeout_path=str(root / "v064.json"),
                out_dir=str(root / "recheck"),
            )
            build_v065_decision_maturity(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                open_world_recheck_path=str(root / "recheck" / "summary.json"),
                out_dir=str(root / "maturity"),
            )
            payload = build_v065_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                open_world_recheck_path=str(root / "recheck" / "summary.json"),
                decision_maturity_path=str(root / "maturity" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_5_phase_decision_partial")
            self.assertEqual((payload.get("conclusion") or {}).get("dominant_remaining_authority_gap"), "complex_tier_pressure_under_representative_logic")

    def test_v065_becomes_invalid_when_handoff_chain_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_inputs(root, invalid=True)
            build_v065_handoff_integrity(
                v062_closeout_path=str(root / "v062.json"),
                v064_closeout_path=str(root / "v064.json"),
                out_dir=str(root / "integrity"),
            )
            payload = build_v065_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                open_world_recheck_path=str(root / "recheck" / "summary.json"),
                decision_maturity_path=str(root / "maturity" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_5_handoff_substrate_invalid")


if __name__ == "__main__":
    unittest.main()
