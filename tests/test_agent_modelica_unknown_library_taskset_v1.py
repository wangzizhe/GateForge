import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _write_model(path: Path, model_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"model {model_name}",
                "  Modelica.Blocks.Sources.Constant src(k=1);",
                "  Modelica.Blocks.Math.Gain gain(k=2);",
                "equation",
                "  connect(src.y, gain.u);",
                f"end {model_name};",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _manifest_payload(root: Path) -> dict:
    liba = root / "LibA"
    libb = root / "LibB"
    models = [
        liba / "ModelA.mo",
        liba / "ModelB.mo",
        libb / "ModelC.mo",
        libb / "ModelD.mo",
    ]
    for path in models:
        _write_model(path, path.stem)
    return {
        "schema_version": "agent_modelica_unknown_library_pool_manifest_v1",
        "libraries": [
            {
                "library_id": "liba",
                "package_name": "LibA",
                "source_library": "LibA",
                "license_provenance": "MIT",
                "local_path": str(liba),
                "accepted_source_path": str(liba),
                "domain": "controls",
                "component_interface_hints": ["gain"],
                "connector_semantic_hints": ["u", "y"],
                "allowed_models": [
                    {"model_id": "ma", "qualified_model_name": "LibA.ModelA", "model_path": str(liba / "ModelA.mo"), "scale_hint": "small"},
                    {"model_id": "mb", "qualified_model_name": "LibA.ModelB", "model_path": str(liba / "ModelB.mo"), "scale_hint": "small"},
                ],
            },
            {
                "library_id": "libb",
                "package_name": "LibB",
                "source_library": "LibB",
                "license_provenance": "MIT",
                "local_path": str(libb),
                "accepted_source_path": str(libb),
                "domain": "signals",
                "component_interface_hints": ["src"],
                "connector_semantic_hints": ["u", "y"],
                "allowed_models": [
                    {"model_id": "mc", "qualified_model_name": "LibB.ModelC", "model_path": str(libb / "ModelC.mo"), "scale_hint": "small"},
                    {"model_id": "md", "qualified_model_name": "LibB.ModelD", "model_path": str(libb / "ModelD.mo"), "scale_hint": "small"},
                ],
            },
        ],
    }


class AgentModelicaUnknownLibraryTasksetV1Tests(unittest.TestCase):
    def test_builder_produces_frozen_taskset_with_complete_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(_manifest_payload(root), indent=2), encoding="utf-8")
            out_dir = root / "out"

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_unknown_library_taskset_v1",
                    "--manifest",
                    str(manifest),
                    "--out-dir",
                    str(out_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            taskset = json.loads((out_dir / "taskset_frozen.json").read_text(encoding="utf-8"))
            self.assertEqual(summary.get("status"), "PASS")
            self.assertEqual(int(summary.get("total_tasks") or 0), 12)
            self.assertEqual(float(summary.get("provenance_completeness_pct") or 0.0), 100.0)
            self.assertEqual(float(summary.get("library_hints_nonempty_pct") or 0.0), 100.0)
            first = taskset["tasks"][0]
            self.assertTrue(first.get("source_meta"))
            self.assertTrue(first.get("library_hints"))
            self.assertTrue(first.get("component_hints"))
            self.assertTrue(first.get("connector_hints"))

    def test_builder_split_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(_manifest_payload(root), indent=2), encoding="utf-8")
            out_a = root / "out_a"
            out_b = root / "out_b"
            base_cmd = [
                sys.executable,
                "-m",
                "gateforge.agent_modelica_unknown_library_taskset_v1",
                "--manifest",
                str(manifest),
                "--seed",
                "seed123",
            ]
            proc_a = subprocess.run(base_cmd + ["--out-dir", str(out_a)], capture_output=True, text=True, check=False)
            proc_b = subprocess.run(base_cmd + ["--out-dir", str(out_b)], capture_output=True, text=True, check=False)
            self.assertEqual(proc_a.returncode, 0, msg=proc_a.stderr or proc_a.stdout)
            self.assertEqual(proc_b.returncode, 0, msg=proc_b.stderr or proc_b.stdout)
            taskset_a = json.loads((out_a / "taskset_frozen.json").read_text(encoding="utf-8"))
            taskset_b = json.loads((out_b / "taskset_frozen.json").read_text(encoding="utf-8"))
            split_a = {row["task_id"]: row["split"] for row in taskset_a["tasks"]}
            split_b = {row["task_id"]: row["split"] for row in taskset_b["tasks"]}
            self.assertEqual(split_a, split_b)


if __name__ == "__main__":
    unittest.main()

