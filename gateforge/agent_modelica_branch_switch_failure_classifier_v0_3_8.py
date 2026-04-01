from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_branch_switch_failure_classifier_v0_3_8"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_branch_switch_failure_classifier_v0_3_8"
PRIMARY_BUCKETS = (
    "success_after_branch_switch",
    "success_without_branch_switch_evidence",
    "wrong_branch_after_restore",
    "stalled_search_after_progress",
    "no_meaningful_progress",
    "infra_interruption",
)
BUCKET_SCHEMA_VERSION = "v0_3_8_branch_switch_primary_buckets_v1"
INFRA_HINTS = (
    "not logged in",
    "/login",
    "quota",
    "limit",
    "rate limit",
    "network",
    "transport",
    "mcp",
    "url_error",
    "connection reset",
    "timeout",
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


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
    return _norm(row.get("task_id") or row.get("mutation_id") or row.get("item_id"))


def _is_infra(row: dict) -> bool:
    text = " | ".join(
        part
        for part in (
            _norm(row.get("error_message")),
            _norm(row.get("infra_failure_reason")),
        )
        if part
    ).lower()
    return any(hint in text for hint in INFRA_HINTS)


def classify_branch_switch_row(row: dict) -> dict:
    success = _norm(row.get("verdict")).upper() == "PASS" or _norm(row.get("executor_status")).upper() == "PASS"
    success_after_switch = bool(row.get("success_after_branch_switch"))
    wrong_branch_entered = row.get("wrong_branch_entered") is True
    stalled = row.get("stall_event_observed") is True
    if _is_infra(row):
        return {"primary_bucket": "infra_interruption", "bucket_reasons": ["infra_hint_text"]}
    if success_after_switch:
        return {"primary_bucket": "success_after_branch_switch", "bucket_reasons": ["success_after_branch_switch_true"]}
    if success:
        return {"primary_bucket": "success_without_branch_switch_evidence", "bucket_reasons": ["success_without_branch_switch_evidence_true"]}
    if wrong_branch_entered:
        return {"primary_bucket": "wrong_branch_after_restore", "bucket_reasons": ["wrong_branch_entered_true"]}
    if stalled:
        return {"primary_bucket": "stalled_search_after_progress", "bucket_reasons": ["stall_event_observed_true"]}
    return {"primary_bucket": "no_meaningful_progress", "bucket_reasons": ["no_branch_switch_signal_detected"]}


def build_branch_switch_failure_classifier(
    *,
    refreshed_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    payload = _load_json(refreshed_summary_path)
    rows = _rows(payload)
    classified_rows = []
    counts = {bucket: 0 for bucket in PRIMARY_BUCKETS}
    total = len(rows)
    for row in rows:
        classification = classify_branch_switch_row(row)
        bucket = _norm(classification.get("primary_bucket"))
        counts[bucket] = int(counts.get(bucket) or 0) + 1
        classified_rows.append(
            {
                **row,
                "item_id": _item_id(row),
                "branch_switch_primary_bucket": bucket,
                "branch_switch_bucket_reasons": list(classification.get("bucket_reasons") or []),
            }
        )
    payload_out = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if total > 0 else "EMPTY",
        "bucket_schema_version": BUCKET_SCHEMA_VERSION,
        "refreshed_summary_path": str(Path(refreshed_summary_path).resolve()) if Path(refreshed_summary_path).exists() else str(refreshed_summary_path),
        "frozen_mainline_task_ids": list(payload.get("frozen_mainline_task_ids") or []),
        "metrics": {
            "total_rows": total,
            "failure_bucket_counts": counts,
            "success_after_branch_switch_count": int(counts.get("success_after_branch_switch") or 0),
            "success_without_branch_switch_evidence_count": int(counts.get("success_without_branch_switch_evidence") or 0),
            "wrong_branch_after_restore_count": int(counts.get("wrong_branch_after_restore") or 0),
            "stalled_search_after_progress_count": int(counts.get("stalled_search_after_progress") or 0),
        },
        "rows": classified_rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload_out)
    _write_text(out_root / "summary.md", render_markdown(payload_out))
    return payload_out


def render_markdown(payload: dict) -> str:
    counts = (payload.get("metrics") or {}).get("failure_bucket_counts") or {}
    lines = [
        "# Branch-Switch Failure Classifier v0.3.8",
        "",
        f"- status: `{payload.get('status')}`",
        f"- bucket_schema_version: `{payload.get('bucket_schema_version')}`",
        "",
    ]
    for bucket in PRIMARY_BUCKETS:
        lines.append(f"- `{bucket}`: {counts.get(bucket, 0)}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify v0.3.8 branch-switch outcomes from refreshed lane evidence.")
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_branch_switch_failure_classifier(
        refreshed_summary_path=str(args.refreshed_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "total_rows": (payload.get("metrics") or {}).get("total_rows")}))


if __name__ == "__main__":
    main()
