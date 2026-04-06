from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_6_1_closeout import build_v061_closeout
from gateforge.agent_modelica_v0_6_1_handoff_integrity import build_v061_handoff_integrity
from gateforge.agent_modelica_v0_6_1_live_run import build_v061_live_run
from gateforge.agent_modelica_v0_6_1_profile_adjudication import build_v061_profile_adjudication
from gateforge.agent_modelica_v0_6_1_profile_classification import build_v061_profile_classification


class AgentModelicaV061AuthorityProfileFlowTests(unittest.TestCase):
    def _write_v060_inputs(self, root: Path, *, promoted: bool = True) -> None:
        closeout = {
            "conclusion": {
                "version_decision": "v0_6_0_representative_substrate_ready",
                "representative_authority_admission": "ready",
                "can_enter_broader_authority_profile": True,
                "do_not_revert_to_v0_5_boundary_pressure_by_default": True,
            }
        }
        substrate_rows = []
        for idx in range(24):
            if idx < 12:
                slice_class = "already-covered"
            elif idx < 20:
                slice_class = "boundary-adjacent"
            else:
                slice_class = "undeclared-but-bounded-candidate"
            substrate_rows.append(
                {
                    "task_id": f"case_{idx}",
                    "family_id": "component_api_alignment" if idx < 8 else ("local_interface_alignment" if idx < 16 else "medium_redeclare_alignment"),
                    "complexity_tier": "simple" if idx % 3 == 0 else ("medium" if idx % 3 == 1 else "complex"),
                    "slice_class": slice_class,
                    "qualitative_bucket": "medium_surface" if idx in {12, 13, 18, 19} else "none",
                    "family_target_bucket": "stage_2_structural_balance_reference|undefined_symbol",
                }
            )
        substrate = {
            "representative_slice_frozen": True,
            "case_count": 24,
            "task_rows": substrate_rows,
        }
        dispatch = {
            "dispatch_cleanliness_level": "promoted" if promoted else "degraded_but_executable",
            "policy_baseline_valid": True,
        }
        classification = {
            "legacy_bucket_mapping_rate_pct": 100.0,
        }
        for rel, payload in [
            ("closeout/summary.json", closeout),
            ("substrate/summary.json", substrate),
            ("dispatch/summary.json", dispatch),
            ("classification/summary.json", classification),
        ]:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v061_reaches_ready_on_clean_representative_profile(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v060_inputs(root, promoted=True)

            build_v061_handoff_integrity(
                v060_closeout_path=str(root / "closeout" / "summary.json"),
                substrate_path=str(root / "substrate" / "summary.json"),
                dispatch_path=str(root / "dispatch" / "summary.json"),
                classification_path=str(root / "classification" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            build_v061_live_run(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                substrate_path=str(root / "substrate" / "summary.json"),
                out_dir=str(root / "live"),
            )
            build_v061_profile_classification(
                live_run_path=str(root / "live" / "summary.json"),
                out_dir=str(root / "profile"),
            )
            build_v061_profile_adjudication(
                live_run_path=str(root / "live" / "summary.json"),
                profile_classification_path=str(root / "profile" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            payload = build_v061_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                live_run_path=str(root / "live" / "summary.json"),
                profile_classification_path=str(root / "profile" / "summary.json"),
                profile_adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout_v061"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_1_authority_profile_ready")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_6_2_handoff_mode"), "widen_or_stratify_authority_profile_under_same_distribution_logic")

    def test_v061_becomes_invalid_when_upstream_dispatch_is_not_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v060_inputs(root, promoted=False)
            build_v061_handoff_integrity(
                v060_closeout_path=str(root / "closeout" / "summary.json"),
                substrate_path=str(root / "substrate" / "summary.json"),
                dispatch_path=str(root / "dispatch" / "summary.json"),
                classification_path=str(root / "classification" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            payload = build_v061_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                live_run_path=str(root / "live" / "summary.json"),
                profile_classification_path=str(root / "profile" / "summary.json"),
                profile_adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout_v061"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_6_1_handoff_substrate_invalid")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_6_2_handoff_mode"), "repair_representative_profile_substrate_first")


if __name__ == "__main__":
    unittest.main()
