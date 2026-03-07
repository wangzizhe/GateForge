import unittest
from pathlib import Path


class RunAgentModelicaReleasePreflightV011Tests(unittest.TestCase):
    def test_fallback_mutant_generation_uses_real_newlines(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = (repo_root / "scripts" / "run_agent_modelica_release_preflight_v0_1_1.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('lambda _: "equation\\n" + injection', script)
        self.assertIn('insert = "equation\\n" + injection + "\\n"', script)
        self.assertIn('mutated_text = source_text + "\\nequation\\n" + injection + "\\n"', script)
        self.assertNotIn('"equation\\\\n" + injection', script)
        self.assertNotIn('"\\\\nequation\\\\n" + injection', script)


if __name__ == "__main__":
    unittest.main()
