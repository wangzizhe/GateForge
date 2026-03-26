import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentModelicaHardpackLockV1Tests(unittest.TestCase):
    def test_hardpack_lock_builds_deterministic_pack(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            out = root / "hardpack.json"
            rows = []
            idx = 0
            for scale in ["small", "medium", "large"]:
                for ftype in ["model_check_error", "simulate_error", "semantic_regression"]:
                    for _ in range(2):
                        idx += 1
                        rows.append(
                            {
                                "mutation_id": f"m_{idx}",
                                "target_scale": scale,
                                "expected_failure_type": ftype,
                                "expected_stage": "simulate",
                                "source_model_path": f"{scale}_{ftype}.mo",
                                "mutated_model_path": f"{scale}_{ftype}_mut.mo",
                            }
                        )
            manifest.write_text(json.dumps({"mutations": rows}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_hardpack_lock_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--per-scale-total",
                    "3",
                    "--per-scale-failure-targets",
                    "1,1,1",
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
            self.assertEqual(int(payload.get("total_cases", 0)), 9)
            cbs = payload.get("counts_by_scale", {})
            self.assertEqual(cbs, {"small": 3, "medium": 3, "large": 3})

    def test_hardpack_lock_filters_rows_by_include_pattern_and_sets_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            out = root / "hardpack.json"
            rows = [
                {
                    "mutation_id": "m_buildings_1",
                    "target_model_id": "osm_modelica_buildings_aaa",
                    "target_scale": "medium",
                    "expected_failure_type": "model_check_error",
                    "expected_stage": "check",
                    "source_model_path": "assets_private/modelica_sources/modelica_buildings/Buildings/Examples/X.mo",
                    "mutated_model_path": "mutants/buildings/m1.mo",
                },
                {
                    "mutation_id": "m_openipsl_1",
                    "target_model_id": "osm_openipsl_bbb",
                    "target_scale": "medium",
                    "expected_failure_type": "model_check_error",
                    "expected_stage": "check",
                    "source_model_path": "assets_private/modelica_sources/openipsl/OpenIPSL/Examples/Y.mo",
                    "mutated_model_path": "mutants/openipsl/m1.mo",
                },
            ]
            manifest.write_text(json.dumps({"mutations": rows}), encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_hardpack_lock_v1",
                    "--mutation-manifest",
                    str(manifest),
                    "--include-pattern",
                    "modelica_buildings|Buildings/",
                    "--per-scale-total",
                    "1",
                    "--per-scale-failure-targets",
                    "1,0,0",
                    "--track-id",
                    "buildings_v1",
                    "--pack-label",
                    "Buildings Cross-Domain",
                    "--library-load-model",
                    "Buildings",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("track_id"), "buildings_v1")
            self.assertEqual(payload.get("pack_label"), "Buildings Cross-Domain")
            self.assertEqual(payload.get("library_load_models"), ["Buildings"])
            self.assertEqual(payload.get("filtered_row_count"), 1)
            self.assertEqual(len(payload.get("cases") or []), 1)
            self.assertEqual(payload["cases"][0]["mutation_id"], "m_buildings_1")


if __name__ == "__main__":
    unittest.main()
