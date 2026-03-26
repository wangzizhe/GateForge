from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_benchmark_variance_summary_v1 import (
    _provider_noise_counts,
    build_summary,
    render_markdown,
    run_summary,
    summarize_group,
)


class AgentModelicaBenchmarkVarianceSummaryV1Tests(unittest.TestCase):
    def test_provider_noise_counts(self) -> None:
        counts = _provider_noise_counts(
            {
                "bare_llm_results": [
                    {"error": "gemini_http_error: 503"},
                    {"error": "rate_limited"},
                    {"error": "request timeout"},
                ]
            }
        )
        self.assertEqual(counts["provider_503"], 1)
        self.assertEqual(counts["rate_limited"], 1)
        self.assertEqual(counts["timeout"], 1)

    def test_summarize_group_computes_stddev(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cmp1 = root / "cmp1.json"
            cmp2 = root / "cmp2.json"
            gf1 = root / "gf1.json"
            gf2 = root / "gf2.json"
            cmp1.write_text(json.dumps({"bare_llm_metrics": {"repair_rate": 0.2}, "gateforge_metrics": {"repair_rate": 1.0}, "bare_llm_results": [{"error": "gemini_http_error: 503"}]}), encoding="utf-8")
            cmp2.write_text(json.dumps({"bare_llm_metrics": {"repair_rate": 0.4}, "gateforge_metrics": {"repair_rate": 1.0}, "bare_llm_results": [{"error": "rate_limited"}]}), encoding="utf-8")
            gf1.write_text(json.dumps({"metrics": {"repair_rate": 1.0}}), encoding="utf-8")
            gf2.write_text(json.dumps({"metrics": {"repair_rate": 1.0}}), encoding="utf-8")
            row = summarize_group(
                {
                    "group_id": "track_a_baseline",
                    "library": "MSL",
                    "config_label": "baseline",
                    "runs": [
                        {"comparison_summary": str(cmp1), "gateforge_results": str(gf1)},
                        {"comparison_summary": str(cmp2), "gateforge_results": str(gf2)},
                    ],
                }
            )
        self.assertEqual(row["run_count"], 2)
        self.assertEqual(row["gateforge_repair_rate"]["mean"], 1.0)
        self.assertGreater(row["bare_llm_repair_rate"]["stddev"], 0.0)
        self.assertEqual(row["provider_noise"]["provider_503"]["mean"], 1.0)

    def test_run_summary_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cmp1 = root / "cmp1.json"
            gf1 = root / "gf1.json"
            spec = root / "spec.json"
            out = root / "summary.json"
            cmp1.write_text(json.dumps({"bare_llm_metrics": {"repair_rate": 0.3}, "gateforge_metrics": {"repair_rate": 1.0}}), encoding="utf-8")
            gf1.write_text(json.dumps({"metrics": {"repair_rate": 1.0}}), encoding="utf-8")
            spec.write_text(
                json.dumps(
                    {
                        "groups": [
                            {
                                "group_id": "g1",
                                "library": "Buildings",
                                "config_label": "planner_only",
                                "runs": [
                                    {"comparison_summary": str(cmp1), "gateforge_results": str(gf1)}
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            summary = run_summary(spec_path=str(spec), out=str(out))
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(out.exists())
            self.assertTrue(out.with_suffix(".md").exists())
            self.assertIn("planner_only", render_markdown(summary))

    def test_build_summary_fails_without_groups(self) -> None:
        summary = build_summary({})
        self.assertEqual(summary["status"], "FAIL")
        self.assertIn("no_groups", summary["reasons"])

    def test_cli_runs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cmp1 = root / "cmp1.json"
            gf1 = root / "gf1.json"
            spec = root / "spec.json"
            out = root / "summary.json"
            cmp1.write_text(json.dumps({"bare_llm_metrics": {"repair_rate": 0.3}, "gateforge_metrics": {"repair_rate": 1.0}}), encoding="utf-8")
            gf1.write_text(json.dumps({"metrics": {"repair_rate": 1.0}}), encoding="utf-8")
            spec.write_text(
                json.dumps(
                    {
                        "groups": [
                            {
                                "group_id": "g1",
                                "library": "Buildings",
                                "config_label": "baseline",
                                "runs": [
                                    {"comparison_summary": str(cmp1), "gateforge_results": str(gf1)}
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_benchmark_variance_summary_v1",
                    "--spec",
                    str(spec),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("status"), "PASS")


if __name__ == "__main__":
    unittest.main()
