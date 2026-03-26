from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_cross_domain_validation_v1 import (
    _provider_noise_counts,
    build_validation_summary,
    render_markdown,
    run_validation,
    summarize_track_config,
)


class AgentModelicaCrossDomainValidationV1Tests(unittest.TestCase):
    def test_provider_noise_counts_groups_known_errors(self) -> None:
        counts = _provider_noise_counts(
            {
                "bare_llm_results": [
                    {"error": "gemini_http_error: 503"},
                    {"error": "rate_limited"},
                    {"error": "omc_validation_failed"},
                    {"error": "request timeout"},
                ]
            }
        )
        self.assertEqual(counts["provider_503"], 1)
        self.assertEqual(counts["rate_limited"], 1)
        self.assertEqual(counts["omc_validation_failed"], 1)
        self.assertEqual(counts["timeout"], 1)

    def test_summarize_track_config_aggregates_replay_and_planner_diagnostics(self) -> None:
        row = summarize_track_config(
            track_id="buildings",
            library="Buildings",
            config_label="replay_plus_planner",
            comparison_summary={
                "status": "PASS",
                "verdict": "GATEFORGE_ADVANTAGE",
                "bare_llm_metrics": {"repair_rate": 0.5, "total": 2},
                "gateforge_metrics": {"repair_rate": 1.0, "total": 2},
                "bare_llm_results": [{"error": "gemini_http_error: 503"}],
            },
            gateforge_results={
                "metrics": {"repair_rate": 1.0, "total": 2},
                "results": [
                    {
                        "experience_replay": {
                            "used": True,
                            "signal_coverage_status": "sufficient_signal_coverage",
                            "priority_reason": "rules_reordered_by_experience",
                        },
                        "planner_experience_injection": {
                            "used": True,
                            "prompt_token_estimate": 210,
                            "injection_reason": "planner_context_injected",
                        },
                    },
                    {
                        "experience_replay": {
                            "used": False,
                            "signal_coverage_status": "insufficient_signal_coverage",
                            "priority_reason": "default_rule_order",
                        },
                        "planner_experience_injection": {
                            "used": False,
                            "injection_reason": "planner_experience_not_invoked",
                        },
                    },
                ],
            },
        )
        self.assertEqual(row["delta_pp"], 50.0)
        self.assertEqual(row["provider_noise_counts"]["provider_503"], 1)
        self.assertEqual(row["gateforge_diagnostics"]["replay_used_count"], 1)
        self.assertEqual(row["gateforge_diagnostics"]["planner_used_count"], 1)
        self.assertEqual(
            row["gateforge_diagnostics"]["planner_prompt_token_estimate_avg"], 210.0
        )

    def test_build_validation_summary_computes_no_regression_vs_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            base_cmp = root / "base_cmp.json"
            base_gf = root / "base_gf.json"
            replay_cmp = root / "replay_cmp.json"
            replay_gf = root / "replay_gf.json"
            base_cmp.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "verdict": "GATEFORGE_ADVANTAGE",
                        "bare_llm_metrics": {"repair_rate": 0.25, "total": 4},
                        "gateforge_metrics": {"repair_rate": 1.0, "total": 4},
                    }
                ),
                encoding="utf-8",
            )
            base_gf.write_text(json.dumps({"metrics": {"repair_rate": 1.0, "total": 4}}), encoding="utf-8")
            replay_cmp.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "verdict": "GATEFORGE_ADVANTAGE",
                        "bare_llm_metrics": {"repair_rate": 0.25, "total": 4},
                        "gateforge_metrics": {"repair_rate": 0.75, "total": 4},
                    }
                ),
                encoding="utf-8",
            )
            replay_gf.write_text(json.dumps({"metrics": {"repair_rate": 0.75, "total": 4}}), encoding="utf-8")

            summary = build_validation_summary(
                {
                    "tracks": [
                        {
                            "track_id": "openipsl",
                            "library": "OpenIPSL",
                            "configs": {
                                "baseline": {
                                    "comparison_summary": str(base_cmp),
                                    "gateforge_results": str(base_gf),
                                },
                                "replay_only": {
                                    "comparison_summary": str(replay_cmp),
                                    "gateforge_results": str(replay_gf),
                                },
                            },
                        }
                    ]
                }
            )
        agg = {str(x.get("config_label")): x for x in summary.get("aggregate_by_config") or [] if isinstance(x, dict)}
        self.assertEqual(summary["status"], "NEEDS_REVIEW")
        self.assertIn("config_regression_detected", summary["reasons"])
        self.assertFalse(agg["replay_only"]["no_regression_vs_baseline"])

    def test_run_validation_writes_summary_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cmp_path = root / "cmp.json"
            gf_path = root / "gf.json"
            spec = root / "spec.json"
            out = root / "summary.json"
            cmp_path.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "verdict": "GATEFORGE_ADVANTAGE",
                        "bare_llm_metrics": {"repair_rate": 0.2, "total": 5},
                        "gateforge_metrics": {"repair_rate": 1.0, "total": 5},
                    }
                ),
                encoding="utf-8",
            )
            gf_path.write_text(json.dumps({"metrics": {"repair_rate": 1.0, "total": 5}}), encoding="utf-8")
            spec.write_text(
                json.dumps(
                    {
                        "schema_version": "agent_modelica_cross_domain_validation_spec_v1",
                        "tracks": [
                            {
                                "track_id": "buildings",
                                "library": "Buildings",
                                "configs": {
                                    "baseline": {
                                        "comparison_summary": str(cmp_path),
                                        "gateforge_results": str(gf_path),
                                    }
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            summary = run_validation(spec_path=str(spec), out=str(out))
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue(out.exists())
            self.assertTrue(out.with_suffix(".md").exists())
            md = render_markdown(summary)
            self.assertIn("Aggregate by Config", md)

    def test_cli_runs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cmp_path = root / "cmp.json"
            gf_path = root / "gf.json"
            spec = root / "spec.json"
            out = root / "summary.json"
            cmp_path.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "verdict": "GATEFORGE_ADVANTAGE",
                        "bare_llm_metrics": {"repair_rate": 0.2, "total": 3},
                        "gateforge_metrics": {"repair_rate": 1.0, "total": 3},
                    }
                ),
                encoding="utf-8",
            )
            gf_path.write_text(json.dumps({"metrics": {"repair_rate": 1.0, "total": 3}}), encoding="utf-8")
            spec.write_text(
                json.dumps(
                    {
                        "tracks": [
                            {
                                "track_id": "buildings",
                                "library": "Buildings",
                                "configs": {
                                    "baseline": {
                                        "comparison_summary": str(cmp_path),
                                        "gateforge_results": str(gf_path),
                                    }
                                },
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
                    "gateforge.agent_modelica_cross_domain_validation_v1",
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
