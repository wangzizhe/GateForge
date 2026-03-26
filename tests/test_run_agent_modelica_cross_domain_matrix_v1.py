import unittest
from pathlib import Path


class RunAgentModelicaCrossDomainMatrixV1Tests(unittest.TestCase):
    def test_script_defaults(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_cross_domain_matrix_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn('TRACK_ID="${GATEFORGE_AGENT_CROSS_DOMAIN_TRACK_ID:-buildings_v1}"', content)
        self.assertIn('DRY_RUN="${GATEFORGE_AGENT_CROSS_DOMAIN_DRY_RUN:-0}"', content)
        self.assertIn("gateforge.agent_modelica_cross_domain_matrix_runner_v1", content)


if __name__ == "__main__":
    unittest.main()
