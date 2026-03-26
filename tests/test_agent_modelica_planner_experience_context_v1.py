from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_planner_experience_context_v1 import (
    build_planner_experience_context,
)


class AgentModelicaPlannerExperienceContextV1Tests(unittest.TestCase):
    def _experience_payload(self) -> dict:
        return {
            "records": [
                {
                    "task_id": "t1",
                    "failure_type": "model_check_error",
                    "error_subtype": "parse_lexer_error",
                    "repair_quality_score": 0.93,
                    "action_contributions": [
                        {
                            "rule_id": "rule_parse_error_pre_repair",
                            "action_key": "repair|parse_error_pre_repair|rule_engine_v1",
                            "rule_tier": "domain_general_rule",
                            "replay_eligible": True,
                            "failure_type": "model_check_error",
                            "error_subtype": "parse_lexer_error",
                            "contribution": "advancing",
                        },
                        {
                            "rule_id": "rule_wave2_marker_repair",
                            "action_key": "repair|wave2_marker_repair|rule_engine_v1",
                            "rule_tier": "mutation_contract_rule",
                            "replay_eligible": False,
                            "failure_type": "model_check_error",
                            "error_subtype": "parse_lexer_error",
                            "contribution": "advancing",
                        },
                    ],
                },
                {
                    "task_id": "t2",
                    "failure_type": "model_check_error",
                    "error_subtype": "parse_lexer_error",
                    "repair_quality_score": 0.88,
                    "action_contributions": [
                        {
                            "rule_id": "rule_multi_round_layered_repair",
                            "action_key": "repair|multi_round_layered_repair|rule_engine_v1",
                            "rule_tier": "domain_general_rule",
                            "replay_eligible": True,
                            "failure_type": "model_check_error",
                            "error_subtype": "parse_lexer_error",
                            "contribution": "regressing",
                        }
                    ],
                },
                {
                    "task_id": "t3",
                    "failure_type": "simulate_error",
                    "repair_quality_score": 0.95,
                    "action_contributions": [
                        {
                            "rule_id": "rule_source_model_repair",
                            "action_key": "repair|source_model_repair|rule_engine_v1",
                            "rule_tier": "source_aware_only",
                            "failure_type": "simulate_error",
                            "contribution": "advancing",
                        }
                    ],
                },
            ]
        }

    def test_builds_positive_and_caution_hints(self) -> None:
        context = build_planner_experience_context(
            self._experience_payload(),
            failure_type="model_check_error",
            error_subtype="parse_lexer_error",
        )
        self.assertTrue(bool(context.get("used")))
        self.assertEqual(int(context.get("positive_hint_count") or 0), 2)
        self.assertEqual(int(context.get("caution_hint_count") or 0), 1)
        prompt_context = str(context.get("prompt_context_text") or "")
        self.assertIn("Historical success", prompt_context)
        self.assertIn("Historical caution", prompt_context)
        self.assertIn("parse_error_pre_repair", prompt_context)
        self.assertIn("multi_round_layered_repair", prompt_context)

    def test_excludes_source_aware_only_actions(self) -> None:
        context = build_planner_experience_context(
            self._experience_payload(),
            failure_type="simulate_error",
        )
        self.assertFalse(bool(context.get("used")))
        self.assertEqual(int(context.get("positive_hint_count") or 0), 0)
        self.assertEqual(int(context.get("caution_hint_count") or 0), 0)

    def test_respects_token_budget(self) -> None:
        context = build_planner_experience_context(
            self._experience_payload(),
            failure_type="model_check_error",
            error_subtype="parse_lexer_error",
            max_context_tokens=20,
        )
        self.assertLessEqual(int(context.get("prompt_token_estimate") or 0), 20)
        self.assertTrue(bool(context.get("truncated")))

    def test_cli_writes_context(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            experience = root / "experience.json"
            out = root / "planner_context.json"
            experience.write_text(json.dumps(self._experience_payload()), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_planner_experience_context_v1",
                    "--experience",
                    str(experience),
                    "--failure-type",
                    "model_check_error",
                    "--error-subtype",
                    "parse_lexer_error",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(bool(payload.get("used")))
            self.assertGreaterEqual(int(payload.get("positive_hint_count") or 0), 1)


if __name__ == "__main__":
    unittest.main()
