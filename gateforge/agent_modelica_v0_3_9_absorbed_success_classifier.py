from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_9_absorbed_success_classifier"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_9_absorbed_success_classifier"
PRIMARY_BUCKETS = (
    "single_branch_resolution_without_true_stall",
    "noncontributing_branch_sequence",
    "explicit_switch_subfamily_misalignment",
)
BUCKET_SCHEMA_VERSION = "v0_3_9_absorbed_success_primary_buckets_v1"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _item_id(row: dict) -> str:
    return str(row.get("task_id") or row.get("source_mainline_task_id") or "").strip()


def classify_absorbed_success_row(row: dict) -> dict:
    sequence = row.get("detected_branch_sequence")
    sequence = [str(item).strip() for item in sequence if str(item).strip()] if isinstance(sequence, list) else []
    stall = row.get("stall_event_observed") is True
    candidate_branches = row.get("candidate_next_branches")
    candidate_branches = [item for item in candidate_branches if isinstance(item, dict)] if isinstance(candidate_branches, list) else []

    if len(sequence) <= 1 and not stall:
        return {
            "primary_bucket": "single_branch_resolution_without_true_stall",
            "bucket_reason": "single_material_branch_without_stall",
        }
    if len(sequence) >= 2 and row.get("success_after_branch_switch") is not True:
        return {
            "primary_bucket": "noncontributing_branch_sequence",
            "bucket_reason": "multiple_branches_seen_but_switch_not_contributing",
        }
    if len(candidate_branches) >= 2:
        return {
            "primary_bucket": "explicit_switch_subfamily_misalignment",
            "bucket_reason": "structurally_branchy_but_not_behaving_like_explicit_switch_success",
        }
    return {
        "primary_bucket": "single_branch_resolution_without_true_stall",
        "bucket_reason": "fallback_single_branch_like_behavior",
    }


def build_v0_3_9_absorbed_success_classifier(
    *,
    contrast_manifest_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    manifest = _load_json(contrast_manifest_path)
    rows = _rows(manifest)
    counts = {bucket: 0 for bucket in PRIMARY_BUCKETS}
    classified_rows = []
    for row in rows:
        classification = classify_absorbed_success_row(row)
        bucket = str(classification["primary_bucket"])
        counts[bucket] = int(counts.get(bucket) or 0) + 1
        classified_rows.append(
            {
                **row,
                "item_id": _item_id(row),
                "absorbed_success_primary_bucket": bucket,
                "absorbed_success_bucket_reason": classification["bucket_reason"],
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if classified_rows else "EMPTY",
        "bucket_schema_version": BUCKET_SCHEMA_VERSION,
        "contrast_manifest_path": str(Path(contrast_manifest_path).resolve()) if Path(contrast_manifest_path).exists() else str(contrast_manifest_path),
        "metrics": {
            "total_rows": len(classified_rows),
            "primary_bucket_counts": counts,
        },
        "rows": classified_rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.9 Absorbed-Success Classifier",
                "",
                f"- status: `{payload['status']}`",
                f"- bucket_schema_version: `{BUCKET_SCHEMA_VERSION}`",
                f"- total_rows: `{payload['metrics']['total_rows']}`",
                "",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify the frozen absorbed-success contrast manifest for v0.3.9.")
    parser.add_argument("--contrast-manifest", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_9_absorbed_success_classifier(
        contrast_manifest_path=str(args.contrast_manifest),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "total_rows": (payload.get("metrics") or {}).get("total_rows")}))


if __name__ == "__main__":
    main()
