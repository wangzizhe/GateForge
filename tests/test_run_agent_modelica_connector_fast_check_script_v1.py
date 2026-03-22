import unittest
from pathlib import Path


class RunAgentModelicaConnectorFastCheckScriptV1Tests(unittest.TestCase):
    def test_script_sets_absolute_shared_docker_cache_and_higher_timeout(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_connector_fast_check_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn('TIMEOUT_SEC="${GATEFORGE_AGENT_CONNECTOR_FAST_CHECK_TIMEOUT_SEC:-45}"', content)
        self.assertIn("GATEFORGE_OM_DOCKER_LIBRARY_CACHE", content)
        self.assertIn('$ROOT_DIR/$OUT_DIR/.gf_omcache/libraries', content)


if __name__ == "__main__":
    unittest.main()
