from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_deepseek_three_round_slice_v0_27_3 import run_deepseek_three_round_slice


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


class DeepSeekThreeRoundSliceV0273Tests(unittest.TestCase):
    def test_run_three_round_slice_preserves_only_round_budget_change(self) -> None:
        def check_fn(text: str, _model_name: str):
            return ("fixed" in text), "none" if "fixed" in text else "model_check_error"

        calls: list[int] = []

        def repair_fn(**kwargs):
            calls.append(int(kwargs["current_round"]))
            if int(kwargs["current_round"]) >= 3:
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
            summary = run_deepseek_three_round_slice(
                out_dir=root / "out",
                manifest_rows_path=manifest,
                v0226_candidates_path=candidates,
                v0228_admitted_path=admitted,
                limit=1,
                check_fn=check_fn,
                repair_fn=repair_fn,
            )
            self.assertEqual(summary["version"], "v0.27.3")
            self.assertEqual(summary["max_rounds"], 3)
            self.assertEqual(summary["changed_variable"], "max_rounds_only")
            self.assertEqual(summary["pass_count"], 1)
            self.assertEqual(calls, [1, 2, 3])
            persisted = json.loads((root / "out" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(persisted["version"], "v0.27.3")


if __name__ == "__main__":
    unittest.main()
