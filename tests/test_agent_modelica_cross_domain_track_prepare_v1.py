from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_cross_domain_track_prepare_v1 import (
    build_filtered_source_manifest,
    build_prepare_commands,
    resolve_track_entry,
    run_prepare_track,
)


class AgentModelicaCrossDomainTrackPrepareV1Tests(unittest.TestCase):
    def test_resolve_track_entry(self) -> None:
        manifest = {
            "tracks": [
                {"track_id": "buildings_v1", "library": "Buildings"},
                {"track_id": "openipsl_v1", "library": "OpenIPSL"},
            ]
        }
        row = resolve_track_entry(manifest, "openipsl_v1")
        self.assertEqual(row.get("library"), "OpenIPSL")

    def test_build_filtered_source_manifest_keeps_single_source(self) -> None:
        manifest = {
            "schema_version": "seed",
            "sources": [
                {"source_id": "modelica_buildings_cross_domain"},
                {"source_id": "modelica_buildings_cross_domain", "scale_hint": "medium"},
                {"source_id": "openipsl_cross_domain"},
            ],
        }
        filtered = build_filtered_source_manifest(manifest, "modelica_buildings_cross_domain")
        self.assertEqual(len(filtered["sources"]), 2)
        self.assertTrue(all(x["source_id"] == "modelica_buildings_cross_domain" for x in filtered["sources"]))

    def test_build_prepare_commands_includes_track_filters(self) -> None:
        cmds = build_prepare_commands(
            out_dir="artifacts/x",
            filtered_source_manifest_path="artifacts/x/filtered.json",
            track_entry={
                "track_id": "buildings_v1",
                "library": "Buildings",
                "pack_label": "Buildings Cross-Domain",
                "include_patterns": ["Buildings/"],
                "library_load_models": ["Buildings"],
            },
            target_scales="small,medium,large",
            failure_types="model_check_error,simulate_error,semantic_regression",
            mutations_per_failure_type=2,
            max_models=6,
            per_scale_total=6,
            per_scale_failure_targets="2,2,2",
            frozen_root="assets_private/fixture",
            valid_only=True,
        )
        self.assertEqual(cmds[0]["name"], "harvest")
        self.assertEqual(cmds[2]["name"], "source_viability_filter")
        self.assertIn("--extra-model-load", cmds[2]["cmd"])
        self.assertEqual(cmds[3]["name"], "build_selection_plan")
        self.assertIn("--min-covered-scales", cmds[3]["cmd"])
        self.assertEqual(cmds[5]["name"], "lock_hardpack")
        self.assertEqual(cmds[5]["include_patterns"], ["Buildings/"])
        self.assertEqual(cmds[5]["library_load_models"], ["Buildings"])
        self.assertIn("--selection-plan", cmds[4]["cmd"])
        self.assertIn("--valid-only", cmds[6]["cmd"])

    def test_run_prepare_track_dry_run_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source_manifest = root / "source_manifest.json"
            track_manifest = root / "track_manifest.json"
            source_manifest.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "source_id": "modelica_buildings_cross_domain",
                                "mode": "local",
                                "local_path": "assets_private/modelica_sources/modelica_buildings",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            track_manifest.write_text(
                json.dumps(
                    {
                        "tracks": [
                            {
                                "track_id": "buildings_v1",
                                "library": "Buildings",
                                "source_manifest_source_id": "modelica_buildings_cross_domain",
                                "include_patterns": ["Buildings/"],
                                "library_load_models": ["Buildings"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out_dir = root / "out"
            summary = run_prepare_track(
                track_id="buildings_v1",
                source_manifest_path=str(source_manifest),
                track_manifest_path=str(track_manifest),
                out_dir=str(out_dir),
                frozen_root=str(root / "fixture"),
                dry_run=True,
                valid_only=True,
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertEqual(len(summary["steps"]), 7)
            self.assertEqual(summary["steps"][0]["status"], "PLANNED")

    def test_cli_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source_manifest = root / "source_manifest.json"
            track_manifest = root / "track_manifest.json"
            source_manifest.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "source_id": "openipsl_cross_domain",
                                "mode": "local",
                                "local_path": "assets_private/modelica_sources/openipsl",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            track_manifest.write_text(
                json.dumps(
                    {
                        "tracks": [
                            {
                                "track_id": "openipsl_v1",
                                "library": "OpenIPSL",
                                "source_manifest_source_id": "openipsl_cross_domain",
                                "include_patterns": ["OpenIPSL/"],
                                "library_load_models": ["OpenIPSL"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out_dir = root / "out"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_cross_domain_track_prepare_v1",
                    "--track-id",
                    "openipsl_v1",
                    "--source-manifest",
                    str(source_manifest),
                    "--track-manifest",
                    str(track_manifest),
                    "--out-dir",
                    str(out_dir),
                    "--frozen-root",
                    str(root / "fixture"),
                    "--valid-only",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("track_id"), "openipsl_v1")
            self.assertTrue(payload.get("dry_run"))


if __name__ == "__main__":
    unittest.main()
