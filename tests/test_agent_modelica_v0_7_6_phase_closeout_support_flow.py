from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_7_6_closeout import build_v076_closeout
from gateforge.agent_modelica_v0_7_6_handoff_integrity import build_v076_handoff_integrity
from gateforge.agent_modelica_v0_7_6_late_phase_support import build_v076_late_phase_support


class AgentModelicaV076PhaseCloseoutSupportFlowTests(unittest.TestCase):
    def _write_v074(self, root: Path, *, partial: bool = True, fallback: bool = False) -> None:
        payload = {
            "conclusion": {
                "version_decision": (
                    "v0_7_4_open_world_readiness_partial_but_interpretable"
                    if partial
                    else "v0_7_4_handoff_substrate_invalid"
                ),
                "readiness_adjudication_status": "partial_but_interpretable" if partial else "invalid",
                "supported_floor_passed": False,
                "partial_floor_passed": partial,
                "fallback_floor_passed": fallback,
                "bounded_uncovered_subtype_candidate_share_pct_reference": 10.0 if partial else None,
                "dominant_pressure_source_reference": "complexity:complex" if partial else None,
            }
        }
        path = root / "v074" / "summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_v075(
        self,
        root: Path,
        *,
        partial: bool = True,
        remaining_gap_count: int = 1,
        stable_margin: float = -0.7,
        bounded_uncovered: bool = True,
        dominant_gap: str = "stable_coverage_below_supported_floor",
    ) -> None:
        payload = {
            "conclusion": {
                "version_decision": (
                    "v0_7_5_open_world_readiness_partial_but_interpretable"
                    if partial
                    else "v0_7_5_handoff_substrate_invalid"
                ),
                "readiness_refinement_status": "partial_but_interpretable" if partial else "invalid",
                "stable_coverage_margin_vs_supported_floor_pct": stable_margin,
                "spillover_margin_vs_supported_floor_pct": -2.1,
                "legacy_mapping_margin_vs_supported_floor_pct": 12.9,
                "bounded_uncovered_still_subcritical": bounded_uncovered,
                "dominant_remaining_gap_after_refinement": dominant_gap,
                "remaining_gap_count_after_refinement": remaining_gap_count,
            }
        }
        path = root / "v075" / "summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_v076_reaches_phase_closeout_supported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v074(root, partial=True, fallback=False)
            self._write_v075(root, partial=True, stable_margin=-0.7)
            build_v076_handoff_integrity(
                v075_closeout_path=str(root / "v075" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            build_v076_late_phase_support(
                v075_closeout_path=str(root / "v075" / "summary.json"),
                v074_closeout_path=str(root / "v074" / "summary.json"),
                out_dir=str(root / "support"),
            )
            payload = build_v076_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                late_phase_support_path=str(root / "support" / "summary.json"),
                v075_closeout_path=str(root / "v075" / "summary.json"),
                v074_closeout_path=str(root / "v074" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                (payload.get("conclusion") or {}).get("version_decision"),
                "v0_7_6_phase_closeout_supported",
            )

    def test_v076_stays_partial_if_gap_is_too_large(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v074(root, partial=True, fallback=False)
            self._write_v075(root, partial=True, stable_margin=-3.5)
            build_v076_handoff_integrity(
                v075_closeout_path=str(root / "v075" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            build_v076_late_phase_support(
                v075_closeout_path=str(root / "v075" / "summary.json"),
                v074_closeout_path=str(root / "v074" / "summary.json"),
                out_dir=str(root / "support"),
            )
            payload = build_v076_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                late_phase_support_path=str(root / "support" / "summary.json"),
                v075_closeout_path=str(root / "v075" / "summary.json"),
                v074_closeout_path=str(root / "v074" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                (payload.get("conclusion") or {}).get("version_decision"),
                "v0_7_6_open_world_readiness_partial_but_interpretable",
            )

    def test_v076_invalid_when_upstream_chain_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_v074(root, partial=True, fallback=False)
            self._write_v075(root, partial=True, remaining_gap_count=2)
            build_v076_handoff_integrity(
                v075_closeout_path=str(root / "v075" / "summary.json"),
                out_dir=str(root / "integrity"),
            )
            payload = build_v076_closeout(
                handoff_integrity_path=str(root / "integrity" / "summary.json"),
                late_phase_support_path=str(root / "support" / "summary.json"),
                v075_closeout_path=str(root / "v075" / "summary.json"),
                v074_closeout_path=str(root / "v074" / "summary.json"),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                (payload.get("conclusion") or {}).get("version_decision"),
                "v0_7_6_handoff_substrate_invalid",
            )


if __name__ == "__main__":
    unittest.main()
