from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_track_c_matrix_v0_3_1 import (
    build_gateforge_bundle_from_results,
    summarize_track_c_matrix,
)


class AgentModelicaTrackCMatrixV031Tests(unittest.TestCase):
    def test_build_gateforge_bundle_from_results_normalizes_rows(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_tcm_") as td:
            root = Path(td)
            results = root / "gf_results.json"
            results.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "mutation_id": "t1",
                                "success": True,
                                "rounds_used": 2,
                                "elapsed_sec": 10.0,
                                "resolution_path": "rule_then_llm",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            normalized = build_gateforge_bundle_from_results(results_path=str(results), out_path=str(root / "bundle.json"))
            self.assertEqual(normalized["provider_name"], "gateforge")
            self.assertEqual(normalized["summary"]["success_count"], 1)

    def test_summarize_track_c_matrix_builds_variance_rows(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_tcm_") as td:
            root = Path(td)
            bundle_a = root / "a.json"
            bundle_b = root / "b.json"
            for path, provider, rate, infra in [
                (bundle_a, "gateforge", 100.0, 0),
                (bundle_b, "claude", 60.0, 1),
            ]:
                path.write_text(
                    json.dumps(
                        {
                            "provider_name": provider,
                            "arm_id": "arm1",
                            "model_id": f"{provider}-model",
                            "record_count": 5,
                            "records": [{"success": True, "infra_failure": False}] * 5,
                            "summary": {"success_rate_pct": rate, "infra_failure_count": infra},
                        }
                    ),
                    encoding="utf-8",
                )
            payload = summarize_track_c_matrix(bundle_paths=[str(bundle_a), str(bundle_b)], out_dir=str(root / "out"))
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(len(payload["grouped_rows"]), 2)


if __name__ == "__main__":
    unittest.main()
