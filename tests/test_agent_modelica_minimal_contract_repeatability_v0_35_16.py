from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_minimal_contract_repeatability_v0_35_16 import (
    build_minimal_contract_repeatability,
)


def _write_run(path: Path, *, passed: list[str], failed: list[str]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    rows = []
    for case_id in passed:
        rows.append({"case_id": case_id, "final_verdict": "PASS", "submitted": True, "final_model_text": ""})
    for case_id in failed:
        rows.append({"case_id": case_id, "final_verdict": "FAILED", "submitted": False, "final_model_text": ""})
    (path / "results.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


class MinimalContractRepeatabilityV03516Tests(unittest.TestCase):
    def test_detects_stable_partial_gain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_a = root / "run_a"
            run_b = root / "run_b"
            _write_run(run_a, passed=["case_a"], failed=["case_b"])
            _write_run(run_b, passed=["case_a"], failed=["case_b"])
            summary = build_minimal_contract_repeatability(run_dirs=[run_a, run_b], out_dir=root / "out")
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["stable_pass_case_ids"], ["case_a"])
            self.assertEqual(summary["stable_fail_case_ids"], ["case_b"])
            self.assertEqual(summary["decision"], "minimal_contract_stable_partial_gain")

    def test_missing_run_marks_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = build_minimal_contract_repeatability(run_dirs=[root / "missing"], out_dir=root / "out")
            self.assertEqual(summary["status"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
