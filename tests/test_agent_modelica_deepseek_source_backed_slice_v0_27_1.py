from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_deepseek_source_backed_slice_v0_27_1 import (
    resolve_source_backed_cases,
    run_deepseek_source_backed_slice,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


class DeepSeekSourceBackedSliceV0271Tests(unittest.TestCase):
    def test_resolve_source_backed_cases_uses_manifest_and_model_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.mo"
            mutated = root / "mutated.mo"
            source.write_text("model Demo\n  Real x;\nequation\n  x = 1;\nend Demo;\n", encoding="utf-8")
            mutated.write_text("model Demo\n  Real x;\nend Demo;\n", encoding="utf-8")
            manifest = root / "manifest.jsonl"
            candidates = root / "candidates.jsonl"
            admitted = root / "admitted.jsonl"
            _write_jsonl(
                manifest,
                [
                    {
                        "candidate_id": "c1",
                        "seed_id": "c1",
                        "split": "positive",
                        "mutation_family": "family",
                        "repeatability_class": "stable_true_multi",
                    }
                ],
            )
            _write_jsonl(
                candidates,
                [
                    {
                        "candidate_id": "c1",
                        "target_model_name": "Demo",
                        "target_model_path": str(mutated),
                        "source_model_path": str(source),
                        "target_bucket_id": "ET03",
                    }
                ],
            )
            _write_jsonl(admitted, [])
            cases = resolve_source_backed_cases(
                manifest_rows_path=manifest,
                v0226_candidates_path=candidates,
                v0228_admitted_path=admitted,
                limit=1,
            )
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0]["case_id"], "c1")
            self.assertTrue(cases[0]["source_backed"])
            self.assertIn("model Demo", cases[0]["model_text"])

    def test_run_slice_writes_outputs_with_mocked_live_functions(self) -> None:
        def check_fn(text: str, _model_name: str):
            ok = "equation" in text
            return ok, ok, "none" if ok else "model_check_error"

        def repair_fn(**_kwargs):
            return "model Demo\n  Real x;\nequation\n  x = 0;\nend Demo;\n", "", "deepseek"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.mo"
            mutated = root / "mutated.mo"
            source.write_text("model Demo\n  Real x;\nequation\n  x = 1;\nend Demo;\n", encoding="utf-8")
            mutated.write_text("model Demo\n  Real x;\nend Demo;\n", encoding="utf-8")
            manifest = root / "manifest.jsonl"
            candidates = root / "candidates.jsonl"
            admitted = root / "admitted.jsonl"
            _write_jsonl(
                manifest,
                [{"candidate_id": "c1", "seed_id": "c1", "split": "positive", "mutation_family": "family"}],
            )
            _write_jsonl(
                candidates,
                [{"candidate_id": "c1", "target_model_name": "Demo", "target_model_path": str(mutated), "source_model_path": str(source)}],
            )
            _write_jsonl(admitted, [])
            summary = run_deepseek_source_backed_slice(
                out_dir=root / "out",
                manifest_rows_path=manifest,
                v0226_candidates_path=candidates,
                v0228_admitted_path=admitted,
                limit=1,
                max_rounds=2,
                check_fn=check_fn,
                repair_fn=repair_fn,
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["case_count"], 1)
            self.assertEqual(summary["pass_count"], 1)
            self.assertFalse(summary["discipline"]["comparative_claim_made"])
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "results.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
