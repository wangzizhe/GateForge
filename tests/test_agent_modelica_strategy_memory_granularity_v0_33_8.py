from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_strategy_memory_granularity_v0_33_8 import build_strategy_memory_granularity


def _write_run(root: Path, *, case_id: str, verdict: str, model_text: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    row = {
        "case_id": case_id,
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "provider_error": "",
        "token_used": 10,
        "step_count": 2,
        "steps": [
            {
                "tool_calls": [{"name": "check_model", "arguments": {"model_text": model_text}}],
                "tool_results": [{"name": "check_model", "result": 'resultFile = "/workspace/X.mat"' if verdict == "PASS" else "failed"}],
            }
        ],
    }
    (root / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


class StrategyMemoryGranularityV0338Tests(unittest.TestCase):
    def test_boundary_specific_granularity_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            broad = root / "broad"
            specific_a = root / "specific_a"
            specific_b = root / "specific_b"
            generic = root / "generic"
            case_id = "sem_19_arrayed_shared_probe_bus"
            _write_run(broad, case_id=case_id, verdict="FAILED", model_text="model X equation p[1].i = 0; end X;")
            _write_run(generic, case_id=case_id, verdict="FAILED", model_text="model X equation p[1].i = 0; end X;")
            _write_run(
                specific_a,
                case_id=case_id,
                verdict="PASS",
                model_text="model X Modelica.Electrical.Analog.Basic.Resistor r; equation readings[1] = 1; end X;",
            )
            _write_run(
                specific_b,
                case_id=case_id,
                verdict="PASS",
                model_text="model X equation p[1].i = 0; readings[1] = 1; end X;",
            )
            summary = build_strategy_memory_granularity(
                run_specs=[
                    {"run_id": "broad", "granularity": "broad_strategy_note", "path": broad},
                    {"run_id": "generic", "granularity": "generic_strategy_cards", "path": generic},
                    {"run_id": "specific_a", "granularity": "semantic_specific_strategy_source", "path": specific_a},
                    {"run_id": "specific_b", "granularity": "semantic_specific_strategy_source", "path": specific_b},
                ],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["decision"], "semantic_memory_needs_boundary_specific_granularity")
            self.assertFalse(summary["discipline"]["private_context_text_exported"])

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_strategy_memory_granularity(
                run_specs=[{"run_id": "missing", "granularity": "x", "path": root / "missing"}],
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
