import unittest
from pathlib import Path


class RunAgentModelicaCrossDomainTrackPrepareV1Tests(unittest.TestCase):
    def test_script_exposes_cross_domain_prepare_defaults(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_cross_domain_track_prepare_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn('TRACK_ID="${GATEFORGE_AGENT_CROSS_DOMAIN_TRACK_ID:-buildings_v1}"', content)
        self.assertIn('SOURCE_MANIFEST="${GATEFORGE_AGENT_CROSS_DOMAIN_SOURCE_MANIFEST:-data/modelica_cross_domain_seed_sources_v1.json}"', content)
        self.assertIn('TRACK_MANIFEST="${GATEFORGE_AGENT_CROSS_DOMAIN_TRACK_MANIFEST:-data/agent_modelica_cross_domain_track_manifest_v1.json}"', content)
        self.assertIn('VALID_ONLY="${GATEFORGE_AGENT_CROSS_DOMAIN_VALID_ONLY:-1}"', content)
        self.assertIn('DRY_RUN="${GATEFORGE_AGENT_CROSS_DOMAIN_DRY_RUN:-0}"', content)
        self.assertIn("gateforge.agent_modelica_cross_domain_track_prepare_v1", content)


if __name__ == "__main__":
    unittest.main()
