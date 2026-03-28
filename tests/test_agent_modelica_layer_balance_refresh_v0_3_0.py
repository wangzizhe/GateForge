import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_layer_balance_refresh_v0_3_0 import build_layer_balance_refresh


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class AgentModelicaLayerBalanceRefreshV030Tests(unittest.TestCase):
    def test_refresh_adds_layer4_lane_and_reports_delta(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            base_spec = root / "base_spec.json"
            _write_json(
                base_spec,
                {
                    "lanes": [
                        {
                            "lane_id": "track_a",
                            "label": "Track A",
                            "sidecar": str(root / "track_a" / "layer_metadata.json"),
                        }
                    ]
                },
            )
            _write_json(
                root / "track_a" / "layer_metadata.json",
                {
                    "annotations": [
                        {"item_id": "a1", "difficulty_layer": "layer_2", "difficulty_layer_source": "observed"},
                        {"item_id": "a2", "difficulty_layer": "layer_4", "difficulty_layer_source": "observed"},
                    ]
                },
            )
            base_summary = root / "base_summary.json"
            _write_json(
                base_summary,
                {
                    "coverage_gap": {
                        "aggregate_layer_counts": {
                            "layer_2": 1,
                            "layer_4": 1,
                        }
                    }
                },
            )
            layer4_dir = root / "layer4"
            _write_json(
                layer4_dir / "layer_metadata.json",
                {
                    "annotations": [
                        {"item_id": "l1", "difficulty_layer": "layer_4", "difficulty_layer_source": "override"},
                        {"item_id": "l2", "difficulty_layer": "layer_4", "difficulty_layer_source": "override"},
                    ]
                },
            )
            _write_json(layer4_dir / "summary.json", {"status": "PASS"})
            out_dir = root / "out"
            payload = build_layer_balance_refresh(
                base_spec_path=str(base_spec),
                base_summary_path=str(base_summary),
                layer4_lane_dir=str(layer4_dir),
                out_dir=str(out_dir),
            )
            self.assertEqual(payload.get("status"), "PASS")
            self.assertEqual(int(payload["coverage_delta"]["layer4_case_count_delta"]), 2)
            self.assertEqual(int(payload["lane_count"]), 2)
            spec_payload = json.loads((out_dir / "spec.json").read_text(encoding="utf-8"))
            self.assertEqual(len(spec_payload.get("lanes") or []), 2)


if __name__ == "__main__":
    unittest.main()
