import json
import os
import subprocess
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


def _manifest(root: Path) -> Path:
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
    ):
        _write_model(path, path.stem)
    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
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
                        "selection_reason": "selection liba",
                        "exposure_notes": "notes liba",
                        "component_interface_hints": ["gain"],
                        "connector_semantic_hints": ["u", "y"],
                        "allowed_models": [
                            {"model_id": "a", "qualified_model_name": "LibA.A", "model_path": str(liba / "A.mo"), "scale_hint": "small", "seen_risk_band": "less_likely_seen", "source_type": "public_repo", "selection_reason": "a", "exposure_notes": "a"},
                            {"model_id": "b", "qualified_model_name": "LibA.B", "model_path": str(liba / "B.mo"), "scale_hint": "small", "seen_risk_band": "less_likely_seen", "source_type": "public_repo", "selection_reason": "b", "exposure_notes": "b"},
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
                        "selection_reason": "selection libb",
                        "exposure_notes": "notes libb",
                        "component_interface_hints": ["src"],
                        "connector_semantic_hints": ["u", "y"],
                        "allowed_models": [
                            {"model_id": "c", "qualified_model_name": "LibB.C", "model_path": str(libb / "C.mo"), "scale_hint": "small", "seen_risk_band": "hard_unseen", "source_type": "internal_mirror", "selection_reason": "c", "exposure_notes": "c"},
                            {"model_id": "d", "qualified_model_name": "LibB.D", "model_path": str(libb / "D.mo"), "scale_hint": "small", "seen_risk_band": "hard_unseen", "source_type": "internal_mirror", "selection_reason": "d", "exposure_notes": "d"},
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
                        "seen_risk_band": "hard_unseen",
                        "source_type": "research_artifact",
                        "selection_reason": "selection libc",
                        "exposure_notes": "notes libc",
                        "component_interface_hints": ["const"],
                        "connector_semantic_hints": ["u", "y"],
                        "allowed_models": [
                            {"model_id": "e", "qualified_model_name": "LibC.E", "model_path": str(libc / "E.mo"), "scale_hint": "small", "seen_risk_band": "hard_unseen", "source_type": "research_artifact", "selection_reason": "e", "exposure_notes": "e"},
                            {"model_id": "f", "qualified_model_name": "LibC.F", "model_path": str(libc / "F.mo"), "scale_hint": "small", "seen_risk_band": "hard_unseen", "source_type": "research_artifact", "selection_reason": "f", "exposure_notes": "f"},
                        ],
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest


class RunAgentModelicaCuratedHardUnseenEvidenceV1Tests(unittest.TestCase):
    def test_mock_evidence_chain_produces_hard_unseen_summaries(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_curated_hard_unseen_evidence_v1.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = _manifest(root)
            out_dir = root / "out"
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_CURATED_HARD_UNSEEN_MANIFEST": str(manifest),
                    "GATEFORGE_AGENT_CURATED_HARD_UNSEEN_EVIDENCE_OUT_DIR": str(out_dir),
                    "GATEFORGE_AGENT_CURATED_HARD_UNSEEN_REPAIR_MEMORY": str(root / "missing_memory.json"),
                },
                timeout=900,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            baseline = json.loads((out_dir / "hard_unseen_baseline_summary.json").read_text(encoding="utf-8"))
            evidence = json.loads((out_dir / "evidence_summary.json").read_text(encoding="utf-8"))
            decision = json.loads((out_dir / "decision_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(baseline.get("status"), "PASS")
            self.assertIn("hard_unseen", baseline.get("counts_by_seen_risk_band", {}))
            self.assertIn("internal_mirror", baseline.get("counts_by_source_type", {}))
            self.assertIn("baseline_saturation_status", evidence)
            self.assertIn("retrieval_uplift_status", decision)


if __name__ == "__main__":
    unittest.main()
