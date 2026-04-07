from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_7_4_adjudication import build_v074_adjudication
from gateforge.agent_modelica_v0_7_4_closeout import build_v074_closeout
from gateforge.agent_modelica_v0_7_4_handoff_integrity import build_v074_handoff_integrity


class AgentModelicaV074ReadinessAdjudicationFlowTests(unittest.TestCase):
    def _write_v073(self, root: Path, *, ready: bool = True, fallback: bool = False) -> None:
        payload = {
            "conclusion": {
                "version_decision": "v0_7_3_phase_decision_inputs_ready" if ready else "v0_7_3_phase_decision_inputs_partial",
                "decision_input_status": "ready" if ready else "partial",
                "stable_coverage_share_pct_stable": 39.3,
                "spillover_share_pct_stable": 17.9,
                "legacy_bucket_mapping_rate_pct_stable": 92.9,
                "complexity_pressure_profile": {
                    "dominant": "complexity:complex" if ready else "unknown",
                    "explainable": ready,
                },
                "open_world_candidate_gap_summary": "single_gap_complexity_complex_near_supported_floor",
                "v0_7_4_open_world_readiness_supported_floor": {
                    "stable_coverage_share_pct": 40.0,
                    "spillover_share_pct": 20.0,
                    "legacy_bucket_mapping_rate_pct": 80.0,
                },
                "v0_7_4_open_world_readiness_partial_floor": {
                    "stable_coverage_share_pct": 35.0,
                    "spillover_share_pct": 25.0,
                    "legacy_bucket_mapping_rate_pct": 75.0,
                },
                "v0_7_4_fallback_to_targeted_expansion_floor": {
                    "bounded_uncovered_subtype_candidate_share_pct": 15.0,
                },
            },
            "decision_input_table": {
                "bounded_uncovered_subtype_candidate_share_pct_baseline": 16.0 if fallback else 10.0,
            },
        }
        path = root / "v073" / "summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v074_reaches_partial(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v073(root, ready=True, fallback=False)
            build_v074_handoff_integrity(
                v073_closeout_path=str(root / "v073" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            build_v074_adjudication(
                v073_closeout_path=str(root / "v073" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            payload = build_v074_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                (payload.get("conclusion") or {}).get("version_decision"),
                "v0_7_4_open_world_readiness_partial_but_interpretable",
            )

    def test_v074_reaches_supported_if_supported_floor_is_met(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v073(root, ready=True, fallback=False)
            data = json.loads((root / "v073" / "summary.json").read_text(encoding="utf-8"))
            data["conclusion"]["stable_coverage_share_pct_stable"] = 40.0
            (root / "v073" / "summary.json").write_text(json.dumps(data), encoding="utf-8")
            build_v074_handoff_integrity(
                v073_closeout_path=str(root / "v073" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            build_v074_adjudication(
                v073_closeout_path=str(root / "v073" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            payload = build_v074_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                (payload.get("conclusion") or {}).get("version_decision"),
                "v0_7_4_open_world_readiness_supported",
            )

    def test_v074_reaches_fallback_when_bounded_uncovered_reemerges(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v073(root, ready=True, fallback=True)
            build_v074_handoff_integrity(
                v073_closeout_path=str(root / "v073" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            build_v074_adjudication(
                v073_closeout_path=str(root / "v073" / "summary.json"),
                out_dir=str(root / "adjudication"),
            )
            payload = build_v074_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                (payload.get("conclusion") or {}).get("version_decision"),
                "v0_7_4_fallback_to_targeted_expansion_needed",
            )

    def test_v074_invalid_when_v073_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v073(root, ready=False, fallback=False)
            build_v074_handoff_integrity(
                v073_closeout_path=str(root / "v073" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            payload = build_v074_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                adjudication_path=str(root / "adjudication" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                (payload.get("conclusion") or {}).get("version_decision"),
                "v0_7_4_handoff_substrate_invalid",
            )


if __name__ == "__main__":
    unittest.main()
