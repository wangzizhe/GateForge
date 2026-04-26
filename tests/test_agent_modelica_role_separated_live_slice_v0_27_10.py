from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_role_separated_live_slice_v0_27_10 import (
    resolve_role_separated_cases,
    run_role_separated_live_slice,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


class RoleSeparatedLiveSliceV02710Tests(unittest.TestCase):
    def test_resolve_cases_filters_by_slice_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.mo"
            mutated = root / "mutated.mo"
            source.write_text("model Demo\n  Real x;\nequation\n  x = 1;\nend Demo;\n", encoding="utf-8")
            mutated.write_text("model Demo\n  Real x;\nend Demo;\n", encoding="utf-8")
            plan = root / "plan.jsonl"
            v0226 = root / "v0226.jsonl"
            v0228 = root / "v0228.jsonl"
            _write_jsonl(
                plan,
                [
                    {"candidate_id": "c1", "family": "family", "slice_role": "capability_baseline", "split": "positive", "repeatability_class": "stable_true_multi"},
                    {"candidate_id": "c2", "family": "family", "slice_role": "hard_negative", "split": "hard_negative", "repeatability_class": "stable_dead_end"},
                ],
            )
            _write_jsonl(v0226, [])
            _write_jsonl(v0228, [{"candidate_id": "c1", "target_model_name": "Demo", "mutated_model_path": str(mutated), "source_model_path": str(source)}])
            cases = resolve_role_separated_cases(
                slice_plan_path=plan,
                v0226_candidates_path=v0226,
                v0228_admitted_path=v0228,
                slice_role="capability_baseline",
            )
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0]["case_id"], "c1")
            self.assertEqual(cases[0]["model_name"], "Demo")
            self.assertEqual(cases[0]["slice_role"], "capability_baseline")

    def test_run_live_slice_reports_role_and_keeps_pass_rate_scoped(self) -> None:
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
            plan = root / "plan.jsonl"
            v0226 = root / "v0226.jsonl"
            v0228 = root / "v0228.jsonl"
            _write_jsonl(plan, [{"candidate_id": "c1", "family": "family", "slice_role": "capability_baseline", "split": "positive", "repeatability_class": "stable_true_multi"}])
            _write_jsonl(v0226, [])
            _write_jsonl(v0228, [{"candidate_id": "c1", "target_model_name": "Demo", "mutated_model_path": str(mutated), "source_model_path": str(source)}])
            summary = run_role_separated_live_slice(
                out_dir=root / "out",
                slice_plan_path=plan,
                v0226_candidates_path=v0226,
                v0228_admitted_path=v0228,
                slice_role="capability_baseline",
                limit=1,
                max_rounds=2,
                check_fn=check_fn,
                repair_fn=repair_fn,
            )
            self.assertEqual(summary["slice_role"], "capability_baseline")
            self.assertTrue(summary["mixed_pass_rate_allowed"])
            self.assertEqual(summary["pass_count"], 1)
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "results.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
