from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateforge.agent_modelica_substrate_seed_import_v0_25_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST_ROWS_PATH = REPO_ROOT / "artifacts" / "substrate_manifest_v0_25_3" / "manifest_rows.jsonl"
DEFAULT_CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "public_private_boundary_audit_v0_25_4"
SENSITIVE_MARKERS = [
    "assets_private",
    "internal_docs",
    "CHANGELOG_INTERNAL",
    "ROADMAP_V0_",
    "mutation_mapping",
    "taxonomy",
    "/Users/",
]


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def scan_text_for_markers(*, name: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for marker in SENSITIVE_MARKERS:
        if marker in text:
            findings.append({"source": name, "marker": marker})
    return findings


def audit_manifest_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in rows:
        seed_id = str(row.get("seed_id") or "")
        public_status = str(row.get("public_status") or "")
        split = str(row.get("split") or "")
        if split != "smoke" and public_status == "public_fixture":
            findings.append({"seed_id": seed_id, "finding": "non_smoke_marked_public_fixture"})
        if split == "smoke" and public_status != "public_fixture":
            findings.append({"seed_id": seed_id, "finding": "smoke_not_marked_public_fixture"})
        for artifact_ref in row.get("artifact_references") or []:
            ref = str(artifact_ref)
            for marker in SENSITIVE_MARKERS:
                if marker in ref:
                    findings.append({"seed_id": seed_id, "finding": "sensitive_artifact_reference", "marker": marker})
    return findings


def build_public_private_boundary_audit(
    *,
    manifest_rows_path: Path = DEFAULT_MANIFEST_ROWS_PATH,
    changelog_path: Path = DEFAULT_CHANGELOG_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    manifest_rows = load_jsonl(manifest_rows_path)
    manifest_findings = audit_manifest_rows(manifest_rows)
    changelog_findings = scan_text_for_markers(name="CHANGELOG.md", text=read_text(changelog_path))
    all_findings = manifest_findings + changelog_findings
    missing_inputs = []
    if not manifest_rows:
        missing_inputs.append("manifest_rows")
    if not changelog_path.exists():
        missing_inputs.append("CHANGELOG.md")
    status = "PASS" if not missing_inputs and not all_findings else "REVIEW"
    summary = {
        "version": "v0.25.4",
        "status": status,
        "analysis_scope": "public_private_boundary_audit",
        "manifest_row_count": len(manifest_rows),
        "missing_inputs": missing_inputs,
        "finding_count": len(all_findings),
        "manifest_finding_count": len(manifest_findings),
        "changelog_finding_count": len(changelog_findings),
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "public_changelog_is_release_summary_not_experiment_log": True,
            "private_details_stay_in_assets_private": True,
        },
        "conclusion": (
            "public_private_boundary_ready_for_substrate_regression_gates"
            if status == "PASS"
            else "public_private_boundary_needs_review"
        ),
    }
    write_outputs(out_dir=out_dir, findings=all_findings, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, findings: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "boundary_findings.jsonl").open("w", encoding="utf-8") as fh:
        for row in findings:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
