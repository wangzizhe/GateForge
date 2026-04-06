from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_5_7_boundary_synthesis import build_v057_boundary_synthesis
from gateforge.agent_modelica_v0_5_7_closeout import build_v057_closeout
from gateforge.agent_modelica_v0_5_7_phase_ledger import build_v057_phase_ledger
from gateforge.agent_modelica_v0_5_7_stop_condition_audit import build_v057_stop_condition_audit
from gateforge.agent_modelica_v0_5_7_v0_6_handoff import build_v057_v0_6_handoff


class AgentModelicaV057PhaseSynthesisFlowTests(unittest.TestCase):
    def _write_closeout(self, path: Path, version_decision: str, extra: dict | None = None) -> None:
        payload = {"conclusion": {"version_decision": version_decision}}
        if extra:
            payload["conclusion"].update(extra)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_case_classification(self, path: Path, *, bounded_uncovered_count: int = 6) -> None:
        payload = {
            "bucket_case_count_table": {
                "covered_success": 8,
                "covered_but_fragile": 4,
                "dispatch_or_policy_limited": 0,
                "bounded_uncovered_subtype_candidate": bounded_uncovered_count,
                "topology_or_open_world_spillover": 0,
                "boundary_ambiguous": 0,
            }
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_boundary_readiness(self, path: Path) -> None:
        payload = {"boundary_map_ready": True}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v057_reaches_prepare_v0_6_when_full_chain_is_intact(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_closeout(root / "v050" / "summary.json", "v0_5_0_widened_real_substrate_ready", {"qualitative_widening_confirmed": True, "dispatch_cleanliness_preserved": True})
            self._write_closeout(root / "v051" / "summary.json", "v0_5_1_boundary_map_ready", {"boundary_map_status": "ready"})
            self._write_closeout(root / "v052" / "summary.json", "v0_5_2_targeted_expansion_entry_ready", {"entry_ready": True})
            self._write_closeout(root / "v053" / "summary.json", "v0_5_3_targeted_expansion_first_fix_ready", {"first_fix_ready": True})
            self._write_closeout(root / "v054" / "summary.json", "v0_5_4_targeted_expansion_discovery_ready", {"discovery_ready": True})
            self._write_closeout(root / "v055" / "summary.json", "v0_5_5_targeted_expansion_widened_ready", {"widened_ready": True})
            self._write_closeout(
                root / "v056" / "summary.json",
                "v0_5_6_family_level_promotion_supported",
                {"promotion_supported": True, "recommended_promotion_level": "family_extension_supported"},
            )
            self._write_case_classification(root / "classification" / "summary.json")
            self._write_boundary_readiness(root / "readiness" / "summary.json")

            build_v057_phase_ledger(
                v050_closeout_path=str(root / "v050" / "summary.json"),
                v051_closeout_path=str(root / "v051" / "summary.json"),
                v052_closeout_path=str(root / "v052" / "summary.json"),
                v053_closeout_path=str(root / "v053" / "summary.json"),
                v054_closeout_path=str(root / "v054" / "summary.json"),
                v055_closeout_path=str(root / "v055" / "summary.json"),
                v056_closeout_path=str(root / "v056" / "summary.json"),
                out_dir=str(root / "ledger"),
            )
            build_v057_stop_condition_audit(
                v050_closeout_path=str(root / "v050" / "summary.json"),
                v051_closeout_path=str(root / "v051" / "summary.json"),
                v051_boundary_readiness_path=str(root / "readiness" / "summary.json"),
                v056_closeout_path=str(root / "v056" / "summary.json"),
                out_dir=str(root / "audit"),
            )
            build_v057_boundary_synthesis(
                v051_case_classification_path=str(root / "classification" / "summary.json"),
                v056_closeout_path=str(root / "v056" / "summary.json"),
                out_dir=str(root / "boundary"),
            )
            build_v057_v0_6_handoff(
                stop_audit_path=str(root / "audit" / "summary.json"),
                boundary_synthesis_path=str(root / "boundary" / "summary.json"),
                out_dir=str(root / "handoff"),
            )
            payload = build_v057_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_audit_path=str(root / "audit" / "summary.json"),
                boundary_synthesis_path=str(root / "boundary" / "summary.json"),
                v0_6_handoff_path=str(root / "handoff" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_5_phase_complete_prepare_v0_6")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_6_primary_phase_question"), "broader_real_distribution_authority")
            self.assertTrue((payload.get("conclusion") or {}).get("do_not_continue_v0_5_branch_expansion_by_default"))

    def test_v057_does_not_close_phase_when_promotion_link_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_closeout(root / "v050" / "summary.json", "v0_5_0_widened_real_substrate_ready", {"qualitative_widening_confirmed": True, "dispatch_cleanliness_preserved": True})
            self._write_closeout(root / "v051" / "summary.json", "v0_5_1_boundary_map_ready", {"boundary_map_status": "ready"})
            self._write_closeout(root / "v052" / "summary.json", "v0_5_2_targeted_expansion_entry_ready", {"entry_ready": True})
            self._write_closeout(root / "v053" / "summary.json", "v0_5_3_targeted_expansion_first_fix_ready", {"first_fix_ready": True})
            self._write_closeout(root / "v054" / "summary.json", "v0_5_4_targeted_expansion_discovery_ready", {"discovery_ready": True})
            self._write_closeout(root / "v055" / "summary.json", "v0_5_5_targeted_expansion_widened_ready", {"widened_ready": True})
            self._write_closeout(
                root / "v056" / "summary.json",
                "v0_5_6_promotion_not_supported",
                {"promotion_supported": False, "recommended_promotion_level": "stable_branch_only"},
            )
            self._write_case_classification(root / "classification" / "summary.json", bounded_uncovered_count=2)
            self._write_boundary_readiness(root / "readiness" / "summary.json")

            build_v057_phase_ledger(
                v050_closeout_path=str(root / "v050" / "summary.json"),
                v051_closeout_path=str(root / "v051" / "summary.json"),
                v052_closeout_path=str(root / "v052" / "summary.json"),
                v053_closeout_path=str(root / "v053" / "summary.json"),
                v054_closeout_path=str(root / "v054" / "summary.json"),
                v055_closeout_path=str(root / "v055" / "summary.json"),
                v056_closeout_path=str(root / "v056" / "summary.json"),
                out_dir=str(root / "ledger"),
            )
            build_v057_stop_condition_audit(
                v050_closeout_path=str(root / "v050" / "summary.json"),
                v051_closeout_path=str(root / "v051" / "summary.json"),
                v051_boundary_readiness_path=str(root / "readiness" / "summary.json"),
                v056_closeout_path=str(root / "v056" / "summary.json"),
                out_dir=str(root / "audit"),
            )
            build_v057_boundary_synthesis(
                v051_case_classification_path=str(root / "classification" / "summary.json"),
                v056_closeout_path=str(root / "v056" / "summary.json"),
                out_dir=str(root / "boundary"),
            )
            build_v057_v0_6_handoff(
                stop_audit_path=str(root / "audit" / "summary.json"),
                boundary_synthesis_path=str(root / "boundary" / "summary.json"),
                out_dir=str(root / "handoff"),
            )
            payload = build_v057_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_audit_path=str(root / "audit" / "summary.json"),
                boundary_synthesis_path=str(root / "boundary" / "summary.json"),
                v0_6_handoff_path=str(root / "handoff" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_5_7_handoff_substrate_invalid")


if __name__ == "__main__":
    unittest.main()
