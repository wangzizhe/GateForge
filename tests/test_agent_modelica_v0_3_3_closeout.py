from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_v0_3_3_closeout import build_v0_3_3_closeout


class AgentModelicaV033CloseoutTests(unittest.TestCase):
    def test_build_v0_3_3_closeout_classifies_paper_usable_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_closeout_") as td:
            root = Path(td)
            primary = root / "primary.json"
            matrix = root / "matrix.json"
            stability = root / "stability.json"
            claim = root / "claim.json"

            primary.write_text(
                json.dumps(
                    {
                        "status": "PRIMARY_READY",
                        "admitted_count": 20,
                        "planner_sensitive_pct": 100.0,
                        "deterministic_only_pct": 0.0,
                    }
                ),
                encoding="utf-8",
            )
            matrix.write_text(
                json.dumps(
                    {
                        "provider_rows": [
                            {
                                "provider_name": "gateforge",
                                "median_infra_normalized_success_rate_pct": 100.0,
                                "clean_run_count": 2,
                                "main_table_eligible": True,
                            },
                            {
                                "provider_name": "claude",
                                "median_infra_normalized_success_rate_pct": 80.0,
                                "clean_run_count": 3,
                                "main_table_eligible": True,
                            },
                            {
                                "provider_name": "codex",
                                "median_infra_normalized_success_rate_pct": 75.0,
                                "clean_run_count": 1,
                                "main_table_eligible": True,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            stability.write_text(
                json.dumps(
                    {
                        "classification": "STABLE",
                        "switch_required": False,
                        "metrics": {"clean_run_count": 3},
                    }
                ),
                encoding="utf-8",
            )
            claim.write_text(
                json.dumps(
                    {
                        "claim_drafts": {
                            "strong_comparative_claim_candidate": True,
                            "conservative_claim_candidate": True,
                        }
                    }
                ),
                encoding="utf-8",
            )

            payload = build_v0_3_3_closeout(
                primary_slice_summary_path=str(primary),
                paper_matrix_summary_path=str(matrix),
                primary_provider_stability_summary_path=str(stability),
                claim_gate_summary_path=str(claim),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["classification"], "paper_usable_comparative_path")
            self.assertTrue(payload["metrics"]["strong_claim_candidate"])

    def test_build_v0_3_3_closeout_classifies_api_direct_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_closeout_") as td:
            root = Path(td)
            primary = root / "primary.json"
            matrix = root / "matrix.json"
            stability = root / "stability.json"
            claim = root / "claim.json"

            primary.write_text(json.dumps({"status": "PRIMARY_READY"}), encoding="utf-8")
            matrix.write_text(json.dumps({"provider_rows": []}), encoding="utf-8")
            stability.write_text(
                json.dumps({"classification": "API_DIRECT_SWITCH_REQUIRED", "switch_required": True, "metrics": {"clean_run_count": 0}}),
                encoding="utf-8",
            )
            claim.write_text(json.dumps({"claim_drafts": {}}), encoding="utf-8")

            payload = build_v0_3_3_closeout(
                primary_slice_summary_path=str(primary),
                paper_matrix_summary_path=str(matrix),
                primary_provider_stability_summary_path=str(stability),
                claim_gate_summary_path=str(claim),
                out_dir=str(root / "out"),
            )
            self.assertEqual(payload["classification"], "cli_unstable_api_direct_fallback")

    def test_build_v0_3_3_closeout_classifies_development_shift_when_primary_ready(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_closeout_") as td:
            root = Path(td)
            primary = root / "primary.json"
            matrix = root / "matrix.json"
            stability = root / "stability.json"
            claim = root / "claim.json"

            primary.write_text(
                json.dumps(
                    {
                        "status": "PRIMARY_READY",
                        "admitted_count": 20,
                        "planner_sensitive_pct": 100.0,
                        "deterministic_only_pct": 0.0,
                    }
                ),
                encoding="utf-8",
            )
            matrix.write_text(
                json.dumps(
                    {
                        "provider_rows": [
                            {"provider_name": "gateforge", "median_infra_normalized_success_rate_pct": 100.0, "clean_run_count": 2, "main_table_eligible": True},
                            {"provider_name": "claude", "median_infra_normalized_success_rate_pct": 25.0, "clean_run_count": 0, "main_table_eligible": False},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            stability.write_text(
                json.dumps(
                    {
                        "classification": "PROVISIONAL",
                        "switch_required": False,
                        "metrics": {"clean_run_count": 0},
                    }
                ),
                encoding="utf-8",
            )
            claim.write_text(json.dumps({"claim_drafts": {"strong_comparative_claim_candidate": False, "conservative_claim_candidate": False}}), encoding="utf-8")

            payload = build_v0_3_3_closeout(
                primary_slice_summary_path=str(primary),
                paper_matrix_summary_path=str(matrix),
                primary_provider_stability_summary_path=str(stability),
                claim_gate_summary_path=str(claim),
                out_dir=str(root / "out"),
                prefer_development_shift=True,
            )
            self.assertEqual(payload["classification"], "development_priorities_shifted_comparative_path_retained")


if __name__ == "__main__":
    unittest.main()
