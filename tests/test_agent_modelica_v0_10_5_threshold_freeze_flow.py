from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_10_5_closeout import build_v105_closeout
from gateforge.agent_modelica_v0_10_5_first_real_origin_threshold_pack import (
    PARTIAL_GOAL_ALIGNMENT_CASE_COUNT,
    PARTIAL_WORKFLOW_RESOLUTION_CASE_COUNT,
    SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT,
    SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT,
    _check_anti_tautology,
    _check_integer_safe,
    _classify_baseline,
    build_v105_first_real_origin_threshold_pack,
)
from gateforge.agent_modelica_v0_10_5_handoff_integrity import build_v105_handoff_integrity
from gateforge.agent_modelica_v0_10_5_real_origin_threshold_input_table import (
    build_v105_real_origin_threshold_input_table,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

# Baseline case counts that match the frozen v0.10.4 characterized profile:
#   12 total, 4 resolved, 2 surface_fix_only, 6 unresolved
_BASELINE_WR = 4
_BASELINE_GA = 6  # 4 resolved + 2 surface_fix_only
_BASELINE_SF = 2
_BASELINE_UN = 6
_BASELINE_TOTAL = 12


def _write_v104_closeout(
    path: Path,
    *,
    version_decision: str = "v0_10_4_first_real_origin_workflow_profile_characterized",
    profile_run_count: int = 3,
    profile_non_success_unclassified_count: int = 0,
    handoff_mode: str = "freeze_first_real_origin_workflow_thresholds",
    per_case_consistency_rate: float = 100.0,
    unexplained_flip_count: int = 0,
    workflow_resolution_rate_range: float = 0.0,
) -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "profile_run_count": profile_run_count,
            "profile_non_success_unclassified_count": profile_non_success_unclassified_count,
            "v0_10_5_handoff_mode": handoff_mode,
        },
        "real_origin_profile_replay_pack": {
            "per_case_outcome_consistency_rate_pct": per_case_consistency_rate,
            "unexplained_case_flip_count": unexplained_flip_count,
            "workflow_resolution_rate_range_pct": workflow_resolution_rate_range,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v104_characterization(
    path: Path,
    *,
    workflow_resolution_count: int = _BASELINE_WR,
    surface_fix_only_count: int = _BASELINE_SF,
    unresolved_count: int = _BASELINE_UN,
    profile_run_count: int = 3,
    profile_non_success_unclassified_count: int = 0,
) -> None:
    """Write a minimal v0.10.4 characterization summary with the given case counts."""
    total = workflow_resolution_count + surface_fix_only_count + unresolved_count
    rows = []
    for i in range(workflow_resolution_count):
        rows.append({"task_id": f"r{i}", "pilot_outcome": "goal_level_resolved", "primary_non_success_label": None})
    for i in range(surface_fix_only_count):
        rows.append(
            {
                "task_id": f"s{i}",
                "pilot_outcome": "surface_fix_only",
                "primary_non_success_label": "interface_fragility_after_surface_fix",
            }
        )
    for i in range(unresolved_count):
        rows.append(
            {
                "task_id": f"u{i}",
                "pilot_outcome": "unresolved",
                "primary_non_success_label": "extractive_conversion_chain_unresolved",
            }
        )
    payload = {
        "case_characterization_table": rows,
        "real_origin_substrate_size": total,
        "workflow_resolution_rate_pct": round(workflow_resolution_count / total * 100, 1) if total else 0.0,
        "goal_alignment_rate_pct": round((workflow_resolution_count + surface_fix_only_count) / total * 100, 1)
        if total
        else 0.0,
        "profile_run_count": profile_run_count,
        "profile_non_success_unclassified_count": profile_non_success_unclassified_count,
        "workflow_level_interpretable": True,
        "non_success_label_coverage_rate_pct": 100.0,
        "execution_source": "frozen_real_origin_substrate_deterministic_replay",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class AgentModelicaV105ThresholdFreezeFlowTests(unittest.TestCase):

    def test_handoff_integrity_passes_on_expected_v104_characterized_inputs(self) -> None:
        """Step 1: handoff integrity must pass when v0.10.4 closeout is fully characterized."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v104_closeout = root / "v104" / "closeout.json"
            _write_v104_closeout(v104_closeout)
            payload = build_v105_handoff_integrity(
                v104_closeout_path=str(v104_closeout),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")
            self.assertTrue(all(payload["checks"].values()), msg=f"Some checks failed: {payload['checks']}")

    def test_thresholds_frozen_full_happy_path(self) -> None:
        """Full pipeline with valid v0.10.4 inputs must produce thresholds_frozen decision."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v104_closeout = root / "v104" / "closeout.json"
            v104_characterization = root / "v104" / "characterization.json"
            _write_v104_closeout(v104_closeout)
            _write_v104_characterization(v104_characterization)
            payload = build_v105_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                threshold_input_table_path=str(root / "input_table" / "summary.json"),
                threshold_pack_path=str(root / "pack" / "summary.json"),
                v104_closeout_path=str(v104_closeout),
                v104_characterization_path=str(v104_characterization),
                out_dir=str(root / "closeout"),
            )
            conclusion = payload["conclusion"]
            self.assertEqual(conclusion["version_decision"], "v0_10_5_first_real_origin_workflow_thresholds_frozen")
            self.assertEqual(
                conclusion["v0_10_6_handoff_mode"],
                "adjudicate_first_real_origin_workflow_readiness_against_frozen_thresholds",
            )
            self.assertTrue(conclusion["anti_tautology_pass"])
            self.assertTrue(conclusion["integer_safe_pass"])
            self.assertEqual(
                conclusion["baseline_classification_under_frozen_pack"],
                "real_origin_workflow_readiness_partial_but_interpretable",
            )

    def test_anti_tautology_assertion_against_real_v104_baseline(self) -> None:
        """The v0.10.4 characterized baseline must not self-classify as supported.

        Concretely: 4 workflow_resolution and 6 goal_alignment on 12 cases must
        land in partial_but_interpretable, not supported.  The supported band
        must be strictly stronger on ≥1 metric.
        """
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v104_characterization = root / "v104" / "characterization.json"
            _write_v104_characterization(v104_characterization)
            # Build the threshold input table first
            build_v105_real_origin_threshold_input_table(
                v104_characterization_path=str(v104_characterization),
                out_dir=str(root / "input_table"),
            )
            pack_payload = build_v105_first_real_origin_threshold_pack(
                threshold_input_table_path=str(root / "input_table" / "summary.json"),
                out_dir=str(root / "pack"),
            )
            self.assertEqual(
                pack_payload["baseline_classification_under_frozen_pack"],
                "real_origin_workflow_readiness_partial_but_interpretable",
            )
            self.assertTrue(pack_payload["anti_tautology_pass"])
            # Verify the supported band is strictly stronger on both main metrics
            self.assertGreater(SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT, _BASELINE_WR)
            self.assertGreater(SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT, _BASELINE_GA)

    def test_integer_safe_threshold_validation(self) -> None:
        """Frozen threshold constants must satisfy the integer-safe rule (no band overlap or inversion)."""
        # Bands must not overlap: supported floor strictly above partial floor on every metric
        self.assertGreater(SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT, PARTIAL_WORKFLOW_RESOLUTION_CASE_COUNT)
        self.assertGreater(SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT, PARTIAL_GOAL_ALIGNMENT_CASE_COUNT)
        # The check function itself must return True
        self.assertTrue(_check_integer_safe())
        # Comparisons must work on integer counts: verify _classify_baseline uses counts, not floats
        self.assertEqual(
            _classify_baseline(_BASELINE_WR, _BASELINE_GA),
            "real_origin_workflow_readiness_partial_but_interpretable",
        )
        self.assertEqual(
            _classify_baseline(SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT, SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT),
            "real_origin_workflow_readiness_supported",
        )
        self.assertEqual(
            _classify_baseline(0, 0),
            "real_origin_workflow_readiness_fallback",
        )

    def test_partial_closeout_path(self) -> None:
        """Closeout must route to partial when execution-posture semantics fail.

        We force this by giving the threshold input table internally inconsistent
        case counts (goal_alignment != workflow_resolution + surface_fix_only), so
        execution_posture_semantics_preserved becomes False.  Anti-tautology and
        integer-safe still hold because the baseline is not supported.
        """
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v104_closeout = root / "v104" / "closeout.json"
            _write_v104_closeout(v104_closeout)

            # Write a characterization where counts are internally inconsistent:
            # goal_alignment is 0 even though there are resolved cases → posture check fails.
            bad_characterization = root / "v104" / "bad_characterization.json"
            bad_characterization.parent.mkdir(parents=True, exist_ok=True)
            bad_characterization.write_text(
                json.dumps(
                    {
                        "case_characterization_table": [
                            {"task_id": "r0", "pilot_outcome": "goal_level_resolved"},
                            {"task_id": "r1", "pilot_outcome": "goal_level_resolved"},
                            {"task_id": "u0", "pilot_outcome": "unresolved"},
                        ],
                        "real_origin_substrate_size": 3,
                        "profile_run_count": 3,
                        "profile_non_success_unclassified_count": 0,
                        "workflow_level_interpretable": True,
                        "non_success_label_coverage_rate_pct": 100.0,
                    }
                ),
                encoding="utf-8",
            )

            # Build input table manually to force inconsistency:
            # Override goal_alignment_case_count to be wrong (0 instead of 2)
            input_table_dir = root / "input_table"
            input_table_dir.mkdir(parents=True, exist_ok=True)
            (input_table_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "real_origin_substrate_case_count": 3,
                        "workflow_resolution_case_count": 2,
                        "goal_alignment_case_count": 0,  # intentionally wrong → posture fails
                        "surface_fix_only_case_count": 0,
                        "unresolved_case_count": 1,
                        "profile_run_count": 3,
                        "profile_non_success_unclassified_count": 0,
                    }
                ),
                encoding="utf-8",
            )

            payload = build_v105_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                threshold_input_table_path=str(input_table_dir / "summary.json"),
                threshold_pack_path=str(root / "pack" / "summary.json"),
                v104_closeout_path=str(v104_closeout),
                v104_characterization_path=str(bad_characterization),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_10_5_first_real_origin_workflow_thresholds_partial",
            )

    def test_invalid_threshold_pack_route(self) -> None:
        """Closeout must route to invalid when v0.10.4 handoff integrity fails."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v104_closeout = root / "v104" / "closeout.json"
            _write_v104_closeout(
                v104_closeout,
                version_decision="v0_10_4_real_origin_profile_inputs_invalid",
            )
            v104_characterization = root / "v104" / "characterization.json"
            _write_v104_characterization(v104_characterization)
            payload = build_v105_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                threshold_input_table_path=str(root / "input_table" / "summary.json"),
                threshold_pack_path=str(root / "pack" / "summary.json"),
                v104_closeout_path=str(v104_closeout),
                v104_characterization_path=str(v104_characterization),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(
                payload["conclusion"]["version_decision"],
                "v0_10_5_real_origin_threshold_inputs_invalid",
            )
            self.assertEqual(payload["conclusion"]["v0_10_6_handoff_mode"], "rebuild_v0_10_5_inputs_first")


if __name__ == "__main__":
    unittest.main()
