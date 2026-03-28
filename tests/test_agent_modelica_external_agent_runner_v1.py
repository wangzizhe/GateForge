import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_external_agent_runner_v1 import (
    external_agent_run_schema_v1,
    normalize_external_agent_run,
)


class AgentModelicaExternalAgentRunnerV1Tests(unittest.TestCase):
    def test_normalize_external_agent_run_builds_summary(self) -> None:
        payload = {
            "arm_id": "arm1_general_agent",
            "provider_name": "claude",
            "model_id": "claude-opus-4-6-20260301",
            "model_id_resolvable": True,
            "records": [
                {"task_id": "t1", "success": True, "agent_rounds": 2, "tool_calls": [{"tool_name": "omc_check_model"}], "wall_clock_sec": 10},
                {"task_id": "t2", "success": False, "infra_failure_reason": "docker_permission_denied", "agent_rounds": 1, "omc_tool_call_count": 2, "wall_clock_sec": 20},
            ],
        }
        normalized = normalize_external_agent_run(payload)
        self.assertEqual(normalized.get("provider_name"), "claude")
        self.assertEqual(int(normalized.get("record_count") or 0), 2)
        self.assertEqual(int(normalized["summary"]["infra_failure_count"]), 1)
        self.assertEqual(float(normalized["summary"]["avg_omc_tool_call_count"]), 1.5)

    def test_schema_exposes_required_fields(self) -> None:
        schema = external_agent_run_schema_v1()
        self.assertIn("arm_id", schema.get("bundle_fields") or [])
        self.assertIn("task_id", schema.get("record_fields") or [])


if __name__ == "__main__":
    unittest.main()
