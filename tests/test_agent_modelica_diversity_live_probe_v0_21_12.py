from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_diversity_live_probe_v0_21_12 import (
    build_ab_summary,
    build_context_block,
    run_diversity_live_probe,
    run_first_turn_probe,
)


def _case(model_path: Path) -> dict:
    return {
        "candidate_id": "v0218_001_measurement_abstraction_partial_M",
        "task_id": "v0218_001_measurement_abstraction_partial_M",
        "mutation_family": "measurement_abstraction_partial",
        "mutated_model_path": str(model_path),
        "failure_type": "ET03",
        "expected_stage": "check",
        "workflow_goal": "repair model",
        "planner_backend": "gemini",
    }


def _repair_fn(**kwargs):
    base = str(kwargs.get("original_text") or "")
    context = str(kwargs.get("context_block") or "")
    if context:
        return [
            {"patched_text": base + f"\n  Real diverse{i};", "llm_error": "", "provider": "gemini", "temperature_used": i}
            for i in range(5)
        ]
    return [
        {"patched_text": base + "\n  Real same;", "llm_error": "", "provider": "gemini", "temperature_used": i}
        for i in range(5)
    ]


def _check_fn(text: str, model_name: str) -> tuple[bool, str]:
    return ("diverse0" in text), "omc output"


def _simulate_fn(text: str, model_name: str) -> tuple[bool, bool, str]:
    ok = "diverse0" in text
    return ok, ok, "sim output"


class DiversityLiveProbeV02112Tests(unittest.TestCase):
    def test_build_context_block_uses_safe_generic_profile(self) -> None:
        context, label = build_context_block("diversity-c5")

        self.assertIn("structurally distinct", context)
        self.assertIn("Do not use hidden benchmark metadata", context)
        self.assertEqual(label, "Candidate diversity profile")

    def test_run_first_turn_probe_records_diversity_gain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "M.mo"
            model_path.write_text("model M\nequation\nend M;", encoding="utf-8")

            row = run_first_turn_probe(
                _case(model_path),
                mode="diversity-c5",
                repair_fn=_repair_fn,
                check_fn=_check_fn,
                simulate_fn=_simulate_fn,
            )

            self.assertTrue(row["context_profile_enabled"])
            self.assertTrue(row["first_turn_any_check_pass"])
            self.assertGreater(row["diversity"]["structural_uniqueness_rate"], 0.0)

    def test_build_ab_summary_detects_structural_gain(self) -> None:
        rows = [
            {
                "mode": "standard-c5",
                "first_turn_any_check_pass": False,
                "first_turn_any_simulate_pass": False,
                "diversity": {"structural_uniqueness_rate": 0.2, "text_uniqueness_rate": 0.2},
            },
            {
                "mode": "diversity-c5",
                "first_turn_any_check_pass": True,
                "first_turn_any_simulate_pass": True,
                "diversity": {"structural_uniqueness_rate": 0.8, "text_uniqueness_rate": 1.0},
            },
        ]

        summary = build_ab_summary(rows)

        self.assertEqual(summary["conclusion"], "diversity_profile_changed_candidates_and_improved_first_turn_signal")

    def test_run_diversity_live_probe_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_path = root / "M.mo"
            benchmark = root / "benchmark.jsonl"
            out_dir = root / "out"
            model_path.write_text("model M\nequation\nend M;", encoding="utf-8")
            benchmark.write_text(json.dumps(_case(model_path)) + "\n", encoding="utf-8")

            summary = run_diversity_live_probe(
                benchmark_path=benchmark,
                out_dir=out_dir,
                modes=["standard-c5", "diversity-c5"],
                repair_fn=_repair_fn,
                check_fn=_check_fn,
                simulate_fn=_simulate_fn,
            )

            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "probe_rows.jsonl").exists())
            self.assertTrue((out_dir / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
