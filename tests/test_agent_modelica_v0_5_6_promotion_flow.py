from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_5_6_closeout import build_v056_closeout
from gateforge.agent_modelica_v0_5_6_handoff_integrity import build_v056_handoff_integrity
from gateforge.agent_modelica_v0_5_6_promotion_adjudication import build_v056_promotion_adjudication
from gateforge.agent_modelica_v0_5_6_promotion_criteria import build_v056_promotion_criteria


class AgentModelicaV056PromotionFlowTests(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_chain(self, root: Path, *, widened_ready: bool = True, correct_entry: bool = True) -> dict[str, Path]:
        v052 = root / "v052.json"
        v052_spec = root / "v052_spec.json"
        v053 = root / "v053.json"
        v053_fix = root / "v053_fix.json"
        v054 = root / "v054.json"
        v054_discovery = root / "v054_discovery.json"
        v055 = root / "v055.json"
        v055_adjudication = root / "v055_adjudication.json"
        v055_execution = root / "v055_execution.json"
        entry_pattern = "medium_redeclare_alignment.fluid_network_medium_surface_pressure" if correct_entry else "other.entry"

        self._write_json(
            v052,
            {"conclusion": {"selected_entry_pattern_id": entry_pattern, "entry_ready": True}},
        )
        self._write_json(
            v052_spec,
            {
                "allowed_patch_types": [
                    "replace_redeclare_medium_package_path",
                    "align_local_medium_redeclare_clause",
                ],
                "anti_expansion_boundary_rules": [
                    "disallow topology-heavy patch or cross-component network rewrite",
                    "disallow cross-stage scope expansion beyond local medium redeclare alignment",
                ],
            },
        )
        self._write_json(v053, {"conclusion": {"entry_pattern_id": entry_pattern, "first_fix_ready": True}})
        self._write_json(v053_fix, {"first_fix_ready": True})
        self._write_json(v054, {"conclusion": {"entry_pattern_id": entry_pattern, "discovery_ready": True}})
        self._write_json(v054_discovery, {"discovery_ready": True})
        self._write_json(
            v055,
            {
                "conclusion": {
                    "entry_pattern_id": entry_pattern,
                    "widened_ready": widened_ready,
                    "branch_status": "widened_and_stable" if widened_ready else "not_ready_under_widening",
                },
                "widened_manifest": {"active_single_task_count": 8},
            },
        )
        self._write_json(v055_adjudication, {"widened_ready": widened_ready})
        self._write_json(
            v055_execution,
            {
                "scope_creep_rate_pct": 0.0,
                "second_residual_bounded_rate_pct": 100.0 if widened_ready else 0.0,
            },
        )
        return {
            "v052": v052,
            "v052_spec": v052_spec,
            "v053": v053,
            "v053_fix": v053_fix,
            "v054": v054,
            "v054_discovery": v054_discovery,
            "v055": v055,
            "v055_adjudication": v055_adjudication,
            "v055_execution": v055_execution,
        }

    def test_v056_reports_family_level_promotion_supported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = self._write_chain(root, widened_ready=True, correct_entry=True)
            build_v056_handoff_integrity(
                v0_5_2_closeout_path=str(paths["v052"]),
                v0_5_2_entry_spec_path=str(paths["v052_spec"]),
                v0_5_3_closeout_path=str(paths["v053"]),
                v0_5_3_first_fix_path=str(paths["v053_fix"]),
                v0_5_4_closeout_path=str(paths["v054"]),
                v0_5_4_discovery_path=str(paths["v054_discovery"]),
                v0_5_5_closeout_path=str(paths["v055"]),
                v0_5_5_widened_adjudication_path=str(paths["v055_adjudication"]),
                v0_5_5_widened_execution_path=str(paths["v055_execution"]),
                out_dir=str(root / "integrity"),
            )
            build_v056_promotion_criteria(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                out_dir=str(root / "criteria"),
            )
            build_v056_promotion_adjudication(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                promotion_criteria_path=str(root / "criteria" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            payload = build_v056_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                promotion_criteria_path=str(root / "criteria" / "summary.json"),
                promotion_adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_5_6_family_level_promotion_supported")
            self.assertEqual((payload.get("conclusion") or {}).get("recommended_promotion_level"), "family_extension_supported")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_5_7_handoff_mode"), "run_phase_synthesis_with_promoted_branch")

    def test_v056_reports_handoff_invalid_when_evidence_chain_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = self._write_chain(root, widened_ready=True, correct_entry=False)
            build_v056_handoff_integrity(
                v0_5_2_closeout_path=str(paths["v052"]),
                v0_5_2_entry_spec_path=str(paths["v052_spec"]),
                v0_5_3_closeout_path=str(paths["v053"]),
                v0_5_3_first_fix_path=str(paths["v053_fix"]),
                v0_5_4_closeout_path=str(paths["v054"]),
                v0_5_4_discovery_path=str(paths["v054_discovery"]),
                v0_5_5_closeout_path=str(paths["v055"]),
                v0_5_5_widened_adjudication_path=str(paths["v055_adjudication"]),
                v0_5_5_widened_execution_path=str(paths["v055_execution"]),
                out_dir=str(root / "integrity"),
            )
            build_v056_promotion_criteria(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                out_dir=str(root / "criteria"),
            )
            build_v056_promotion_adjudication(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                promotion_criteria_path=str(root / "criteria" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            payload = build_v056_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                promotion_criteria_path=str(root / "criteria" / "summary.json"),
                promotion_adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_5_6_handoff_substrate_invalid")
            self.assertEqual((payload.get("conclusion") or {}).get("v0_5_7_handoff_mode"), "return_to_boundary_mapping_for_reassessment")


if __name__ == "__main__":
    unittest.main()
