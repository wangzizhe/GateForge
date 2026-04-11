from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_11_4_closeout import build_v114_closeout
from gateforge.agent_modelica_v0_11_4_handoff_integrity import build_v114_handoff_integrity
from gateforge.agent_modelica_v0_11_4_product_gap_threshold_input_table import (
    build_v114_product_gap_threshold_input_table,
)
from gateforge.agent_modelica_v0_11_4_product_gap_threshold_pack import (
    PARTIAL_GOAL_ALIGNMENT_CASE_COUNT,
    PARTIAL_WORKFLOW_RESOLUTION_CASE_COUNT,
    SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT,
    SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT,
    _check_anti_tautology,
    _check_integer_safe,
    _classify_baseline,
    build_v114_product_gap_threshold_pack,
)


_BASELINE_WR = 3
_BASELINE_GA = 5
_BASELINE_SF = 2
_BASELINE_UN = 7
_BASELINE_TOTAL = 12


def _write_v113_closeout(
    path: Path,
    *,
    version_decision: str = "v0_11_3_first_product_gap_profile_characterized",
    profile_run_count: int = 3,
    unclassified_count: int = 0,
    handoff_mode: str = "freeze_first_product_gap_thresholds",
) -> None:
    payload = {
        "conclusion": {
            "version_decision": version_decision,
            "first_product_gap_profile_status": "characterized",
            "v0_11_4_handoff_mode": handoff_mode,
        },
        "product_gap_profile_replay_pack": {
            "product_gap_profile_run_count": profile_run_count,
            "runtime_product_gap_evidence_completeness_pass": True,
            "observation_placeholder_fully_replaced": True,
        },
        "product_gap_profile_characterization": {
            "product_gap_non_success_unclassified_count": unclassified_count,
            "candidate_dominant_gap_family_interpretability": "interpretable",
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_v113_characterization(path: Path) -> None:
    rows = []
    for i in range(_BASELINE_WR):
        rows.append({"task_id": f"r{i}", "product_gap_outcome": "goal_level_resolved"})
    for i in range(_BASELINE_SF):
        rows.append({"task_id": f"s{i}", "product_gap_outcome": "surface_fix_only"})
    for i in range(_BASELINE_UN):
        rows.append({"task_id": f"u{i}", "product_gap_outcome": "unresolved"})
    payload = {
        "case_characterization_table": rows,
        "workflow_resolution_rate_pct": round(_BASELINE_WR / _BASELINE_TOTAL * 100, 1),
        "goal_alignment_rate_pct": round(_BASELINE_GA / _BASELINE_TOTAL * 100, 1),
        "surface_fix_only_rate_pct": round(_BASELINE_SF / _BASELINE_TOTAL * 100, 1),
        "unresolved_rate_pct": round(_BASELINE_UN / _BASELINE_TOTAL * 100, 1),
        "candidate_dominant_gap_family": "residual_core_capability_gap",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class AgentModelicaV114ProductGapThresholdFreezeFlowTests(unittest.TestCase):
    def test_handoff_integrity_passes_on_expected_v113_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v113_closeout = root / "v113" / "closeout.json"
            _write_v113_closeout(v113_closeout)
            payload = build_v114_handoff_integrity(
                v113_closeout_path=str(v113_closeout),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "PASS")

    def test_handoff_integrity_fails_on_wrong_handoff_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v113_closeout = root / "v113" / "closeout.json"
            _write_v113_closeout(v113_closeout, handoff_mode="adjudicate_first_product_gap_profile_against_frozen_thresholds")
            payload = build_v114_handoff_integrity(
                v113_closeout_path=str(v113_closeout),
                out_dir=str(root / "handoff"),
            )
            self.assertEqual(payload["handoff_integrity_status"], "FAIL")

    def test_thresholds_frozen_full_happy_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v113_closeout = root / "v113" / "closeout.json"
            v113_characterization = root / "v113" / "characterization.json"
            _write_v113_closeout(v113_closeout)
            _write_v113_characterization(v113_characterization)
            payload = build_v114_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                threshold_input_table_path=str(root / "input_table" / "summary.json"),
                threshold_pack_path=str(root / "pack" / "summary.json"),
                v113_closeout_path=str(v113_closeout),
                v113_characterization_path=str(v113_characterization),
                out_dir=str(root / "closeout"),
            )
            conclusion = payload["conclusion"]
            self.assertEqual(conclusion["version_decision"], "v0_11_4_first_product_gap_thresholds_frozen")
            self.assertEqual(conclusion["v0_11_5_handoff_mode"], "adjudicate_first_product_gap_profile_against_frozen_thresholds")
            self.assertTrue(conclusion["anti_tautology_pass"])
            self.assertTrue(conclusion["integer_safe_pass"])
            self.assertEqual(conclusion["baseline_classification_under_frozen_pack"], "product_gap_partial_but_interpretable")

    def test_anti_tautology_assertion_against_current_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v113_characterization = root / "v113" / "characterization.json"
            _write_v113_characterization(v113_characterization)
            build_v114_product_gap_threshold_input_table(
                v113_characterization_path=str(v113_characterization),
                out_dir=str(root / "input_table"),
            )
            pack_payload = build_v114_product_gap_threshold_pack(
                threshold_input_table_path=str(root / "input_table" / "summary.json"),
                out_dir=str(root / "pack"),
            )
            self.assertEqual(
                pack_payload["baseline_classification_under_frozen_pack"],
                "product_gap_partial_but_interpretable",
            )
            self.assertTrue(pack_payload["anti_tautology_pass"])
            self.assertGreater(SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT, _BASELINE_WR)
            self.assertGreater(SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT, _BASELINE_GA)

    def test_integer_safe_threshold_validation(self) -> None:
        self.assertGreater(SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT, PARTIAL_WORKFLOW_RESOLUTION_CASE_COUNT)
        self.assertGreater(SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT, PARTIAL_GOAL_ALIGNMENT_CASE_COUNT)
        self.assertTrue(_check_integer_safe())
        self.assertEqual(
            _classify_baseline(_BASELINE_WR, _BASELINE_GA),
            "product_gap_partial_but_interpretable",
        )
        self.assertEqual(
            _classify_baseline(SUPPORTED_WORKFLOW_RESOLUTION_CASE_COUNT, SUPPORTED_GOAL_ALIGNMENT_CASE_COUNT),
            "product_gap_supported",
        )

    def test_partial_closeout_path_when_integer_safe_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v113_closeout = root / "v113" / "closeout.json"
            v113_characterization = root / "v113" / "characterization.json"
            _write_v113_closeout(v113_closeout)
            _write_v113_characterization(v113_characterization)
            build_v114_handoff_integrity(
                v113_closeout_path=str(v113_closeout),
                out_dir=str(root / "handoff"),
            )
            build_v114_product_gap_threshold_input_table(
                v113_characterization_path=str(v113_characterization),
                out_dir=str(root / "input_table"),
            )
            pack = build_v114_product_gap_threshold_pack(
                threshold_input_table_path=str(root / "input_table" / "summary.json"),
                out_dir=str(root / "pack"),
            )
            pack["integer_safe_pass"] = False
            (root / "pack" / "summary.json").write_text(json.dumps(pack), encoding="utf-8")
            payload = build_v114_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                threshold_input_table_path=str(root / "input_table" / "summary.json"),
                threshold_pack_path=str(root / "pack" / "summary.json"),
                v113_closeout_path=str(v113_closeout),
                v113_characterization_path=str(v113_characterization),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_4_first_product_gap_thresholds_partial")

    def test_invalid_closeout_when_execution_posture_semantics_break(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v113_closeout = root / "v113" / "closeout.json"
            v113_characterization = root / "v113" / "characterization.json"
            _write_v113_closeout(v113_closeout)
            _write_v113_characterization(v113_characterization)
            build_v114_handoff_integrity(
                v113_closeout_path=str(v113_closeout),
                out_dir=str(root / "handoff"),
            )
            build_v114_product_gap_threshold_input_table(
                v113_characterization_path=str(v113_characterization),
                out_dir=str(root / "input_table"),
            )
            pack = build_v114_product_gap_threshold_pack(
                threshold_input_table_path=str(root / "input_table" / "summary.json"),
                out_dir=str(root / "pack"),
            )
            pack["execution_posture_semantics_preserved"] = False
            (root / "pack" / "summary.json").write_text(json.dumps(pack), encoding="utf-8")
            payload = build_v114_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                threshold_input_table_path=str(root / "input_table" / "summary.json"),
                threshold_pack_path=str(root / "pack" / "summary.json"),
                v113_closeout_path=str(v113_closeout),
                v113_characterization_path=str(v113_characterization),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_4_product_gap_threshold_inputs_invalid")

    def test_anti_tautology_failure_routes_to_invalid_not_partial(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            v113_closeout = root / "v113" / "closeout.json"
            v113_characterization = root / "v113" / "characterization.json"
            _write_v113_closeout(v113_closeout)
            _write_v113_characterization(v113_characterization)
            build_v114_handoff_integrity(
                v113_closeout_path=str(v113_closeout),
                out_dir=str(root / "handoff"),
            )
            build_v114_product_gap_threshold_input_table(
                v113_characterization_path=str(v113_characterization),
                out_dir=str(root / "input_table"),
            )
            pack = build_v114_product_gap_threshold_pack(
                threshold_input_table_path=str(root / "input_table" / "summary.json"),
                out_dir=str(root / "pack"),
            )
            pack["anti_tautology_pass"] = False
            pack["baseline_classification_under_frozen_pack"] = "product_gap_supported"
            (root / "pack" / "summary.json").write_text(json.dumps(pack), encoding="utf-8")
            payload = build_v114_closeout(
                handoff_integrity_path=str(root / "handoff" / "summary.json"),
                threshold_input_table_path=str(root / "input_table" / "summary.json"),
                threshold_pack_path=str(root / "pack" / "summary.json"),
                v113_closeout_path=str(v113_closeout),
                v113_characterization_path=str(v113_characterization),
                out_dir=str(root / "closeout"),
            )
            self.assertEqual(payload["conclusion"]["version_decision"], "v0_11_4_product_gap_threshold_inputs_invalid")


if __name__ == "__main__":
    unittest.main()
