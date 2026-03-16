import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_wave2_realism_manifest_v1 import (
    load_wave2_realism_manifest,
    validate_wave2_realism_manifest,
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


class AgentModelicaWave2RealismManifestV1Tests(unittest.TestCase):
    def test_validate_accepts_minimal_valid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            paths = [root / f"LibA/M{i}.mo" for i in range(6)]
            for path in paths:
                _write_model(path, path.stem)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "agent_modelica_wave2_realism_pack_manifest_v1",
                        "libraries": [
                            {
                                "library_id": "liba",
                                "package_name": "LibA",
                                "source_library": "LibA",
                                "license_provenance": "MIT",
                                "domain": "controls",
                                "seen_risk_band": "less_likely_seen",
                                "source_type": "public_repo",
                                "selection_reason": "a",
                                "exposure_notes": "a",
                                "allowed_models": [
                                    {"model_id": "m0", "qualified_model_name": "LibA.M0", "model_path": str(paths[0]), "seen_risk_band": "less_likely_seen", "source_type": "public_repo", "selection_reason": "x", "exposure_notes": "x"},
                                    {"model_id": "m1", "qualified_model_name": "LibA.M1", "model_path": str(paths[1]), "seen_risk_band": "less_likely_seen", "source_type": "public_repo", "selection_reason": "x", "exposure_notes": "x"},
                                    {"model_id": "m2", "qualified_model_name": "LibA.M2", "model_path": str(paths[2]), "seen_risk_band": "less_likely_seen", "source_type": "public_repo", "selection_reason": "x", "exposure_notes": "x"},
                                ],
                            },
                            {
                                "library_id": "libb",
                                "package_name": "LibB",
                                "source_library": "LibB",
                                "license_provenance": "MIT",
                                "domain": "signals",
                                "seen_risk_band": "hard_unseen",
                                "source_type": "internal_mirror",
                                "selection_reason": "b",
                                "exposure_notes": "b",
                                "allowed_models": [
                                    {"model_id": "m3", "qualified_model_name": "LibB.M3", "model_path": str(paths[3]), "seen_risk_band": "hard_unseen", "source_type": "internal_mirror", "selection_reason": "x", "exposure_notes": "x"},
                                    {"model_id": "m4", "qualified_model_name": "LibB.M4", "model_path": str(paths[4]), "seen_risk_band": "hard_unseen", "source_type": "internal_mirror", "selection_reason": "x", "exposure_notes": "x"},
                                    {"model_id": "m5", "qualified_model_name": "LibB.M5", "model_path": str(paths[5]), "seen_risk_band": "hard_unseen", "source_type": "internal_mirror", "selection_reason": "x", "exposure_notes": "x"},
                                ],
                            },
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            payload = load_wave2_realism_manifest(str(manifest))
            libraries, reasons = validate_wave2_realism_manifest(payload)
            self.assertEqual(len(libraries), 2)
            self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
