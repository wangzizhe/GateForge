from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_same_branch_continuity_failure_classifier_v0_3_10"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_same_branch_continuity_failure_classifier_v0_3_10"
PRIMARY_BUCKETS = (
    "true_same_branch_multi_step_success",
    "same_branch_one_shot_or_accidental_success",
    "hidden_branch_change_misclassified_as_continuity",
    "stalled_unresolved_same_branch_failure",
)
BUCKET_SCHEMA_VERSION = "v0_3_10_same_branch_continuity_primary_buckets_v1"


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
    return str(row.get("task_id") or row.get("item_id") or "").strip()


def classify_continuity_row(row: dict) -> dict:
    success = str(row.get("verdict") or row.get("executor_status") or "").upper() == "PASS"
    branch_identity_continuous = row.get("branch_identity_continuous") is True
    branch_switch_event = row.get("branch_switch_event_observed") is True
    refinement_count = int(row.get("same_branch_refinement_event_count") or 0)
    if success and branch_identity_continuous and not branch_switch_event and refinement_count >= 2:
        return {
            "primary_bucket": "true_same_branch_multi_step_success",
            "bucket_reason": "same_branch_multi_step_evidence_present",
        }
    if success and branch_identity_continuous and not branch_switch_event:
        return {
            "primary_bucket": "same_branch_one_shot_or_accidental_success",
            "bucket_reason": "same_branch_success_without_enough_refinement_events",
        }
    if success and (branch_switch_event or not branch_identity_continuous):
        return {
            "primary_bucket": "hidden_branch_change_misclassified_as_continuity",
            "bucket_reason": "branch_identity_not_continuous_or_switch_observed",
        }
    return {
        "primary_bucket": "stalled_unresolved_same_branch_failure",
        "bucket_reason": "same_branch_continuity_not_resolved",
    }


def build_same_branch_continuity_failure_classifier(
    *,
    refreshed_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    refreshed = _load_json(refreshed_summary_path)
    rows = _rows(refreshed)
    counts = {bucket: 0 for bucket in PRIMARY_BUCKETS}
    classified_rows = []
    for row in rows:
        classification = classify_continuity_row(row)
        bucket = str(classification["primary_bucket"])
        counts[bucket] = int(counts.get(bucket) or 0) + 1
        classified_rows.append(
            {
                **row,
                "item_id": _item_id(row),
                "same_branch_continuity_primary_bucket": bucket,
                "same_branch_continuity_bucket_reason": classification["bucket_reason"],
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if classified_rows else "EMPTY",
        "bucket_schema_version": BUCKET_SCHEMA_VERSION,
        "refreshed_summary_path": str(Path(refreshed_summary_path).resolve()) if Path(refreshed_summary_path).exists() else str(refreshed_summary_path),
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
                "# v0.3.10 Same-Branch Continuity Classifier",
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
    parser = argparse.ArgumentParser(description="Classify the refreshed v0.3.10 same-branch continuity lane.")
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_same_branch_continuity_failure_classifier(
        refreshed_summary_path=str(args.refreshed_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "total_rows": (payload.get("metrics") or {}).get("total_rows")}))


if __name__ == "__main__":
    main()
