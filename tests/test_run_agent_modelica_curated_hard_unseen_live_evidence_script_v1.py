import unittest
from pathlib import Path


class RunAgentModelicaCuratedHardUnseenLiveEvidenceScriptV1Tests(unittest.TestCase):
    def test_live_wrapper_overrides_unknown_library_modules(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_curated_hard_unseen_live_evidence_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("GATEFORGE_AGENT_CURATED_HARD_UNSEEN_LIVE_EVIDENCE_OUT_DIR", content)
        self.assertIn("GATEFORGE_AGENT_UNKNOWN_LIBRARY_TASKSET_MODULE", content)
        self.assertIn("gateforge.agent_modelica_curated_hard_unseen_taskset_v1", content)
        self.assertIn("gateforge.agent_modelica_curated_hard_unseen_curated_retrieval_v1", content)
        self.assertIn("agent_modelica_curated_hard_unseen_baseline_summary_v1", content)
        self.assertIn("run_agent_modelica_unknown_library_live_evidence_v1.sh", content)

    def test_resume_wrapper_calls_live_wrapper(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "resume_agent_modelica_curated_hard_unseen_live_run_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("GATEFORGE_AGENT_CURATED_HARD_UNSEEN_RESUME", content)
        self.assertIn("GATEFORGE_AGENT_UNKNOWN_LIBRARY_RESUME", content)
        self.assertIn("GATEFORGE_AGENT_CURATED_HARD_UNSEEN_RESUME_RUN_ID", content)
        self.assertIn("run_agent_modelica_curated_hard_unseen_live_evidence_v1.sh", content)


if __name__ == "__main__":
    unittest.main()
