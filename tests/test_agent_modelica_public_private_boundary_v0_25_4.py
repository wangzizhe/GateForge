from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_public_private_boundary_v0_25_4 import (
    audit_manifest_rows,
    build_public_private_boundary_audit,
    scan_text_for_markers,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


class PublicPrivateBoundaryV0254Tests(unittest.TestCase):
    def test_scan_text_for_markers_finds_private_reference(self) -> None:
        findings = scan_text_for_markers(name="x", text="see assets_private/internal_docs")
        self.assertTrue(findings)

    def test_audit_manifest_rows_requires_smoke_public_only(self) -> None:
        findings = audit_manifest_rows([{"seed_id": "s", "split": "positive", "public_status": "public_fixture"}])
        self.assertEqual(findings[0]["finding"], "non_smoke_marked_public_fixture")

    def test_build_public_private_boundary_audit_passes_clean_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.jsonl"
            changelog = root / "CHANGELOG.md"
            out_dir = root / "out"
            _write_jsonl(manifest, [{"seed_id": "smoke", "split": "smoke", "public_status": "public_fixture", "artifact_references": ["a"]}])
            changelog.write_text("# Change log\n\nPublic summary only.\n", encoding="utf-8")
            summary = build_public_private_boundary_audit(
                manifest_rows_path=manifest,
                changelog_path=changelog,
                out_dir=out_dir,
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["finding_count"], 0)


if __name__ == "__main__":
    unittest.main()
