from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_methodology_trace_attribution_v0_29_12 import (
    build_methodology_trace_attribution,
    classify_transition,
)


def _row(case_id: str, verdict: str, tools: list[str], *, submitted: bool = False, tokens: int = 1000) -> dict:
    return {
        "case_id": case_id,
        "final_verdict": verdict,
        "submitted": submitted,
        "token_used": tokens,
        "steps": [
            {
                "step": idx + 1,
                "text": f"step {idx + 1}",
                "tool_calls": [{"name": tool, "arguments": {}}],
            }
            for idx, tool in enumerate(tools)
        ],
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.mkdir(parents=True)
    with (path / "results.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class MethodologyTraceAttributionV02912Tests(unittest.TestCase):
    def test_classify_positive_without_connector_diagnostic(self) -> None:
        row = classify_transition(
            base_row=_row("sem_03", "FAILED", ["check_model"]),
            connector_row=_row("sem_03", "PASS", ["check_model", "submit_final"], submitted=True),
        )
        self.assertIn("connector_positive_delta", row["labels"])
        self.assertIn("no_connector_diagnostic_used", row["labels"])

    def test_classify_regression_budget_exhaustion(self) -> None:
        row = classify_transition(
            base_row=_row("sem_01", "PASS", ["check_model", "submit_final"], submitted=True),
            connector_row=_row(
                "sem_01",
                "FAILED",
                ["check_model", "get_unmatched_vars", "causalized_form"],
                submitted=False,
                tokens=35000,
            ),
        )
        self.assertIn("connector_regression", row["labels"])
        self.assertIn("budget_exhausted_before_submit", row["labels"])

    def test_build_attribution_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            connector = root / "connector"
            _write_jsonl(
                base,
                [
                    _row("sem_03", "FAILED", ["check_model"]),
                    _row("sem_01", "PASS", ["check_model", "submit_final"], submitted=True),
                ],
            )
            _write_jsonl(
                connector,
                [
                    _row("sem_03", "PASS", ["check_model", "submit_final"], submitted=True),
                    _row("sem_01", "FAILED", ["check_model", "get_unmatched_vars"], tokens=33000),
                ],
            )
            summary = build_methodology_trace_attribution(base_dir=base, connector_dir=connector, out_dir=root / "out")
            self.assertEqual(summary["positive_delta_count"], 1)
            self.assertEqual(summary["regression_count"], 1)
            self.assertEqual(summary["decision"], "connector_profile_positive_not_attributable_to_connector_diagnostic")
            self.assertTrue((root / "out" / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
