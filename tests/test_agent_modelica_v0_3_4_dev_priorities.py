from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_4_dev_priorities import build_v0_3_4_dev_priorities


class AgentModelicaV034DevPrioritiesTests(unittest.TestCase):
    def test_build_dev_priorities_reports_top_lever_and_best_lane(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v034_dev_priorities_") as td:
            root = Path(td)
            failure_input = root / "failures.json"
            refreshed = root / "refreshed.json"
            multi_round = root / "multi_round.json"
            failure_input.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "mutation_id": "case_a",
                                "success": False,
                                "planner_invoked": True,
                                "rounds_used": 1,
                                "resolution_path": "unresolved",
                            },
                            {
                                "mutation_id": "case_b",
                                "success": False,
                                "planner_invoked": True,
                                "rounds_used": 1,
                                "resolution_path": "unresolved",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            refreshed.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": f"cand_{idx}",
                                "holdout_clean": True,
                                "v0_3_family_id": "runtime_numerical_instability",
                                "expected_layer_hint": "layer_4",
                                "resolution_path": "llm_planner_assisted",
                                "planner_invoked": True,
                            }
                            for idx in range(5)
                        ]
                    }
                ),
                encoding="utf-8",
            )
            multi_round.mkdir(parents=True, exist_ok=True)
            for name in ("mr_case_a", "mr_case_b"):
                (multi_round / f"{name}.json").write_text(
                    json.dumps(
                        {
                            "task_id": name,
                            "failure_type": "coupled_conflict_failure",
                            "executor_status": "PASS",
                            "check_model_pass": True,
                            "simulate_pass": True,
                            "resolution_path": "deterministic_rule_only",
                            "live_request_count": 0,
                            "rounds_used": 2,
                            "attempts": [
                                {"check_model_pass": False, "simulate_pass": False},
                                {
                                    "check_model_pass": True,
                                    "simulate_pass": True,
                                    "source_repair": {"applied": True},
                                },
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
            payload = build_v0_3_4_dev_priorities(
                failure_input_path=str(failure_input),
                refreshed_candidate_taskset_path=str(refreshed),
                out_dir=str(root / "out"),
                min_freeze_ready_cases=5,
                multi_round_audit_input_path=str(multi_round),
            )
            self.assertEqual(payload["primary_repair_lever"]["lever"], "multi_round_deterministic_repair_validation")
            self.assertEqual(payload["top_bottleneck_lever"]["lever"], "l2_replan")
            self.assertEqual(
                payload["evidence_backed_repair_lever"]["lever"],
                "multi_round_deterministic_repair_validation",
            )
            self.assertEqual(payload["best_harder_lane"]["family_id"], "runtime_numerical_instability")
            self.assertTrue(payload["next_actions"])
            self.assertTrue(
                any("Promote multi-round deterministic repair validation" in str(item) for item in payload["next_actions"])
            )
            self.assertTrue(
                any("Treat `multi_round_deterministic_repair_validation` as the primary v0.3.4 repair lever" in str(item) for item in payload["next_actions"])
            )


if __name__ == "__main__":
    unittest.main()
