from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_layer4_holdout_pack_v0_3_1 import (
    build_layer4_holdout_pack_v0_3_1,
)


class AgentModelicaLayer4HoldoutPackV031Tests(unittest.TestCase):
    def test_build_holdout_pack_maps_taskset_into_hardpack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gf_holdout_pack_") as td:
            root = Path(td)
            model = root / "mutant.mo"
            source = root / "source.mo"
            lib_root = root / "Buildings"
            lib_model = lib_root / "Electrical" / "Loads.mo"
            model.write_text("model M end M;", encoding="utf-8")
            source.write_text("model M end M;", encoding="utf-8")
            lib_model.parent.mkdir(parents=True, exist_ok=True)
            lib_model.write_text("within Buildings.Electrical; model Loads end Loads;", encoding="utf-8")
            taskset = root / "taskset.json"
            taskset.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "task_id": "t1",
                                "scale": "small",
                                "failure_type": "runtime_fail",
                                "expected_stage": "simulate",
                                "mutated_model_path": str(model),
                                "source_model_path": str(source),
                                "v0_3_family_id": "runtime_numerical_instability",
                                "expected_layer_hint": "layer_4",
                                "split": "holdout",
                                "source_library": "buildings",
                                "domain": "building_electrical",
                                "source_meta": {
                                    "accepted_source_path": str(lib_root),
                                    "package_name": "Buildings",
                                    "qualified_model_name": "Buildings.Electrical.Loads",
                                    "model_path": str(lib_model),
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out_dir = root / "out"
            payload = build_layer4_holdout_pack_v0_3_1(taskset_path=str(taskset), out_dir=str(out_dir))
            self.assertEqual(payload["status"], "PASS")
            hardpack = json.loads((out_dir / "hardpack_frozen.json").read_text(encoding="utf-8"))
            self.assertEqual(hardpack["case_count"], 1)
            self.assertEqual(hardpack["library_load_models"], ["Buildings"])
            case = hardpack["cases"][0]
            self.assertEqual(case["mutation_id"], "t1")
            self.assertEqual(case["source_package_name"], "Buildings")
            self.assertEqual(case["source_qualified_model_name"], "Buildings.Electrical.Loads")


if __name__ == "__main__":
    unittest.main()
