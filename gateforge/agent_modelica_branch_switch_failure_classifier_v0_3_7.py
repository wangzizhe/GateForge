from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_branch_switch_failure_classifier_v0_3_7"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_branch_switch_failure_classifier_v0_3_7"
FAILURE_BUCKETS = (
    "success_after_branch_switch",
    "success_without_branch_switch_evidence",
    "wrong_branch_after_restore",
    "stalled_search_after_progress",
    "no_meaningful_progress",
    "infra_interruption",
)
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
SUCCESS_PATHS = {"deterministic_rule_only", "rule_then_llm", "llm_planner_assisted"}


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
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _item_id(row: dict) -> str:
    return _norm(row.get("task_id") or row.get("mutation_id") or row.get("item_id"))


def _is_success(row: dict) -> bool:
    if _norm(row.get("executor_status")).upper() == "PASS":
        return True
    if _norm(row.get("verdict")).upper() == "PASS":
        return True
    return _norm(row.get("resolution_path")) in SUCCESS_PATHS


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
    success = _is_success(row)
    wrong_branch = bool(row.get("wrong_branch_entered"))
    correct_branch = bool(row.get("correct_branch_selected"))
    planner_invoked = bool(row.get("planner_invoked"))
    rounds_used = int(row.get("rounds_used") or 0)

    if _is_infra(row):
        return {
            "failure_bucket": "infra_interruption",
            "bucket_reasons": ["infra_hint_text"],
            "progress_detected": False,
        }
    if success and correct_branch:
        return {
            "failure_bucket": "success_after_branch_switch",
            "bucket_reasons": ["row_marked_success", "correct_branch_selected_true"],
            "progress_detected": True,
        }
    if success:
        return {
            "failure_bucket": "success_without_branch_switch_evidence",
            "bucket_reasons": ["row_marked_success", "no_explicit_branch_switch_evidence"],
            "progress_detected": bool(planner_invoked or rounds_used > 1),
        }
    if wrong_branch and not correct_branch:
        return {
            "failure_bucket": "wrong_branch_after_restore",
            "bucket_reasons": ["wrong_branch_entered_true"],
            "progress_detected": True,
        }
    if planner_invoked or rounds_used > 1:
        return {
            "failure_bucket": "stalled_search_after_progress",
            "bucket_reasons": ["planner_or_multiround_progress_detected"],
            "progress_detected": True,
        }
    return {
        "failure_bucket": "no_meaningful_progress",
        "bucket_reasons": ["no_progress_detected"],
        "progress_detected": False,
    }


def build_branch_switch_failure_classifier(
    *,
    refreshed_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    payload = _load_json(refreshed_summary_path)
    rows = _rows(payload)
    classified_rows = []
    counts = {bucket: 0 for bucket in FAILURE_BUCKETS}
    progress_count = 0
    success_after_switch_count = 0

    for row in rows:
        classification = classify_branch_switch_row(row)
        bucket = _norm(classification.get("failure_bucket"))
        if bool(classification.get("progress_detected")):
            progress_count += 1
        if bucket == "success_after_branch_switch":
            success_after_switch_count += 1
        counts[bucket] = int(counts.get(bucket) or 0) + 1
        classified_rows.append(
            {
                **row,
                "item_id": _item_id(row),
                "branch_switch_failure_bucket": bucket,
                "branch_switch_bucket_reasons": list(classification.get("bucket_reasons") or []),
                "branch_switch_progress_detected": bool(classification.get("progress_detected")),
            }
        )

    total = len(rows)
    payload_out = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if total > 0 else "EMPTY",
        "refreshed_summary_path": str(Path(refreshed_summary_path).resolve()) if Path(refreshed_summary_path).exists() else str(refreshed_summary_path),
        "metrics": {
            "total_rows": total,
            "branch_switch_progress_count": progress_count,
            "branch_switch_progress_rate_pct": round(100.0 * progress_count / total, 1) if total else 0.0,
            "success_after_branch_switch_count": success_after_switch_count,
            "success_after_branch_switch_rate_pct": round(100.0 * success_after_switch_count / total, 1) if total else 0.0,
            "failure_bucket_counts": counts,
        },
        "rows": classified_rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload_out)
    _write_text(out_root / "summary.md", render_markdown(payload_out))
    return payload_out


def render_markdown(payload: dict) -> str:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    counts = metrics.get("failure_bucket_counts") if isinstance(metrics.get("failure_bucket_counts"), dict) else {}
    lines = [
        "# Branch-Switch Failure Classifier v0.3.7",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_rows: `{metrics.get('total_rows')}`",
        f"- branch_switch_progress_rate_pct: `{metrics.get('branch_switch_progress_rate_pct')}`",
        f"- success_after_branch_switch_rate_pct: `{metrics.get('success_after_branch_switch_rate_pct')}`",
        "",
        "## Bucket Counts",
        "",
    ]
    for bucket in FAILURE_BUCKETS:
        lines.append(f"- `{bucket}`: {counts.get(bucket, 0)}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify v0.3.7 branch-switch outcomes from refreshed lane evidence.")
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
