import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_curated_hard_unseen_manifest_v1 import (
    SCHEMA_VERSION,
    load_curated_hard_unseen_manifest,
    validate_curated_hard_unseen_manifest,
)


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


class AgentModelicaCuratedHardUnseenManifestV1Tests(unittest.TestCase):
    def test_validate_manifest_accepts_curated_pool(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for rel in ("LibA/A.mo", "LibA/B.mo", "LibB/C.mo", "LibB/D.mo", "LibC/E.mo", "LibC/F.mo"):
                _write_model(root / rel, Path(rel).stem)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "libraries": [
                            {
                                "library_id": "liba",
                                "package_name": "LibA",
                                "source_library": "LibA",
                                "license_provenance": "MIT",
                                "local_path": str(root / "LibA"),
                                "accepted_source_path": str(root / "LibA"),
                                "domain": "controls",
                                "seen_risk_band": "less_likely_seen",
                                "source_type": "public_repo",
                                "selection_reason": "curated",
                                "exposure_notes": "lower exposure",
                                "allowed_models": [
                                    {"model_id": "a", "qualified_model_name": "LibA.A", "model_path": str(root / "LibA/A.mo"), "seen_risk_band": "less_likely_seen", "source_type": "public_repo", "selection_reason": "curated", "exposure_notes": "low"},
                                    {"model_id": "b", "qualified_model_name": "LibA.B", "model_path": str(root / "LibA/B.mo"), "seen_risk_band": "less_likely_seen", "source_type": "public_repo", "selection_reason": "curated", "exposure_notes": "low"},
                                ],
                            },
                            {
                                "library_id": "libb",
                                "package_name": "LibB",
                                "source_library": "LibB",
                                "license_provenance": "MIT",
                                "local_path": str(root / "LibB"),
                                "accepted_source_path": str(root / "LibB"),
                                "domain": "signals",
                                "seen_risk_band": "hard_unseen",
                                "source_type": "internal_mirror",
                                "selection_reason": "curated",
                                "exposure_notes": "lower exposure",
                                "allowed_models": [
                                    {"model_id": "c", "qualified_model_name": "LibB.C", "model_path": str(root / "LibB/C.mo"), "seen_risk_band": "hard_unseen", "source_type": "internal_mirror", "selection_reason": "curated", "exposure_notes": "low"},
                                    {"model_id": "d", "qualified_model_name": "LibB.D", "model_path": str(root / "LibB/D.mo"), "seen_risk_band": "hard_unseen", "source_type": "internal_mirror", "selection_reason": "curated", "exposure_notes": "low"},
                                ],
                            },
                            {
                                "library_id": "libc",
                                "package_name": "LibC",
                                "source_library": "LibC",
                                "license_provenance": "MIT",
                                "local_path": str(root / "LibC"),
                                "accepted_source_path": str(root / "LibC"),
                                "domain": "signals",
                                "seen_risk_band": "less_likely_seen",
                                "source_type": "research_artifact",
                                "selection_reason": "curated",
                                "exposure_notes": "lower exposure",
                                "allowed_models": [
                                    {"model_id": "e", "qualified_model_name": "LibC.E", "model_path": str(root / "LibC/E.mo"), "seen_risk_band": "less_likely_seen", "source_type": "research_artifact", "selection_reason": "curated", "exposure_notes": "low"},
                                    {"model_id": "f", "qualified_model_name": "LibC.F", "model_path": str(root / "LibC/F.mo"), "seen_risk_band": "less_likely_seen", "source_type": "research_artifact", "selection_reason": "curated", "exposure_notes": "low"},
                                ],
                            },
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            payload = load_curated_hard_unseen_manifest(str(manifest))
            libraries, reasons = validate_curated_hard_unseen_manifest(payload)
            self.assertEqual(reasons, [])
            self.assertEqual(len(libraries), 3)

    def test_validate_manifest_rejects_missing_seen_fields(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_model(root / "LibA/A.mo", "A")
            _write_model(root / "LibA/B.mo", "B")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "libraries": [
                            {
                                "library_id": "liba",
                                "package_name": "LibA",
                                "source_library": "LibA",
                                "license_provenance": "MIT",
                                "local_path": str(root / "LibA"),
                                "accepted_source_path": str(root / "LibA"),
                                "domain": "controls",
                                "allowed_models": [
                                    {"model_id": "a", "qualified_model_name": "LibA.A", "model_path": str(root / "LibA/A.mo")},
                                    {"model_id": "b", "qualified_model_name": "LibA.B", "model_path": str(root / "LibA/B.mo")},
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            _libraries, reasons = validate_curated_hard_unseen_manifest(load_curated_hard_unseen_manifest(str(manifest)))
            self.assertIn("library_missing_field:liba:seen_risk_band", reasons)
            self.assertIn("model_missing_field:liba:a:seen_risk_band", reasons)


if __name__ == "__main__":
    unittest.main()
