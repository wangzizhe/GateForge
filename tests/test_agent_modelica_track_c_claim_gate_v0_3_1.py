from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_track_c_claim_gate_v0_3_1 import build_claim_gate


class AgentModelicaTrackCClaimGateV031Tests(unittest.TestCase):
    def test_claim_gate_reports_advantage_when_gateforge_leads(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_tcc_") as td:
            root = Path(td)
            matrix = root / "matrix.json"
            matrix.write_text(
                json.dumps(
                    {
                        "grouped_rows": [
                            {
                                "provider_name": "gateforge",
                                "arm_id": "gateforge_full",
                                "model_id": "gateforge-v0.3.1/auto",
                                "infra_normalized_success_rate_pct": 80.0,
                                "infra_failure_rate_pct": 0.0,
                            },
                            {
                                "provider_name": "claude",
                                "arm_id": "arm1_general_agent",
                                "model_id": "claude-opus",
                                "infra_normalized_success_rate_pct": 70.0,
                                "infra_failure_rate_pct": 0.0,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_claim_gate(matrix_summary_path=str(matrix), out_dir=str(root / "out"))
            self.assertEqual(payload["classification"], "advantage")


if __name__ == "__main__":
    unittest.main()
