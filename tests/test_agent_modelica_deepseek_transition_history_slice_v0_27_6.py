from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_deepseek_transition_history_slice_v0_27_6 import (
    run_deepseek_transition_history_slice,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


class DeepSeekTransitionHistorySliceV0276Tests(unittest.TestCase):
    def test_run_transition_history_slice_marks_changed_variable(self) -> None:
        def check_fn(text: str, _model_name: str):
            ok = "fixed" in text
            return ok, ok, "none" if ok else "model_check_error"

        seen_history: list[list[dict]] = []

        def repair_fn(**kwargs):
            seen_history.append(list(kwargs.get("repair_history") or []))
            if int(kwargs["current_round"]) >= 2:
                return "model Demo\n  Real fixed;\nequation\n  fixed = 1;\nend Demo;\n", "", "deepseek"
            return "model Demo\n  Real x;\nend Demo;\n", "", "deepseek"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.mo"
            mutated = root / "mutated.mo"
            source.write_text("model Demo\n  Real x;\nequation\n  x = 1;\nend Demo;\n", encoding="utf-8")
            mutated.write_text("model Demo\n  Real x;\nend Demo;\n", encoding="utf-8")
            manifest = root / "manifest.jsonl"
            candidates = root / "candidates.jsonl"
            admitted = root / "admitted.jsonl"
            _write_jsonl(manifest, [{"candidate_id": "c1", "split": "positive", "mutation_family": "family"}])
            _write_jsonl(candidates, [{"candidate_id": "c1", "target_model_name": "Demo", "target_model_path": str(mutated), "source_model_path": str(source)}])
            _write_jsonl(admitted, [])
            summary = run_deepseek_transition_history_slice(
                out_dir=root / "out",
                manifest_rows_path=manifest,
                v0226_candidates_path=candidates,
                v0228_admitted_path=admitted,
                limit=1,
                max_rounds=3,
                check_fn=check_fn,
                repair_fn=repair_fn,
            )
            self.assertEqual(summary["version"], "v0.27.6")
            self.assertEqual(summary["changed_variable"], "repair_history_transition_contract")
            self.assertEqual(summary["pass_count"], 1)
            self.assertIn("input_omc_summary", seen_history[1][0])
            self.assertIn("post_patch_omc_summary", seen_history[1][0])


if __name__ == "__main__":
    unittest.main()
