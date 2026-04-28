from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_candidate_structure_attribution_v0_30_9 import (
    build_candidate_structure_attribution,
)


def _model(connects: int, equations: int) -> str:
    connect_lines = "\n".join(f"  connect(a{i}.p, b{i}.p);" for i in range(connects))
    equation_sections = "\n".join("equation\n  x = 1;" for _ in range(equations))
    return f"model X\n  Real x;\n{equation_sections}\n{connect_lines}\nend X;"


def _write(path: Path, *, case_id: str, verdict: str, model_texts: list[str], success_step: int | None = None) -> None:
    path.mkdir(parents=True, exist_ok=True)
    steps = []
    for idx, model_text in enumerate(model_texts, start=1):
        result = 'resultFile = "/workspace/X_res.mat"' if success_step == idx else "Failed to build model"
        steps.append(
            {
                "step": idx,
                "tool_calls": [{"name": "check_model", "arguments": {"model_text": model_text}}],
                "tool_results": [{"name": "check_model", "result": result}],
            }
        )
    row = {
        "case_id": case_id,
        "final_verdict": verdict,
        "submitted": verdict == "PASS",
        "token_used": 1000,
        "steps": steps,
    }
    with (path / "results.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


class CandidateStructureAttributionV0309Tests(unittest.TestCase):
    def test_summary_detects_low_structure_diversity_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_1 = root / "run_1"
            _write(
                run_1,
                case_id="sem_case",
                verdict="FAILED",
                model_texts=[_model(1, 1), _model(1, 1), _model(1, 1), _model(1, 1)],
            )
            summary = build_candidate_structure_attribution(run_dirs={"run_1": run_1}, out_dir=root / "out")
            self.assertEqual(summary["decision"], "candidate_discovery_limited_by_structure_homogeneity")
            self.assertEqual(summary["low_structure_diversity_failure_count"], 1)

    def test_summary_detects_distinct_success_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fail_run = root / "fail"
            pass_run = root / "pass"
            _write(fail_run, case_id="sem_case", verdict="FAILED", model_texts=[_model(1, 1), _model(1, 1)])
            _write(pass_run, case_id="sem_case", verdict="PASS", model_texts=[_model(2, 1)], success_step=1)
            summary = build_candidate_structure_attribution(
                run_dirs={"fail": fail_run, "pass": pass_run},
                out_dir=root / "out",
            )
            self.assertEqual(summary["cases"][0]["classification"], "success_requires_distinct_structure")


if __name__ == "__main__":
    unittest.main()
