from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_track_c_candidate_attribution_refresh_v0_3_3 import refresh_candidate_attribution


class AgentModelicaTrackCCandidateAttributionRefreshV033Tests(unittest.TestCase):
    def test_refresh_candidate_attribution_attaches_resolution_fields(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_v033_attr_") as td:
            root = Path(td)
            candidates = root / "candidates.json"
            results = root / "results.json"
            candidates.write_text(json.dumps({"tasks": [{"task_id": "cand_a"}]}), encoding="utf-8")
            results.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "mutation_id": "cand_a",
                                "resolution_path": "llm_planner_assisted",
                                "planner_invoked": True,
                                "rounds_used": 2,
                                "llm_request_count": 1,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = refresh_candidate_attribution(
                candidate_taskset_path=str(candidates),
                results_paths=[str(results)],
                out_dir=str(root / "out"),
            )
            row = payload["tasks"][0]
            self.assertEqual(row["resolution_path"], "llm_planner_assisted")
            self.assertEqual(row["attribution_status"], "attributed")
            self.assertEqual(payload["metrics"]["attributed_count"], 1)


if __name__ == "__main__":
    unittest.main()
