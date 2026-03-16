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
    libc = root / "LibC"
    for path in (
        liba / "A.mo",
        liba / "B.mo",
        libb / "C.mo",
        libb / "D.mo",
        libc / "E.mo",
        libc / "F.mo",
        libc / "G.mo",
    ):
        _write_model(path, path.stem)
    return {
        "schema_version": "agent_modelica_curated_hard_unseen_pool_manifest_v1",
        "libraries": [
            {
                "library_id": "liba",
                "package_name": "LibA",
                "source_library": "LibA",
                "license_provenance": "MIT",
                "local_path": str(liba),
                "accepted_source_path": str(liba),
                "domain": "controls",
                "seen_risk_band": "less_likely_seen",
                "source_type": "public_repo",
                "selection_reason": "less common controls examples",
                "exposure_notes": "limited public exposure",
                "component_interface_hints": ["gain"],
                "connector_semantic_hints": ["u", "y"],
                "allowed_models": [
                    {
                        "model_id": "a",
                        "qualified_model_name": "LibA.A",
                        "model_path": str(liba / "A.mo"),
                        "scale_hint": "small",
                        "seen_risk_band": "less_likely_seen",
                        "source_type": "public_repo",
                        "selection_reason": "selection A",
                        "exposure_notes": "notes A",
                    },
                    {
                        "model_id": "b",
                        "qualified_model_name": "LibA.B",
                        "model_path": str(liba / "B.mo"),
                        "scale_hint": "small",
                        "seen_risk_band": "less_likely_seen",
                        "source_type": "public_repo",
                        "selection_reason": "selection B",
                        "exposure_notes": "notes B",
                    },
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
                "seen_risk_band": "hard_unseen",
                "source_type": "internal_mirror",
                "selection_reason": "hard unseen signals",
                "exposure_notes": "mirror only",
                "component_interface_hints": ["src"],
                "connector_semantic_hints": ["u", "y"],
                "allowed_models": [
                    {
                        "model_id": "c",
                        "qualified_model_name": "LibB.C",
                        "model_path": str(libb / "C.mo"),
                        "scale_hint": "small",
                        "seen_risk_band": "hard_unseen",
                        "source_type": "internal_mirror",
                        "selection_reason": "selection C",
                        "exposure_notes": "notes C",
                    },
                    {
                        "model_id": "d",
                        "qualified_model_name": "LibB.D",
                        "model_path": str(libb / "D.mo"),
                        "scale_hint": "small",
                        "seen_risk_band": "hard_unseen",
                        "source_type": "internal_mirror",
                        "selection_reason": "selection D",
                        "exposure_notes": "notes D",
                    },
                ],
            },
            {
                "library_id": "libc",
                "package_name": "LibC",
                "source_library": "LibC",
                "license_provenance": "MIT",
                "local_path": str(libc),
                "accepted_source_path": str(libc),
                "domain": "power",
                "seen_risk_band": "known_public",
                "source_type": "research_artifact",
                "selection_reason": "mixed selection",
                "exposure_notes": "one public, one hard unseen",
                "component_interface_hints": ["const"],
                "connector_semantic_hints": ["u", "y"],
                "allowed_models": [
                    {
                        "model_id": "e",
                        "qualified_model_name": "LibC.E",
                        "model_path": str(libc / "E.mo"),
                        "scale_hint": "small",
                        "seen_risk_band": "known_public",
                        "source_type": "research_artifact",
                        "selection_reason": "selection E",
                        "exposure_notes": "notes E",
                    },
                    {
                        "model_id": "f",
                        "qualified_model_name": "LibC.F",
                        "model_path": str(libc / "F.mo"),
                        "scale_hint": "small",
                        "seen_risk_band": "hard_unseen",
                        "source_type": "research_artifact",
                        "selection_reason": "selection F",
                        "exposure_notes": "notes F",
                    },
                    {
                        "model_id": "g",
                        "qualified_model_name": "LibC.G",
                        "model_path": str(libc / "G.mo"),
                        "scale_hint": "small",
                        "seen_risk_band": "hard_unseen",
                        "source_type": "research_artifact",
                        "selection_reason": "selection G",
                        "exposure_notes": "notes G",
                    },
                ],
            },
        ],
    }


class AgentModelicaCuratedHardUnseenTasksetV1Tests(unittest.TestCase):
    def test_builder_filters_to_less_likely_seen_and_hard_unseen(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(_manifest_payload(root), indent=2), encoding="utf-8")
            out_dir = root / "out"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_curated_hard_unseen_taskset_v1",
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
            self.assertEqual(int(summary.get("total_tasks") or 0), 18)
            self.assertEqual(int(summary.get("selected_model_count") or 0), 6)
            self.assertEqual(float(summary.get("provenance_completeness_pct") or 0.0), 100.0)
            self.assertEqual(float(summary.get("library_hints_nonempty_pct") or 0.0), 100.0)
            self.assertEqual(summary.get("counts_by_seen_risk_band"), {"hard_unseen": 12, "less_likely_seen": 6})
            self.assertEqual(summary.get("counts_by_source_type"), {"internal_mirror": 6, "public_repo": 6, "research_artifact": 6})
            bands = {row["task_id"]: row.get("seen_risk_band") for row in taskset["tasks"]}
            self.assertFalse(any(task_id.startswith("hardunseen_libc_e_") for task_id in bands))
            self.assertEqual(set(bands.values()), {"less_likely_seen", "hard_unseen"})

    def test_builder_applies_source_unstable_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(_manifest_payload(root), indent=2), encoding="utf-8")
            exclusions = root / "source_unstable.json"
            exclusions.write_text(
                json.dumps(
                    {
                        "schema_version": "agent_modelica_curated_hard_unseen_source_unstable_exclusions_v1",
                        "qualified_model_names": ["LibB.C"],
                        "model_ids": ["c"],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            out_dir = root / "out"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_curated_hard_unseen_taskset_v1",
                    "--manifest",
                    str(manifest),
                    "--out-dir",
                    str(out_dir),
                    "--exclude-models-json",
                    str(exclusions),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            task_ids = [row["task_id"] for row in json.loads((out_dir / "taskset_frozen.json").read_text(encoding="utf-8"))["tasks"]]
            self.assertEqual(int(summary.get("excluded_model_count") or 0), 1)
            self.assertIn("task_count_below_target", summary.get("reasons") or [])
            self.assertFalse(any(task_id.startswith("hardunseen_libb_c_") for task_id in task_ids))


if __name__ == "__main__":
    unittest.main()
