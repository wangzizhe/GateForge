import unittest
from pathlib import Path


class RunAgentModelicaMultiRoundFailureLiveEvidenceScriptV1Tests(unittest.TestCase):
    def test_script_contains_multi_round_stages(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_multi_round_failure_live_evidence_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("agent_modelica_multi_round_failure_taskset_v1", content)
        self.assertIn("multi_round_baseline_summary", content)
        self.assertIn("GATEFORGE_AGENT_MULTI_ROUND_DETERMINISTIC_REPAIR=1", content)
        self.assertIn("RETRIEVAL_EXECUTOR_CMD", content)
        self.assertIn("task_construction_still_too_easy", content)
        self.assertIn("GATEFORGE_AGENT_MULTI_ROUND_VARIANT_TAG", content)
        self.assertIn("--variant-tag", content)
        self.assertIn("GATEFORGE_AGENT_MULTI_ROUND_ALLOW_PARTIAL_TASKSET", content)
        self.assertIn("--allow-partial-taskset", content)


if __name__ == "__main__":
    unittest.main()
