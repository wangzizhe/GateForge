from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_6_3_candidate_adjudication import build_v063_candidate_adjudication
from gateforge.agent_modelica_v0_6_3_closeout import build_v063_closeout
from gateforge.agent_modelica_v0_6_3_decision_basis import build_v063_decision_basis
from gateforge.agent_modelica_v0_6_3_handoff_integrity import build_v063_handoff_integrity
from gateforge.agent_modelica_v0_6_3_phase_decision_input import build_v063_phase_decision_input


class AgentModelicaV063PhaseDecisionBasisFlowTests(unittest.TestCase):
    def _write_v062_inputs(self, root: Path, *, stable: bool = True, strong_open_world: bool = False) -> None:
        closeout = {
            "conclusion": {
                "version_decision": "v0_6_2_authority_profile_stable" if stable else "v0_6_2_authority_profile_partial",
                "profile_stability_status": "stable" if stable else "partial",
                "primary_profile_gap": "none" if stable else "profile_stability_gap",
                "legacy_taxonomy_still_sufficient": True,
                "fluid_network_extension_status_under_representative_pressure": "stable" if strong_open_world else "fragile_but_real",
                "do_not_reopen_v0_5_boundary_pressure_by_default": True,
            }
        }
        profile_stability = {
            "status": "PASS" if stable else "FAIL",
            "profile_stability_status": "stable" if stable else "partial",
            "legacy_taxonomy_still_sufficient": True,
            "legacy_bucket_mapping_rate_pct": 100.0,
            "stable_coverage_share_pct": 55.0 if strong_open_world else 47.2,
            "fragile_coverage_share_pct": 20.0,
            "limited_or_uncovered_share_pct": 25.0 if strong_open_world else 30.6,
        }
        live_rows = []
        for idx in range(36):
            if strong_open_world:
                bucket = "covered_success" if idx < 20 else ("covered_but_fragile" if idx < 30 else "dispatch_or_policy_limited")
            else:
                bucket = "covered_success" if idx < 17 else ("covered_but_fragile" if idx < 25 else ("bounded_uncovered_subtype_candidate" if idx < 31 else "dispatch_or_policy_limited"))
            live_rows.append({"task_id": f"case_{idx}", "assigned_bucket": bucket})
        live_run = {
            "case_result_table": live_rows,
        }
        for rel, payload in [
            ("closeout/summary.json", closeout),
            ("profile_stability/summary.json", profile_stability),
            ("live_run/summary.json", live_run),
        ]:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v063_reaches_ready_when_decision_basis_is_complete(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v062_inputs(root, stable=True, strong_open_world=False)
            build_v063_handoff_integrity(
                v062_closeout_path=str(root / "closeout" / "summary.json"),
                profile_stability_path=str(root / "profile_stability" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            build_v063_phase_decision_input(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                profile_stability_path=str(root / "profile_stability" / "summary.json"),
                live_run_path=str(root / "live_run" / "summary.json"),
                out_dir=str(root / "decision_input"),
            )
            build_v063_candidate_adjudication(
                phase_decision_input_path=str(root / "decision_input" / "summary.json"),
                out_dir=str(root / "candidate"),
            )
            build_v063_decision_basis(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                phase_decision_input_path=str(root / "decision_input" / "summary.json"),
                candidate_adjudication_path=str(root / "candidate" / "summary.json"),
                out_dir=str(root / "basis"),
            )
            payload = build_v063_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                phase_decision_input_path=str(root / "decision_input" / "summary.json"),
                candidate_adjudication_path=str(root / "candidate" / "summary.json"),
                decision_basis_path=str(root / "basis" / "summary.json"),
                out_dir=str(root / "closeout_v063"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_3_phase_decision_basis_ready")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_6_4_handoff_mode"), "run_late_v0_6_phase_decision")

    def test_v063_becomes_partial_when_neither_candidate_threshold_is_met(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v062_inputs(root, stable=True, strong_open_world=False)
            build_v063_handoff_integrity(
                v062_closeout_path=str(root / "closeout" / "summary.json"),
                profile_stability_path=str(root / "profile_stability" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            build_v063_phase_decision_input(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                profile_stability_path=str(root / "profile_stability" / "summary.json"),
                live_run_path=str(root / "live_run" / "summary.json"),
                out_dir=str(root / "decision_input"),
            )
            decision_input_path = root / "decision_input" / "summary.json"
            decision_input = json.loads(decision_input_path.read_text(encoding="utf-8"))
            decision_input["stable_coverage_share_pct"] = 47.2
            decision_input["phase_decision_input_table"]["stable_coverage_share_pct"] = 47.2
            decision_input["fluid_network_extension_status_under_representative_pressure"] = "fragile_but_real"
            decision_input["phase_decision_input_table"]["fluid_network_extension_status_under_representative_pressure"] = "fragile_but_real"
            decision_input["bounded_uncovered_signal_share_pct"] = 11.1
            decision_input["phase_decision_input_table"]["bounded_uncovered_signal_share_pct"] = 11.1
            decision_input_path.write_text(json.dumps(decision_input), encoding="utf-8")
            build_v063_candidate_adjudication(
                phase_decision_input_path=str(decision_input_path),
                out_dir=str(root / "candidate"),
            )
            build_v063_decision_basis(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                phase_decision_input_path=str(decision_input_path),
                candidate_adjudication_path=str(root / "candidate" / "summary.json"),
                out_dir=str(root / "basis"),
            )
            payload = build_v063_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                phase_decision_input_path=str(decision_input_path),
                candidate_adjudication_path=str(root / "candidate" / "summary.json"),
                decision_basis_path=str(root / "basis" / "summary.json"),
                out_dir=str(root / "closeout_v063"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_3_phase_decision_basis_partial")
            self.assertEqual((payload.get("conclusion") or {}).get("phase_decision_basis_gap"), "neither_candidate_threshold_met")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_6_4_handoff_mode"), "continue_late_v0_6_decision_preparation")

    def test_v063_becomes_invalid_when_upstream_profile_is_not_stable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v062_inputs(root, stable=False)
            build_v063_handoff_integrity(
                v062_closeout_path=str(root / "closeout" / "summary.json"),
                profile_stability_path=str(root / "profile_stability" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            payload = build_v063_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                phase_decision_input_path=str(root / "decision_input" / "summary.json"),
                candidate_adjudication_path=str(root / "candidate" / "summary.json"),
                decision_basis_path=str(root / "basis" / "summary.json"),
                out_dir=str(root / "closeout_v063"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_3_handoff_substrate_invalid")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_6_4_handoff_mode"), "repair_phase_decision_basis_first")


if __name__ == "__main__":
    unittest.main()
