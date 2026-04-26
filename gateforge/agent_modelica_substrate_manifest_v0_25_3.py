from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from gateforge.agent_modelica_substrate_seed_import_v0_25_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPLIT_PATH = REPO_ROOT / "artifacts" / "substrate_split_v0_25_2" / "substrate_split.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "substrate_manifest_v0_25_3"
SUBSTRATE_MANIFEST_VERSION = "benchmark_substrate_manifest_v1"


def stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def public_status_for_split(split: str) -> str:
    if split == "smoke":
        return "public_fixture"
    return "private_substrate_reference"


def build_manifest_rows(split_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in sorted(split_rows, key=lambda item: (str(item.get("split") or ""), str(item.get("seed_id") or ""))):
        split = str(row.get("split") or "unknown")
        manifest_row = {
            "manifest_version": SUBSTRATE_MANIFEST_VERSION,
            "seed_id": str(row.get("seed_id") or ""),
            "candidate_id": str(row.get("candidate_id") or row.get("seed_id") or ""),
            "mutation_family": str(row.get("mutation_family") or "unknown"),
            "split": split,
            "repeatability_class": str(row.get("repeatability_class") or "unknown"),
            "import_status": str(row.get("import_status") or "unknown"),
            "public_status": public_status_for_split(split),
            "artifact_references": list(row.get("artifact_references") or []),
            "routing_allowed": False,
        }
        manifest_row["artifact_hash"] = stable_hash(manifest_row)
        rows.append(manifest_row)
    return rows


def validate_manifest_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        row_errors: list[str] = []
        seed_id = str(row.get("seed_id") or "")
        if not seed_id:
            row_errors.append("missing_seed_id")
        if seed_id in seen:
            row_errors.append("duplicate_seed_id")
        seen.add(seed_id)
        if bool(row.get("routing_allowed")):
            row_errors.append("routing_must_be_false")
        if not row.get("artifact_hash"):
            row_errors.append("missing_artifact_hash")
        if not row.get("artifact_references"):
            row_errors.append("missing_artifact_references")
        if row_errors:
            errors.append({"seed_id": seed_id, "errors": row_errors})
    return errors


def build_substrate_manifest(
    *,
    split_path: Path = DEFAULT_SPLIT_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    split_rows = load_jsonl(split_path)
    manifest_rows = build_manifest_rows(split_rows)
    validation_errors = validate_manifest_rows(manifest_rows)
    split_counts = Counter(row["split"] for row in manifest_rows)
    status = "PASS" if manifest_rows and not validation_errors else "REVIEW"
    manifest = {
        "manifest_version": SUBSTRATE_MANIFEST_VERSION,
        "version": "v0.25.3",
        "seed_count": len(manifest_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "source_split_artifact": str(split_path.relative_to(REPO_ROOT)) if split_path.is_relative_to(REPO_ROOT) else str(split_path),
        "runner_policy": "runners_must_read_seed_ids_from_this_manifest",
        "routing_allowed": False,
    }
    summary = {
        "version": "v0.25.3",
        "status": status,
        "analysis_scope": "substrate_manifest_freeze",
        "manifest_version": SUBSTRATE_MANIFEST_VERSION,
        "seed_count": len(manifest_rows),
        "split_counts": dict(sorted(split_counts.items())),
        "validation_error_count": len(validation_errors),
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "runner_seed_source": "substrate_manifest_only",
            "routing_allowed": False,
        },
        "conclusion": (
            "substrate_manifest_ready_for_public_private_boundary_audit"
            if status == "PASS"
            else "substrate_manifest_needs_review"
        ),
    }
    write_outputs(out_dir=out_dir, manifest=manifest, manifest_rows=manifest_rows, validation_errors=validation_errors, summary=summary)
    return summary


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def write_outputs(
    *,
    out_dir: Path,
    manifest: dict[str, Any],
    manifest_rows: list[dict[str, Any]],
    validation_errors: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_jsonl(out_dir / "manifest_rows.jsonl", manifest_rows)
    _write_jsonl(out_dir / "validation_errors.jsonl", validation_errors)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
