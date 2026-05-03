from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_medium_candidate_mining_v0_54_0 import (
    collect_base_tool_use_outcomes,
    discover_result_paths,
    run_medium_candidate_mining,
    summarize_medium_candidates,
)


class MediumCandidateMiningV054Tests(unittest.TestCase):
    def test_summarize_selects_non_hard_cases_in_target_pass_band(self) -> None:
        summary, rows = summarize_medium_candidates(
            outcomes={
                "medium_a": {"case_id": "medium_a", "pass": 1, "fail": 1, "provider_error": 0, "paths": ["p"]},
                "hard_a": {"case_id": "hard_a", "pass": 0, "fail": 2, "provider_error": 0, "paths": ["p"]},
                "already_hard": {"case_id": "already_hard", "pass": 1, "fail": 1, "provider_error": 0, "paths": ["p"]},
            },
            hard_case_ids=["already_hard"],
        )
        self.assertEqual(summary["medium_candidate_ids"], ["medium_a"])
        self.assertEqual(rows[0]["candidate_status"], "medium_candidate")

    def test_collect_outcomes_excludes_provider_errors_and_non_base_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"case_id":"case_a","run_mode":"tool_use","tool_profile":"base","final_verdict":"PASS","provider_error":""}',
                        '{"case_id":"case_a","run_mode":"tool_use","tool_profile":"base","final_verdict":"FAILED","provider_error":""}',
                        '{"case_id":"case_a","run_mode":"tool_use","tool_profile":"structural","final_verdict":"PASS","provider_error":""}',
                        '{"case_id":"case_b","run_mode":"tool_use","tool_profile":"base","final_verdict":"FAILED","provider_error":"service_unavailable"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            outcomes = collect_base_tool_use_outcomes(result_paths=[path])
        self.assertEqual(outcomes["case_a"]["pass"], 1)
        self.assertEqual(outcomes["case_a"]["fail"], 1)
        self.assertEqual(outcomes["case_b"]["provider_error"], 1)
        self.assertEqual(outcomes["case_b"]["fail"], 0)

    def test_run_medium_candidate_mining_writes_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "results.jsonl").write_text(
                '{"case_id":"case_a","run_mode":"tool_use","tool_profile":"base","final_verdict":"PASS","provider_error":""}\n'
                '{"case_id":"case_a","run_mode":"tool_use","tool_profile":"base","final_verdict":"FAILED","provider_error":""}\n',
                encoding="utf-8",
            )
            hard = root / "hard.json"
            hard.write_text('{"hard_case_ids":[]}', encoding="utf-8")
            out = root / "out"
            self.assertEqual(discover_result_paths(root), [run_dir / "results.jsonl"])
            summary = run_medium_candidate_mining(artifact_root=root, hard_pack_path=hard, out_dir=out)
            self.assertEqual(summary["medium_candidate_ids"], ["case_a"])
            self.assertTrue((out / "medium_candidates.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
