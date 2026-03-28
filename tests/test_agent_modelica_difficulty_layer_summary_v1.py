import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_difficulty_layer_summary_v1 import build_summary


class AgentModelicaDifficultyLayerSummaryV1Tests(unittest.TestCase):
    def test_build_summary_aggregates_lane_layer_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sidecar = root / "sidecar.json"
            sidecar.write_text(
                json.dumps(
                    {
                        "annotations": [
                            {
                                "item_id": "m1",
                                "difficulty_layer": "layer_2",
                                "difficulty_layer_source": "observed",
                            },
                            {
                                "item_id": "m2",
                                "difficulty_layer": "layer_3",
                                "difficulty_layer_source": "override",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            gf = root / "gf.json"
            gf.write_text(json.dumps({"results": [{"mutation_id": "m1", "success": True}, {"mutation_id": "m2", "success": False}]}), encoding="utf-8")
            comparison = root / "comparison.json"
            comparison.write_text(json.dumps({"bare_llm_results": [{"mutation_id": "m1", "success": False}, {"mutation_id": "m2", "success": True}]}), encoding="utf-8")
            spec = {
                "lanes": [
                    {
                        "lane_id": "track_a",
                        "label": "Track A",
                        "sidecar": str(sidecar),
                        "gf_results": str(gf),
                        "comparison_summary": str(comparison),
                    }
                ]
            }
            payload = build_summary(spec)
            lane = payload["lanes"][0]
            self.assertEqual(lane["per_layer"]["layer_2"]["gateforge_success_rate_pct"], 100.0)
            self.assertEqual(lane["per_layer"]["layer_3"]["bare_success_rate_pct"], 100.0)
            self.assertEqual(lane["per_layer"]["layer_3"]["override_ratio"], 100.0)
            self.assertIn("layer_1", lane["missing_layers"])

    def test_build_summary_uses_run_results_for_planner_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sidecar = root / "sidecar.json"
            sidecar.write_text(
                json.dumps(
                    {
                        "annotations": [
                            {
                                "item_id": "t1",
                                "difficulty_layer": "layer_3",
                                "difficulty_layer_source": "observed",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            run_results = root / "run_results.json"
            run_results.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "task_id": "t1",
                                "passed": True,
                                "planner_invoked": True,
                                "replay_used": False,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            payload = build_summary(
                {
                    "lanes": [
                        {
                            "lane_id": "planner_sensitive",
                            "sidecar": str(sidecar),
                            "run_results": str(run_results),
                        }
                    ]
                }
            )
            lane = payload["lanes"][0]
            self.assertEqual(lane["per_layer"]["layer_3"]["gateforge_success_rate_pct"], 100.0)
            self.assertEqual(lane["per_layer"]["layer_3"]["planner_invoked_rate_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
