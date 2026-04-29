from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_external_strategy_source_synthesis_v0_33_4 import (
    build_external_strategy_source_synthesis,
)


def _write_run(root: Path, *, case_id: str, verdict: str, submitted: bool) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "summary.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    row = {
        "case_id": case_id,
        "final_verdict": verdict,
        "submitted": submitted,
        "step_count": 3,
        "provider_error": "",
        "steps": [
            {"tool_calls": [{"name": "check_model", "arguments": {"model_text": "model X end X;"}}]},
            {"tool_calls": [{"name": "simulate_model", "arguments": {"model_text": "model X end X;"}}]},
            {"tool_calls": [{"name": "submit_final", "arguments": {"model_text": "model X end X;"}}]}
            if submitted
            else {"tool_calls": []},
        ],
    }
    (root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class ExternalStrategySourceSynthesisV0334Tests(unittest.TestCase):
    def test_build_summary_detects_strategy_specificity_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            high = root / "high"
            worked = root / "worked"
            library_a = root / "library_a"
            library_b = root / "library_b"
            case_id = "sem_19_arrayed_shared_probe_bus"
            _write_run(high, case_id=case_id, verdict="FAILED", submitted=False)
            _write_run(worked, case_id=case_id, verdict="FAILED", submitted=False)
            _write_run(library_a, case_id=case_id, verdict="PASS", submitted=True)
            _write_run(library_b, case_id=case_id, verdict="PASS", submitted=True)

            summary = build_external_strategy_source_synthesis(
                run_specs=[
                    {"run_id": "high", "source_class": "high_level_strategy_source", "path": high},
                    {"run_id": "worked", "source_class": "worked_strategy_source", "path": worked},
                    {
                        "run_id": "library_a",
                        "source_class": "library_semantic_strategy_source",
                        "path": library_a,
                    },
                    {
                        "run_id": "library_b",
                        "source_class": "library_semantic_strategy_source",
                        "path": library_b,
                    },
                ],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "strategy_source_specificity_changes_candidate_discovery")
            self.assertFalse(summary["discipline"]["wrapper_patch_generated"])

    def test_missing_runs_make_summary_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_external_strategy_source_synthesis(
                run_specs=[{"run_id": "missing", "source_class": "x", "path": root / "missing"}],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")
            self.assertEqual(summary["missing_runs"], ["missing"])


if __name__ == "__main__":
    unittest.main()
