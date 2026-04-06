from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_7_2_closeout import build_v072_closeout
from gateforge.agent_modelica_v0_7_2_handoff_integrity import build_v072_handoff_integrity
from gateforge.agent_modelica_v0_7_2_live_run import build_v072_live_run
from gateforge.agent_modelica_v0_7_2_profile_extension import build_v072_profile_extension
from gateforge.agent_modelica_v0_7_2_profile_stability import build_v072_profile_stability


class AgentModelicaV072ReadinessProfileStabilityFlowTests(unittest.TestCase):
    def _write_v071_inputs(self, root: Path, *, ready: bool = True) -> None:
        closeout = {
            "conclusion": {
                "version_decision": "v0_7_1_readiness_profile_ready" if ready else "v0_7_1_readiness_profile_partial",
                "profile_admission_status": "ready" if ready else "partial",
                "legacy_bucket_mapping_rate_pct_after_live_run": 90.9,
                "spillover_share_pct_after_live_run": 18.2,
                "stable_coverage_share_pct": 40.9,
                "dominant_pressure_source": "complexity:complex" if ready else "unknown",
            }
        }
        rows = [
            {"task_id": "c1", "family_id": "component_api_alignment", "complexity_tier": "simple", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
            {"task_id": "c2", "family_id": "component_api_alignment", "complexity_tier": "medium", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
            {"task_id": "c3", "family_id": "component_api_alignment", "complexity_tier": "complex", "legacy_bucket_hint": "dispatch_or_policy_limited", "dispatch_risk": "ambiguous"},
            {"task_id": "c4", "family_id": "local_interface_alignment", "complexity_tier": "simple", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
            {"task_id": "c5", "family_id": "local_interface_alignment", "complexity_tier": "medium", "legacy_bucket_hint": "covered_but_fragile", "dispatch_risk": "clean"},
            {"task_id": "c6", "family_id": "local_interface_alignment", "complexity_tier": "complex", "legacy_bucket_hint": "dispatch_or_policy_limited", "dispatch_risk": "ambiguous"},
            {"task_id": "c7", "family_id": "medium_redeclare_alignment", "complexity_tier": "simple", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
            {"task_id": "c8", "family_id": "medium_redeclare_alignment", "complexity_tier": "medium", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
            {"task_id": "c9", "family_id": "medium_redeclare_alignment", "complexity_tier": "complex", "legacy_bucket_hint": "bounded_uncovered_subtype_candidate", "dispatch_risk": "clean"},
            {"task_id": "c10", "family_id": "medium_redeclare_alignment", "complexity_tier": "complex", "legacy_bucket_hint": "topology_or_open_world_spillover", "dispatch_risk": "clean"},
            {"task_id": "c11", "family_id": "local_interface_alignment", "complexity_tier": "complex", "legacy_bucket_hint": "topology_or_open_world_spillover", "dispatch_risk": "clean"},
            {"task_id": "c12", "family_id": "component_api_alignment", "complexity_tier": "medium", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
            {"task_id": "c13", "family_id": "local_interface_alignment", "complexity_tier": "medium", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
            {"task_id": "c14", "family_id": "medium_redeclare_alignment", "complexity_tier": "complex", "legacy_bucket_hint": "unclassified_pending_taxonomy", "dispatch_risk": "clean"},
            {"task_id": "c15", "family_id": "component_api_alignment", "complexity_tier": "complex", "legacy_bucket_hint": "topology_or_open_world_spillover", "dispatch_risk": "clean"},
            {"task_id": "c16", "family_id": "local_interface_alignment", "complexity_tier": "simple", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
            {"task_id": "c17", "family_id": "medium_redeclare_alignment", "complexity_tier": "simple", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
            {"task_id": "c18", "family_id": "component_api_alignment", "complexity_tier": "complex", "legacy_bucket_hint": "dispatch_or_policy_limited", "dispatch_risk": "ambiguous"},
            {"task_id": "c19", "family_id": "local_interface_alignment", "complexity_tier": "medium", "legacy_bucket_hint": "covered_but_fragile", "dispatch_risk": "clean"},
            {"task_id": "c20", "family_id": "medium_redeclare_alignment", "complexity_tier": "complex", "legacy_bucket_hint": "bounded_uncovered_subtype_candidate", "dispatch_risk": "clean"},
            {"task_id": "c21", "family_id": "component_api_alignment", "complexity_tier": "simple", "legacy_bucket_hint": "covered_success", "dispatch_risk": "clean"},
            {"task_id": "c22", "family_id": "local_interface_alignment", "complexity_tier": "complex", "legacy_bucket_hint": "dispatch_or_policy_limited", "dispatch_risk": "ambiguous"},
        ]
        substrate = {"task_rows": rows}
        for rel, payload in [
            ("closeout/summary.json", closeout),
            ("substrate/summary.json", substrate),
        ]:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v072_reaches_stable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v071_inputs(root, ready=True)
            build_v072_handoff_integrity(
                v071_closeout_path=str(root / "closeout" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            build_v072_profile_extension(
                substrate_path=str(root / "substrate" / "summary.json"),
                out_dir=str(root / "extension"),
            )
            build_v072_live_run(
                profile_extension_path=str(root / "extension" / "summary.json"),
                out_dir=str(root / "live"),
            )
            build_v072_profile_stability(
                v071_closeout_path=str(root / "closeout" / "summary.json"),
                live_run_path=str(root / "live" / "summary.json"),
                out_dir=str(root / "stability"),
            )
            payload = build_v072_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                profile_extension_path=str(root / "extension" / "summary.json"),
                live_run_path=str(root / "live" / "summary.json"),
                profile_stability_path=str(root / "stability" / "summary.json"),
                out_dir=str(root / "closeout_v072"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_7_2_readiness_profile_stable")

    def test_v072_partial_when_stable_share_drops_but_not_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v071_inputs(root, ready=True)
            build_v072_handoff_integrity(
                v071_closeout_path=str(root / "closeout" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            build_v072_profile_extension(
                substrate_path=str(root / "substrate" / "summary.json"),
                out_dir=str(root / "extension"),
            )
            build_v072_live_run(
                profile_extension_path=str(root / "extension" / "summary.json"),
                out_dir=str(root / "live"),
            )
            stability = build_v072_profile_stability(
                v071_closeout_path=str(root / "closeout" / "summary.json"),
                live_run_path=str(root / "live" / "summary.json"),
                out_dir=str(root / "stability"),
            )
            stability["stable_coverage_share_pct_after_extension"] = 30.0
            stability["profile_stability_status"] = "partial"
            (root / "stability" / "summary.json").write_text(json.dumps(stability), encoding="utf-8")
            payload = build_v072_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                profile_extension_path=str(root / "extension" / "summary.json"),
                live_run_path=str(root / "live" / "summary.json"),
                profile_stability_path=str(root / "stability" / "summary.json"),
                out_dir=str(root / "closeout_v072"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_7_2_readiness_profile_partial")

    def test_v072_invalid_when_v071_ready_chain_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v071_inputs(root, ready=False)
            build_v072_handoff_integrity(
                v071_closeout_path=str(root / "closeout" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            payload = build_v072_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                profile_extension_path=str(root / "extension" / "summary.json"),
                live_run_path=str(root / "live" / "summary.json"),
                profile_stability_path=str(root / "stability" / "summary.json"),
                out_dir=str(root / "closeout_v072"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_7_2_handoff_substrate_invalid")


if __name__ == "__main__":
    unittest.main()
