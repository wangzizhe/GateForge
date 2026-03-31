from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_track_c_claim_gate_v0_3_3 import build_claim_gate


class AgentModelicaTrackCClaimGateV033Tests(unittest.TestCase):
    def test_strong_claim_uses_median_success_gap(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_claim_") as td:
            root = Path(td)
            matrix = root / "matrix.json"
            stability = root / "stability.json"
            matrix.write_text(
                json.dumps(
                    {
                        "provider_rows": [
                            {
                                "provider_name": "gateforge",
                                "clean_run_count": 2,
                                "median_infra_normalized_success_rate_pct": 95.0,
                                "median_avg_wall_clock_sec": 10.0,
                                "median_avg_omc_tool_call_count": 1.0,
                                "infra_failure_rate_pct": 0.0,
                                "auth_session_failure_rate_pct": 0.0,
                            },
                            {
                                "provider_name": "claude",
                                "clean_run_count": 3,
                                "median_infra_normalized_success_rate_pct": 89.0,
                                "median_avg_wall_clock_sec": 20.0,
                                "median_avg_omc_tool_call_count": 2.0,
                                "infra_failure_rate_pct": 0.0,
                                "auth_session_failure_rate_pct": 0.0,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            stability.write_text(json.dumps({"classification": "STABLE"}), encoding="utf-8")
            payload = build_claim_gate(
                paper_matrix_summary_path=str(matrix),
                claude_stability_summary_path=str(stability),
                out_dir=str(root / "out"),
            )
            self.assertTrue(payload["claim_drafts"]["strong_comparative_claim_candidate"])

    def test_conservative_claim_allows_failure_quality_advantage(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_claim_cons_") as td:
            root = Path(td)
            matrix = root / "matrix.json"
            stability = root / "stability.json"
            matrix.write_text(
                json.dumps(
                    {
                        "provider_rows": [
                            {
                                "provider_name": "gateforge",
                                "clean_run_count": 2,
                                "median_infra_normalized_success_rate_pct": 90.0,
                                "median_avg_wall_clock_sec": 20.0,
                                "median_avg_omc_tool_call_count": 2.0,
                                "infra_failure_rate_pct": 0.0,
                                "auth_session_failure_rate_pct": 0.0,
                            },
                            {
                                "provider_name": "claude",
                                "clean_run_count": 3,
                                "median_infra_normalized_success_rate_pct": 88.0,
                                "median_avg_wall_clock_sec": 19.0,
                                "median_avg_omc_tool_call_count": 2.0,
                                "infra_failure_rate_pct": 20.0,
                                "auth_session_failure_rate_pct": 20.0,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            stability.write_text(json.dumps({"classification": "PROVISIONAL"}), encoding="utf-8")
            payload = build_claim_gate(
                paper_matrix_summary_path=str(matrix),
                claude_stability_summary_path=str(stability),
                gateforge_attribution_missing_rate_pct=0.0,
                gateforge_terminal_path_coverage_pct=85.0,
                out_dir=str(root / "out"),
            )
            self.assertTrue(payload["claim_drafts"]["conservative_claim_candidate"])
            self.assertTrue(payload["claim_drafts"]["failure_quality_advantage"])


if __name__ == "__main__":
    unittest.main()
