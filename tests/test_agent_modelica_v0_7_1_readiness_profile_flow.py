from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_7_1_closeout import build_v071_closeout
from gateforge.agent_modelica_v0_7_1_handoff_integrity import build_v071_handoff_integrity
from gateforge.agent_modelica_v0_7_1_live_run import build_v071_live_run
from gateforge.agent_modelica_v0_7_1_profile_adjudication import build_v071_profile_adjudication
from gateforge.agent_modelica_v0_7_1_profile_classification import build_v071_profile_classification


class AgentModelicaV071ReadinessProfileFlowTests(unittest.TestCase):
    def _write_v070_inputs(self, root: Path, *, invalid: bool = False) -> None:
        closeout = {
            "conclusion": {
                "version_decision": "v0_7_0_open_world_adjacent_substrate_ready" if not invalid else "v0_7_0_open_world_adjacent_substrate_partial",
                "substrate_admission_status": "ready" if not invalid else "partial",
                "weaker_curation_confirmed": True,
                "legacy_bucket_mapping_rate_pct": 90.9,
                "dispatch_cleanliness_level": "promoted",
                "spillover_share_pct": 18.2,
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
        ]
        substrate = {"task_rows": rows}
        for rel, payload in [
            ("closeout/summary.json", closeout),
            ("substrate/summary.json", substrate),
        ]:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v071_reaches_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v070_inputs(root)
            build_v071_handoff_integrity(
                v070_closeout_path=str(root / "closeout" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            build_v071_live_run(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                substrate_path=str(root / "substrate" / "summary.json"),
                out_dir=str(root / "live"),
            )
            build_v071_profile_classification(
                live_run_path=str(root / "live" / "summary.json"),
                out_dir=str(root / "profile"),
            )
            build_v071_profile_adjudication(
                profile_classification_path=str(root / "profile" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            payload = build_v071_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                live_run_path=str(root / "live" / "summary.json"),
                profile_classification_path=str(root / "profile" / "summary.json"),
                profile_adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout_v071"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_7_1_readiness_profile_ready")

    def test_v071_partial_when_stable_share_is_below_ready_floor(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v070_inputs(root)
            build_v071_handoff_integrity(
                v070_closeout_path=str(root / "closeout" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            build_v071_live_run(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                substrate_path=str(root / "substrate" / "summary.json"),
                out_dir=str(root / "live"),
            )
            classification = build_v071_profile_classification(
                live_run_path=str(root / "live" / "summary.json"),
                out_dir=str(root / "profile"),
            )
            classification["stable_coverage_share_pct"] = 30.0
            (root / "profile" / "summary.json").write_text(json.dumps(classification), encoding="utf-8")
            build_v071_profile_adjudication(
                profile_classification_path=str(root / "profile" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            payload = build_v071_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                live_run_path=str(root / "live" / "summary.json"),
                profile_classification_path=str(root / "profile" / "summary.json"),
                profile_adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout_v071"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_7_1_readiness_profile_partial")

    def test_v071_invalid_when_v070_ready_chain_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v070_inputs(root, invalid=True)
            build_v071_handoff_integrity(
                v070_closeout_path=str(root / "closeout" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            payload = build_v071_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                live_run_path=str(root / "live" / "summary.json"),
                profile_classification_path=str(root / "profile" / "summary.json"),
                profile_adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout_v071"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_7_1_handoff_substrate_invalid")


if __name__ == "__main__":
    unittest.main()
