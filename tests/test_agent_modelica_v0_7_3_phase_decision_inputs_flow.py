from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_7_3_closeout import build_v073_closeout
from gateforge.agent_modelica_v0_7_3_decision_adjudication import build_v073_decision_adjudication
from gateforge.agent_modelica_v0_7_3_decision_input_table import build_v073_decision_input_table
from gateforge.agent_modelica_v0_7_3_handoff_integrity import build_v073_handoff_integrity


class AgentModelicaV073PhaseDecisionInputsFlowTests(unittest.TestCase):
    def _write_inputs(self, root: Path, *, stable: bool = True) -> None:
        v071 = {
            "conclusion": {
                "version_decision": "v0_7_1_readiness_profile_ready",
                "stable_coverage_share_pct": 40.9,
                "spillover_share_pct_after_live_run": 18.2,
                "legacy_bucket_mapping_rate_pct_after_live_run": 90.9,
                "dominant_pressure_source": "complexity:complex",
            },
            "profile_classification": {
                "bucket_counts": {
                    "covered_success": 9,
                    "covered_but_fragile": 2,
                    "dispatch_or_policy_limited": 3,
                    "bounded_uncovered_subtype_candidate": 2,
                    "topology_or_open_world_spillover": 4,
                    "unclassified_pending_taxonomy": 2,
                },
                "complexity_breakdown_after_live_run": {
                    "simple": {"stable": 5, "fragile": 0, "limited_or_uncovered": 0},
                    "medium": {"stable": 4, "fragile": 2, "limited_or_uncovered": 1},
                    "complex": {"stable": 0, "fragile": 0, "limited_or_uncovered": 10},
                },
            },
        }
        v072 = {
            "conclusion": {
                "version_decision": "v0_7_2_readiness_profile_stable" if stable else "v0_7_2_readiness_profile_partial",
                "profile_stability_status": "stable" if stable else "partial",
                "stable_coverage_share_pct_after_extension": 39.3 if stable else 32.0,
                "spillover_share_pct_after_extension": 17.9 if stable else 24.0,
                "legacy_bucket_mapping_rate_pct_after_extension": 92.9 if stable else 78.0,
                "dominant_pressure_source_after_extension": "complexity:complex" if stable else "unknown",
            },
            "profile_stability": {
                "family_breakdown_after_extension": {
                    "component_api_alignment": {"stable": 5, "fragile": 0, "limited_or_uncovered": 4},
                    "local_interface_alignment": {"stable": 4, "fragile": 2, "limited_or_uncovered": 4},
                    "medium_redeclare_alignment": {"stable": 2, "fragile": 1, "limited_or_uncovered": 6},
                },
                "complexity_breakdown_after_extension": {
                    "simple": {"stable": 6, "fragile": 0, "limited_or_uncovered": 0},
                    "medium": {"stable": 5, "fragile": 3, "limited_or_uncovered": 1},
                    "complex": {"stable": 0, "fragile": 0, "limited_or_uncovered": 13},
                },
            },
        }
        for rel, payload in [
            ("v071/summary.json", v071),
            ("v072/summary.json", v072),
        ]:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v073_reaches_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_inputs(root, stable=True)
            build_v073_handoff_integrity(
                v072_closeout_path=str(root / "v072" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            build_v073_decision_input_table(
                v071_closeout_path=str(root / "v071" / "summary.json"),
                v072_closeout_path=str(root / "v072" / "summary.json"),
                out_dir=str(root / "table"),
            )
            build_v073_decision_adjudication(
                decision_input_table_path=str(root / "table" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            payload = build_v073_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                decision_input_table_path=str(root / "table" / "summary.json"),
                decision_adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_7_3_phase_decision_inputs_ready")

    def test_v073_partial_when_table_is_interpretable_but_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_inputs(root, stable=True)
            build_v073_handoff_integrity(
                v072_closeout_path=str(root / "v072" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            table = build_v073_decision_input_table(
                v071_closeout_path=str(root / "v071" / "summary.json"),
                v072_closeout_path=str(root / "v072" / "summary.json"),
                out_dir=str(root / "table"),
            )
            table["spillover_share_pct_stable"] = 22.0
            (root / "table" / "summary.json").write_text(json.dumps(table), encoding="utf-8")
            build_v073_decision_adjudication(
                decision_input_table_path=str(root / "table" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            payload = build_v073_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                decision_input_table_path=str(root / "table" / "summary.json"),
                decision_adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_7_3_phase_decision_inputs_partial")

    def test_v073_invalid_when_v072_chain_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_inputs(root, stable=False)
            build_v073_handoff_integrity(
                v072_closeout_path=str(root / "v072" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            payload = build_v073_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                decision_input_table_path=str(root / "table" / "summary.json"),
                decision_adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual((payload.get("conclusion") or {}).get("version_decision"), "v0_7_3_handoff_substrate_invalid")


if __name__ == "__main__":
    unittest.main()
