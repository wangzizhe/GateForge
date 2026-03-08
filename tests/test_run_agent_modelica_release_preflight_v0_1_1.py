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

    def test_script_integrates_l3_diagnostic_gate_and_summary_fields(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = (repo_root / "scripts" / "run_agent_modelica_release_preflight_v0_1_1.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("ENABLE_L3_DIAGNOSTIC_GATE", script)
        self.assertIn("ENFORCE_L3_DIAGNOSTIC_GATE", script)
        self.assertIn("python3 -m gateforge.agent_modelica_diagnostic_quality_v0", script)
        self.assertIn("python3 -m gateforge.agent_modelica_l3_diagnostic_gate_v0", script)
        self.assertIn('"l3_diagnostic_gate_status"', script)
        self.assertIn('"l3_parse_coverage_pct"', script)
        self.assertIn('"l3_type_match_rate_pct"', script)
        self.assertIn('"l3_stage_match_rate_pct"', script)


if __name__ == "__main__":
    unittest.main()
