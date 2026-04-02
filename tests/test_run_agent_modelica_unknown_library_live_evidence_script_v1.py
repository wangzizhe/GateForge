import unittest
from pathlib import Path


class RunAgentModelicaUnknownLibraryLiveEvidenceScriptV1Tests(unittest.TestCase):
    def test_script_wires_live_unknown_library_chain(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_unknown_library_live_evidence_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("agent_modelica_unknown_library_taskset_v1", content)
        self.assertIn("--mode live", content)
        self.assertIn("agent_modelica_unknown_library_curated_retrieval_v1", content)
        self.assertIn("agent_modelica_unknown_library_retrieval_summary_v1", content)
        self.assertIn("agent_modelica_unknown_library_evidence_v1", content)
        self.assertIn("agent_modelica_diagnostic_quality_v0", content)
        self.assertIn("GATEFORGE_AGENT_UNKNOWN_LIBRARY_LIVE_EVIDENCE_OUT_DIR", content)
        self.assertIn("GATEFORGE_AGENT_UNKNOWN_LIBRARY_RUN_ID", content)
        self.assertIn("GATEFORGE_AGENT_UNKNOWN_LIBRARY_EXCLUDE_MODELS_JSON", content)
        self.assertIn("RUN_ROOT", content)
        self.assertIn("latest_run.json", content)
        self.assertIn("run_manifest.json", content)
        self.assertIn("STOP_AFTER_STAGE", content)
        self.assertIn("GATEFORGE_AGENT_LIVE_EXECUTOR_CMD", content)
        self.assertIn("agent_modelica_live_executor_v1", content)
        self.assertIn("--exclude-models-json", content)
        self.assertIn("--source-unstable-exclusions-out", content)
        self.assertIn("__SOURCE_LIBRARY_PATH__", content)
        self.assertIn("__SOURCE_PACKAGE_NAME__", content)
        self.assertIn("__SOURCE_LIBRARY_MODEL_PATH__", content)
        self.assertIn("__SOURCE_QUALIFIED_MODEL_NAME__", content)

    def test_resume_wrapper_sets_resume_env(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "resume_agent_modelica_unknown_library_live_run_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn("GATEFORGE_AGENT_UNKNOWN_LIBRARY_RESUME=1", content)
        self.assertIn("GATEFORGE_AGENT_UNKNOWN_LIBRARY_RESUME_RUN_ID", content)
        self.assertIn("GATEFORGE_AGENT_UNKNOWN_LIBRARY_RESUME_STAGES", content)
        self.assertIn("run_agent_modelica_unknown_library_live_evidence_v1.sh", content)


if __name__ == "__main__":
    unittest.main()
