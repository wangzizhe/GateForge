from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_candidate_discovery_attribution_v0_30_5 import build_candidate_discovery_attribution


def _write(path: Path, *, case_id: str, verdict: str, success_seen: bool, submitted: bool) -> None:
    path.mkdir(parents=True, exist_ok=True)
    result = 'resultFile = "/workspace/X_res.mat"' if success_seen else "Failed to build model"
    row = {
        "case_id": case_id,
        "final_verdict": verdict,
        "submitted": submitted,
        "token_used": 1000,
        "steps": [
            {
                "step": 1,
                "tool_calls": [{"name": "check_model", "arguments": {"model_text": "model X end X;"}}],
                "tool_results": [{"name": "check_model", "result": result}],
            }
        ],
    }
    with (path / "results.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


class CandidateDiscoveryAttributionV0305Tests(unittest.TestCase):
    def test_summary_identifies_discovery_bottleneck(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_1 = root / "run_1"
            run_2 = root / "run_2"
            _write(run_1, case_id="sem_a", verdict="FAILED", success_seen=False, submitted=False)
            _write(run_2, case_id="sem_a", verdict="FAILED", success_seen=False, submitted=False)
            _write(run_1, case_id="sem_b", verdict="PASS", success_seen=True, submitted=True)
            _write(run_2, case_id="sem_b", verdict="FAILED", success_seen=False, submitted=False)
            summary = build_candidate_discovery_attribution(
                run_dirs={"run_1": run_1, "run_2": run_2},
                out_dir=root / "out",
            )
            self.assertEqual(summary["decision"], "candidate_discovery_is_current_bottleneck")
            by_case = {case["case_id"]: case for case in summary["cases"]}
            self.assertEqual(by_case["sem_a"]["classification"], "stable_no_success_candidate")
            self.assertEqual(by_case["sem_b"]["classification"], "discovery_unstable")

    def test_summary_separates_acceptance_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_1 = root / "run_1"
            _write(run_1, case_id="sem_a", verdict="FAILED", success_seen=True, submitted=False)
            summary = build_candidate_discovery_attribution(
                run_dirs={"run_1": run_1},
                out_dir=root / "out",
            )
            self.assertEqual(summary["decision"], "candidate_acceptance_remains_bottleneck")
            self.assertEqual(summary["acceptance_failure_count"], 1)


if __name__ == "__main__":
    unittest.main()
