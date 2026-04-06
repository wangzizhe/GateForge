from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_6_2_authority_slice import build_v062_authority_slice
from gateforge.agent_modelica_v0_6_2_closeout import build_v062_closeout
from gateforge.agent_modelica_v0_6_2_handoff_integrity import build_v062_handoff_integrity
from gateforge.agent_modelica_v0_6_2_live_run import build_v062_live_run
from gateforge.agent_modelica_v0_6_2_profile_stability import build_v062_profile_stability


class AgentModelicaV062AuthorityProfileStabilityFlowTests(unittest.TestCase):
    def _write_v061_inputs(self, root: Path, *, ready: bool = True) -> None:
        closeout = {
            "conclusion": {
                "version_decision": "v0_6_1_authority_profile_ready" if ready else "v0_6_1_authority_profile_partial",
                "profile_status": "ready" if ready else "partial",
                "primary_profile_gap": "none" if ready else "legacy_bucket_mapping_below_ready_floor",
                "do_not_reopen_v0_5_style_boundary_pressure_by_default": True,
            }
        }
        profile_adjudication = {
            "status": "PASS" if ready else "FAIL",
            "profile_status": "ready" if ready else "partial",
            "dispatch_cleanliness_level_effective": "promoted",
        }
        profile_classification = {
            "legacy_bucket_mapping_rate_pct": 100.0 if ready else 70.0,
        }
        for rel, payload in [
            ("closeout/summary.json", closeout),
            ("profile_adjudication/summary.json", profile_adjudication),
            ("profile_classification/summary.json", profile_classification),
        ]:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")

        # reuse real v0.6.0 substrate shape from current repo in tests by writing a minimal compatible file
        rows = []
        for idx in range(24):
            rows.append(
                {
                    "task_id": f"base_{idx}",
                    "family_id": "component_api_alignment" if idx < 8 else ("local_interface_alignment" if idx < 16 else "medium_redeclare_alignment"),
                    "complexity_tier": "simple" if idx % 3 == 0 else ("medium" if idx % 3 == 1 else "complex"),
                    "slice_class": "already-covered" if idx < 12 else ("boundary-adjacent" if idx < 20 else "undeclared-but-bounded-candidate"),
                    "qualitative_bucket": "fluid_network_medium_surface_pressure" if idx in {20, 21} else "none",
                    "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
                }
            )
        substrate = {
            "representative_slice_frozen": True,
            "case_count": 24,
            "task_rows": rows,
        }
        path = root / "v060_substrate" / "summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(substrate), encoding="utf-8")

    def test_v062_reaches_stable_when_widened_profile_holds(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v061_inputs(root, ready=True)
            build_v062_handoff_integrity(
                v061_closeout_path=str(root / "closeout" / "summary.json"),
                profile_adjudication_path=str(root / "profile_adjudication" / "summary.json"),
                profile_classification_path=str(root / "profile_classification" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            build_v062_authority_slice(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                substrate_path=str(root / "v060_substrate" / "summary.json"),
                out_dir=str(root / "slice"),
            )
            build_v062_live_run(
                authority_slice_path=str(root / "slice" / "summary.json"),
                out_dir=str(root / "live"),
            )
            build_v062_profile_stability(
                authority_slice_path=str(root / "slice" / "summary.json"),
                live_run_path=str(root / "live" / "summary.json"),
                out_dir=str(root / "stability"),
            )
            payload = build_v062_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                authority_slice_path=str(root / "slice" / "summary.json"),
                live_run_path=str(root / "live" / "summary.json"),
                profile_stability_path=str(root / "stability" / "summary.json"),
                out_dir=str(root / "closeout_v062"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_2_authority_profile_stable")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_6_3_handoff_mode"), "prepare_phase_level_authority_decision_inputs")

    def test_v062_becomes_invalid_when_v061_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v061_inputs(root, ready=False)
            build_v062_handoff_integrity(
                v061_closeout_path=str(root / "closeout" / "summary.json"),
                profile_adjudication_path=str(root / "profile_adjudication" / "summary.json"),
                profile_classification_path=str(root / "profile_classification" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            payload = build_v062_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                authority_slice_path=str(root / "slice" / "summary.json"),
                live_run_path=str(root / "live" / "summary.json"),
                profile_stability_path=str(root / "stability" / "summary.json"),
                out_dir=str(root / "closeout_v062"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_2_handoff_substrate_invalid")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_6_3_handoff_mode"), "repair_authority_profile_substrate_first")


if __name__ == "__main__":
    unittest.main()
