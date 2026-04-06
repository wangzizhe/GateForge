from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_6_4_candidate_pressure import build_v064_candidate_pressure
from gateforge.agent_modelica_v0_6_4_closeout import build_v064_closeout
from gateforge.agent_modelica_v0_6_4_decision_maturity import build_v064_decision_maturity
from gateforge.agent_modelica_v0_6_4_handoff_integrity import build_v064_handoff_integrity
from gateforge.agent_modelica_v0_6_4_profile_refinement import build_v064_profile_refinement


class AgentModelicaV064PhaseDecisionInputFlowTests(unittest.TestCase):
    def _write_inputs(self, root: Path, *, invalid: bool = False, ready: bool = False) -> None:
        v060 = {"conclusion": {"version_decision": "v0_6_0_representative_substrate_ready"}}
        v062 = {
            "conclusion": {
                "version_decision": "v0_6_2_authority_profile_stable" if not invalid else "v0_6_2_authority_profile_partial",
                "fluid_network_extension_status_under_representative_pressure": "stable" if ready else "fragile_but_real",
            },
            "profile_stability": {
                "stable_coverage_share_pct": 55.0 if ready else 47.2,
                "fragile_coverage_share_pct": 20.0,
                "limited_or_uncovered_share_pct": 25.0 if ready else 30.6,
            },
        }
        v063 = {
            "conclusion": {
                "version_decision": "v0_6_3_phase_decision_basis_partial",
                "phase_decision_basis_gap": "neither_candidate_threshold_met",
                "do_not_reopen_v0_5_boundary_pressure_by_default": True,
            },
            "phase_decision_input": {
                "bounded_uncovered_signal_share_pct": 8.0 if ready else 11.1,
                "topology_or_open_world_spillover_share_pct": 0.0,
            },
        }

        live_rows = []
        if ready:
            for idx in range(36):
                bucket = "covered_success" if idx < 20 else ("covered_but_fragile" if idx < 28 else "dispatch_or_policy_limited")
                live_rows.append(
                    {
                        "task_id": f"case_{idx}",
                        "family_id": "component_api_alignment" if idx < 12 else ("local_interface_alignment" if idx < 24 else "medium_redeclare_alignment"),
                        "complexity_tier": "simple" if idx < 12 else ("medium" if idx < 24 else "complex"),
                        "assigned_bucket": bucket,
                        "qualitative_bucket": "fluid_network_medium_surface_pressure" if 30 <= idx < 33 else "none",
                    }
                )
        else:
            # mirrors the real 47.2 / 22.2 / 30.6 shape and creates a dominant complex-tier pressure
            for idx in range(36):
                if idx < 17:
                    bucket = "covered_success"
                elif idx < 25:
                    bucket = "covered_but_fragile"
                elif idx < 32:
                    bucket = "dispatch_or_policy_limited"
                else:
                    bucket = "bounded_uncovered_subtype_candidate"
                live_rows.append(
                    {
                        "task_id": f"case_{idx}",
                        "family_id": "component_api_alignment" if idx < 10 else ("local_interface_alignment" if idx < 20 else "medium_redeclare_alignment"),
                        "complexity_tier": "simple" if idx < 11 else ("medium" if idx < 23 else "complex"),
                        "assigned_bucket": bucket,
                        "qualitative_bucket": "fluid_network_medium_surface_pressure" if idx in {24, 25, 30, 33, 34} else "none",
                    }
                )

        for rel, payload in [
            ("v060.json", v060),
            ("v062_closeout.json", v062),
            ("v063_closeout.json", v063),
            ("v062_live.json", {"case_result_table": live_rows}),
        ]:
            path = root / rel
            path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v064_reaches_ready_when_open_world_candidate_crosses_floor(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_inputs(root, ready=True)
            build_v064_handoff_integrity(
                v060_closeout_path=str(root / "v060.json"),
                v062_closeout_path=str(root / "v062_closeout.json"),
                v063_closeout_path=str(root / "v063_closeout.json"),
                out_dir=str(root / "integrity"),
            )
            build_v064_profile_refinement(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                live_run_path=str(root / "v062_live.json"),
                out_dir=str(root / "refinement"),
            )
            build_v064_candidate_pressure(
                profile_refinement_path=str(root / "refinement" / "summary.json"),
                v062_closeout_path=str(root / "v062_closeout.json"),
                v063_closeout_path=str(root / "v063_closeout.json"),
                out_dir=str(root / "candidate"),
            )
            build_v064_decision_maturity(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                profile_refinement_path=str(root / "refinement" / "summary.json"),
                candidate_pressure_path=str(root / "candidate" / "summary.json"),
                out_dir=str(root / "maturity"),
            )
            payload = build_v064_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                profile_refinement_path=str(root / "refinement" / "summary.json"),
                candidate_pressure_path=str(root / "candidate" / "summary.json"),
                decision_maturity_path=str(root / "maturity" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_4_phase_decision_input_ready")

    def test_v064_reaches_partial_when_open_world_is_only_a_near_miss(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_inputs(root, ready=False)
            build_v064_handoff_integrity(
                v060_closeout_path=str(root / "v060.json"),
                v062_closeout_path=str(root / "v062_closeout.json"),
                v063_closeout_path=str(root / "v063_closeout.json"),
                out_dir=str(root / "integrity"),
            )
            build_v064_profile_refinement(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                live_run_path=str(root / "v062_live.json"),
                out_dir=str(root / "refinement"),
            )
            build_v064_candidate_pressure(
                profile_refinement_path=str(root / "refinement" / "summary.json"),
                v062_closeout_path=str(root / "v062_closeout.json"),
                v063_closeout_path=str(root / "v063_closeout.json"),
                out_dir=str(root / "candidate"),
            )
            build_v064_decision_maturity(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                profile_refinement_path=str(root / "refinement" / "summary.json"),
                candidate_pressure_path=str(root / "candidate" / "summary.json"),
                out_dir=str(root / "maturity"),
            )
            payload = build_v064_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                profile_refinement_path=str(root / "refinement" / "summary.json"),
                candidate_pressure_path=str(root / "candidate" / "summary.json"),
                decision_maturity_path=str(root / "maturity" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_4_phase_decision_input_partial")
            self.assertTrue((payload.get("conclusion") or {}).get("near_miss_open_world_candidate"))

    def test_v064_becomes_invalid_when_upstream_chain_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_inputs(root, invalid=True)
            build_v064_handoff_integrity(
                v060_closeout_path=str(root / "v060.json"),
                v062_closeout_path=str(root / "v062_closeout.json"),
                v063_closeout_path=str(root / "v063_closeout.json"),
                out_dir=str(root / "integrity"),
            )
            payload = build_v064_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                profile_refinement_path=str(root / "refinement" / "summary.json"),
                candidate_pressure_path=str(root / "candidate" / "summary.json"),
                decision_maturity_path=str(root / "maturity" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_4_handoff_substrate_invalid")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_6_5_handoff_mode"), "repair_phase_decision_basis_first")


if __name__ == "__main__":
    unittest.main()
