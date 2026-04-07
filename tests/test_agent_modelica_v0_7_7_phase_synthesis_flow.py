from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_7_7_closeout import build_v077_closeout
from gateforge.agent_modelica_v0_7_7_phase_ledger import build_v077_phase_ledger
from gateforge.agent_modelica_v0_7_7_stop_condition import build_v077_stop_condition


def _write_closeout(path: Path, version_decision: str, extra: dict | None = None) -> None:
    payload: dict = {"conclusion": {"version_decision": version_decision}}
    if extra:
        payload["conclusion"].update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_standard_chain(root: Path) -> dict[str, Path]:
    paths = {
        "v070": root / "v070" / "summary.json",
        "v071": root / "v071" / "summary.json",
        "v072": root / "v072" / "summary.json",
        "v073": root / "v073" / "summary.json",
        "v074": root / "v074" / "summary.json",
        "v075": root / "v075" / "summary.json",
        "v076": root / "v076" / "summary.json",
    }
    _write_closeout(
        paths["v070"],
        "v0_7_0_open_world_adjacent_substrate_ready",
        {
            "substrate_admission_status": "ready",
            "weaker_curation_confirmed": True,
            "legacy_bucket_mapping_rate_pct": 78.0,
        },
    )
    _write_closeout(paths["v071"], "v0_7_1_readiness_profile_ready")
    _write_closeout(paths["v072"], "v0_7_2_readiness_profile_stable")
    _write_closeout(paths["v073"], "v0_7_3_phase_decision_inputs_ready")
    _write_closeout(
        paths["v074"],
        "v0_7_4_open_world_readiness_partial_but_interpretable",
        {
            "readiness_adjudication_status": "partial_but_interpretable",
            "supported_floor_passed": False,
            "partial_floor_passed": True,
            "fallback_floor_passed": False,
        },
    )
    _write_closeout(
        paths["v075"],
        "v0_7_5_open_world_readiness_partial_but_interpretable",
        {
            "readiness_refinement_status": "partial_but_interpretable",
            "stable_coverage_margin_vs_supported_floor_pct": -0.7,
            "spillover_margin_vs_supported_floor_pct": -1.1,
            "legacy_mapping_margin_vs_supported_floor_pct": 12.9,
            "bounded_uncovered_still_subcritical": True,
            "dominant_remaining_gap_after_refinement": "stable_coverage_below_supported_floor",
            "remaining_gap_count_after_refinement": 1,
        },
    )
    _write_closeout(
        paths["v076"],
        "v0_7_6_phase_closeout_supported",
        {
            "late_phase_support_status": "phase_closeout_supported",
            "gap_magnitude_pct": 0.7,
            "gap_magnitude_small_enough_for_closeout_support": True,
        },
    )
    return paths


class AgentModelicaV077PhaseSynthesisFlowTests(unittest.TestCase):
    def test_phase_ledger_passes_with_correct_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v077_phase_ledger(
                v070_closeout_path=str(paths["v070"]),
                v071_closeout_path=str(paths["v071"]),
                v072_closeout_path=str(paths["v072"]),
                v073_closeout_path=str(paths["v073"]),
                v074_closeout_path=str(paths["v074"]),
                v075_closeout_path=str(paths["v075"]),
                v076_closeout_path=str(paths["v076"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["phase_ledger_integrity_status"], "PASS")

    def test_phase_ledger_fails_when_one_version_wrong(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            # Corrupt v0.7.6 to a wrong decision.
            _write_closeout(
                paths["v076"],
                "v0_7_6_open_world_readiness_partial_but_interpretable",
                {"late_phase_support_status": "partial_but_interpretable"},
            )
            payload = build_v077_phase_ledger(
                v070_closeout_path=str(paths["v070"]),
                v071_closeout_path=str(paths["v071"]),
                v072_closeout_path=str(paths["v072"]),
                v073_closeout_path=str(paths["v073"]),
                v074_closeout_path=str(paths["v074"]),
                v075_closeout_path=str(paths["v075"]),
                v076_closeout_path=str(paths["v076"]),
                out_dir=str(root / "ledger"),
            )
            self.assertEqual(payload["status"], "FAIL")

    def test_stop_condition_met_with_standard_chain(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            payload = build_v077_stop_condition(
                v070_closeout_path=str(paths["v070"]),
                v071_closeout_path=str(paths["v071"]),
                v072_closeout_path=str(paths["v072"]),
                v074_closeout_path=str(paths["v074"]),
                v076_closeout_path=str(paths["v076"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "phase_stop_condition_met")
            self.assertTrue(payload["weaker_curated_substrate_supported"])
            self.assertTrue(payload["readiness_profile_supported"])
            self.assertTrue(payload["legacy_taxonomy_dominant_enough"])
            self.assertTrue(payload["fallback_not_triggered"])
            self.assertTrue(payload["late_phase_closeout_supported"])

    def test_stop_condition_nearly_complete_when_late_phase_not_supported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            # Override v0.7.6 to partial_but_interpretable.
            _write_closeout(
                paths["v076"],
                "v0_7_6_open_world_readiness_partial_but_interpretable",
                {
                    "late_phase_support_status": "partial_but_interpretable",
                    "gap_magnitude_pct": 3.5,
                    "gap_magnitude_small_enough_for_closeout_support": False,
                },
            )
            payload = build_v077_stop_condition(
                v070_closeout_path=str(paths["v070"]),
                v071_closeout_path=str(paths["v071"]),
                v072_closeout_path=str(paths["v072"]),
                v074_closeout_path=str(paths["v074"]),
                v076_closeout_path=str(paths["v076"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "nearly_complete_with_caveat")

    def test_stop_condition_not_ready_when_substrate_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            # Override v0.7.0 to partial (not ready).
            _write_closeout(
                paths["v070"],
                "v0_7_0_open_world_adjacent_substrate_partial",
                {
                    "substrate_admission_status": "partial",
                    "weaker_curation_confirmed": True,
                    "legacy_bucket_mapping_rate_pct": 78.0,
                },
            )
            payload = build_v077_stop_condition(
                v070_closeout_path=str(paths["v070"]),
                v071_closeout_path=str(paths["v071"]),
                v072_closeout_path=str(paths["v072"]),
                v074_closeout_path=str(paths["v074"]),
                v076_closeout_path=str(paths["v076"]),
                out_dir=str(root / "stop"),
            )
            self.assertEqual(payload["phase_stop_condition_status"], "not_ready_for_closeout")

    def test_closeout_reaches_phase_complete(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            build_v077_phase_ledger(
                v070_closeout_path=str(paths["v070"]),
                v071_closeout_path=str(paths["v071"]),
                v072_closeout_path=str(paths["v072"]),
                v073_closeout_path=str(paths["v073"]),
                v074_closeout_path=str(paths["v074"]),
                v075_closeout_path=str(paths["v075"]),
                v076_closeout_path=str(paths["v076"]),
                out_dir=str(root / "ledger"),
            )
            build_v077_stop_condition(
                v070_closeout_path=str(paths["v070"]),
                v071_closeout_path=str(paths["v071"]),
                v072_closeout_path=str(paths["v072"]),
                v074_closeout_path=str(paths["v074"]),
                v076_closeout_path=str(paths["v076"]),
                out_dir=str(root / "stop"),
            )
            payload = build_v077_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "synthesis" / "summary.json"),
                v070_closeout_path=str(paths["v070"]),
                v071_closeout_path=str(paths["v071"]),
                v072_closeout_path=str(paths["v072"]),
                v073_closeout_path=str(paths["v073"]),
                v074_closeout_path=str(paths["v074"]),
                v075_closeout_path=str(paths["v075"]),
                v076_closeout_path=str(paths["v076"]),
                out_dir=str(root / "closeout"),
            )
            conclusion = payload.get("conclusion") or {}
            self.assertEqual(conclusion.get("version_decision"), "v0_7_phase_complete_prepare_v0_8")
            self.assertEqual(conclusion.get("phase_status"), "complete")
            self.assertTrue(conclusion.get("phase_primary_question_answered"))
            self.assertTrue(conclusion.get("deferred_questions_non_blocking"))
            self.assertEqual(conclusion.get("v0_8_handoff_mode"), "run_v0_8_phase_synthesis")
            self.assertTrue(conclusion.get("do_not_continue_v0_7_same_logic_refinement_by_default"))
            spec = conclusion.get("v0_8_handoff_spec") or {}
            self.assertEqual(
                spec.get("v0_8_primary_phase_question"),
                "workflow_proximal_readiness_evaluation",
            )

    def test_closeout_rebuilds_stale_phase_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            import json as _json

            root = Path(d)
            paths = _write_standard_chain(root)

            stale_ledger_path = root / "ledger" / "summary.json"
            stale_ledger_path.parent.mkdir(parents=True, exist_ok=True)
            stale_ledger_path.write_text(
                _json.dumps(
                    {
                        "phase_ledger_integrity_status": "FAIL",
                        "per_version_checks": {
                            "v0.7.6": {
                                "expected_version_decision": "v0_7_6_phase_closeout_supported",
                                "actual_version_decision": "v0_7_6_open_world_readiness_partial_but_interpretable",
                                "check_passed": False,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            payload = build_v077_closeout(
                phase_ledger_path=str(stale_ledger_path),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "synthesis" / "summary.json"),
                v070_closeout_path=str(paths["v070"]),
                v071_closeout_path=str(paths["v071"]),
                v072_closeout_path=str(paths["v072"]),
                v073_closeout_path=str(paths["v073"]),
                v074_closeout_path=str(paths["v074"]),
                v075_closeout_path=str(paths["v075"]),
                v076_closeout_path=str(paths["v076"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                (payload.get("conclusion") or {}).get("version_decision"),
                "v0_7_phase_complete_prepare_v0_8",
            )

    def test_closeout_invalid_when_ledger_fails(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = _write_standard_chain(root)
            # Break the ledger by corrupting v0.7.6.
            _write_closeout(
                paths["v076"],
                "v0_7_6_open_world_readiness_partial_but_interpretable",
                {"late_phase_support_status": "partial_but_interpretable"},
            )
            build_v077_phase_ledger(
                v070_closeout_path=str(paths["v070"]),
                v071_closeout_path=str(paths["v071"]),
                v072_closeout_path=str(paths["v072"]),
                v073_closeout_path=str(paths["v073"]),
                v074_closeout_path=str(paths["v074"]),
                v075_closeout_path=str(paths["v075"]),
                v076_closeout_path=str(paths["v076"]),
                out_dir=str(root / "ledger"),
            )
            payload = build_v077_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(root / "stop" / "summary.json"),
                meaning_synthesis_path=str(root / "synthesis" / "summary.json"),
                v070_closeout_path=str(paths["v070"]),
                v071_closeout_path=str(paths["v071"]),
                v072_closeout_path=str(paths["v072"]),
                v073_closeout_path=str(paths["v073"]),
                v074_closeout_path=str(paths["v074"]),
                v075_closeout_path=str(paths["v075"]),
                v076_closeout_path=str(paths["v076"]),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                (payload.get("conclusion") or {}).get("version_decision"),
                "v0_7_7_handoff_substrate_invalid",
            )

    def test_closeout_refresh_makes_standard_chain_phase_complete(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            import json as _json

            root = Path(d)
            paths = _write_standard_chain(root)

            # Seed a stale nearly-complete stop artifact; closeout should ignore it and
            # rebuild from upstream chain.
            stop_path = root / "stop" / "summary.json"
            stop_path.parent.mkdir(parents=True, exist_ok=True)
            stop_path.write_text(
                _json.dumps(
                    {
                        "phase_stop_condition_status": "nearly_complete_with_caveat",
                        "weaker_curated_substrate_supported": True,
                        "readiness_profile_supported": True,
                        "legacy_taxonomy_dominant_enough": True,
                        "fallback_not_triggered": True,
                        "late_phase_closeout_supported": False,
                    }
                ),
                encoding="utf-8",
            )

            payload = build_v077_closeout(
                phase_ledger_path=str(root / "ledger" / "summary.json"),
                stop_condition_path=str(stop_path),
                meaning_synthesis_path=str(root / "synthesis" / "summary.json"),
                v070_closeout_path=str(paths["v070"]),
                v071_closeout_path=str(paths["v071"]),
                v072_closeout_path=str(paths["v072"]),
                v073_closeout_path=str(paths["v073"]),
                v074_closeout_path=str(paths["v074"]),
                v075_closeout_path=str(paths["v075"]),
                v076_closeout_path=str(paths["v076"]),
                out_dir=str(root / "closeout"),
            )
            conclusion = payload.get("conclusion") or {}
            self.assertEqual(
                conclusion.get("version_decision"),
                "v0_7_phase_complete_prepare_v0_8",
            )
            self.assertEqual(conclusion.get("phase_status"), "complete")


if __name__ == "__main__":
    unittest.main()
