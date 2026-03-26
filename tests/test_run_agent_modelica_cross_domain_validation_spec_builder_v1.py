import unittest
from pathlib import Path


class RunAgentModelicaCrossDomainValidationSpecBuilderV1Tests(unittest.TestCase):
    def test_script_defaults(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_cross_domain_validation_spec_builder_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn('OUT_PATH="${GATEFORGE_AGENT_CROSS_DOMAIN_VALIDATION_SPEC_OUT:-artifacts/agent_modelica_cross_domain_validation_v1/spec.json}"', content)
        self.assertIn('TRACK_MANIFEST="${GATEFORGE_AGENT_CROSS_DOMAIN_TRACK_MANIFEST:-data/agent_modelica_cross_domain_track_manifest_v1.json}"', content)
        self.assertIn("gateforge.agent_modelica_cross_domain_validation_spec_builder_v1", content)


if __name__ == "__main__":
    unittest.main()
