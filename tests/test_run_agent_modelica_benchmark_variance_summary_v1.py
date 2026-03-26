import unittest
from pathlib import Path


class RunAgentModelicaBenchmarkVarianceSummaryV1Tests(unittest.TestCase):
    def test_script_defaults(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_benchmark_variance_summary_v1.sh"
        content = script.read_text(encoding="utf-8")
        self.assertIn('SPEC_PATH="${GATEFORGE_AGENT_BENCHMARK_VARIANCE_SPEC:-data/agent_modelica_benchmark_variance_spec_template_v1.json}"', content)
        self.assertIn('OUT_PATH="${GATEFORGE_AGENT_BENCHMARK_VARIANCE_OUT:-artifacts/benchmark_variance_summary_v1/summary.json}"', content)
        self.assertIn("gateforge.agent_modelica_benchmark_variance_summary_v1", content)


if __name__ == "__main__":
    unittest.main()
