from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_post_restore_failure_classifier_v0_3_6"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_post_restore_failure_classifier_v0_3_6"
FAILURE_BUCKETS = (
    "success_beyond_single_sweep",
    "success_with_single_sweep_only",
    "residual_semantic_conflict_after_restore",
    "verifier_reject_after_restore",
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
            _norm(row.get("output_text")),
            _norm(row.get("infra_failure_reason")),
        )
        if part
    ).lower()
    return any(hint in text for hint in INFRA_HINTS)


def classify_post_restore_row(row: dict) -> dict:
    success = _is_success(row)
    single_sweep_outcome = _norm(row.get("single_sweep_outcome"))
    first_correction_success = bool(row.get("first_correction_success"))
    residual_after_first = bool(row.get("residual_failure_after_first_correction"))
    planner_invoked = bool(row.get("planner_invoked"))
    check_model_pass = row.get("check_model_pass")
    simulate_pass = row.get("simulate_pass")
    wrong_branch_entered = bool(row.get("wrong_branch_entered"))
    correct_branch_selected = bool(row.get("correct_branch_selected"))

    if _is_infra(row):
        return {
            "failure_bucket": "infra_interruption",
            "bucket_reasons": ["infra_hint_text"],
            "progress_detected": False,
        }
    if success and (single_sweep_outcome == "residual_failure_after_first_correction" or residual_after_first):
        return {
            "failure_bucket": "success_beyond_single_sweep",
            "bucket_reasons": ["row_marked_success", "residual_after_first_correction"],
            "progress_detected": True,
        }
    if success:
        return {
            "failure_bucket": "success_with_single_sweep_only",
            "bucket_reasons": ["row_marked_success", "single_sweep_resolved_or_not_observed"],
            "progress_detected": bool(planner_invoked or first_correction_success),
        }
    if wrong_branch_entered and not correct_branch_selected:
        return {
            "failure_bucket": "wrong_branch_after_restore",
            "bucket_reasons": ["wrong_branch_entered_true"],
            "progress_detected": True,
        }
    if first_correction_success and check_model_pass is False:
        return {
            "failure_bucket": "residual_semantic_conflict_after_restore",
            "bucket_reasons": ["first_correction_success_true", "check_model_pass_false"],
            "progress_detected": True,
        }
    if first_correction_success and check_model_pass is True and simulate_pass is False:
        return {
            "failure_bucket": "verifier_reject_after_restore",
            "bucket_reasons": ["first_correction_success_true", "check_model_pass_true", "simulate_pass_false"],
            "progress_detected": True,
        }
    if planner_invoked or first_correction_success:
        return {
            "failure_bucket": "stalled_search_after_progress",
            "bucket_reasons": ["planner_or_first_correction_progress_detected"],
            "progress_detected": True,
        }
    return {
        "failure_bucket": "no_meaningful_progress",
        "bucket_reasons": ["no_progress_detected"],
        "progress_detected": False,
    }


def build_post_restore_failure_classifier(
    *,
    refreshed_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    payload = _load_json(refreshed_summary_path)
    rows = _rows(payload)
    classified_rows: list[dict] = []
    failure_counts = {bucket: 0 for bucket in FAILURE_BUCKETS}
    progress_count = 0
    beyond_single_sweep_count = 0

    for row in rows:
        classification = classify_post_restore_row(row)
        bucket = _norm(classification.get("failure_bucket"))
        progress_detected = bool(classification.get("progress_detected"))
        if progress_detected:
            progress_count += 1
        if bucket == "success_beyond_single_sweep":
            beyond_single_sweep_count += 1
        failure_counts[bucket] = int(failure_counts.get(bucket) or 0) + 1
        classified_rows.append(
            {
                **row,
                "item_id": _item_id(row),
                "post_restore_failure_bucket": bucket,
                "post_restore_bucket_reasons": list(classification.get("bucket_reasons") or []),
                "post_restore_progress_detected": progress_detected,
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
            "post_restore_progress_count": progress_count,
            "post_restore_progress_rate_pct": round(100.0 * progress_count / total, 1) if total else 0.0,
            "success_beyond_single_sweep_count": beyond_single_sweep_count,
            "success_beyond_single_sweep_rate_pct": round(100.0 * beyond_single_sweep_count / total, 1) if total else 0.0,
            "failure_bucket_counts": failure_counts,
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
        "# Post-Restore Failure Classifier v0.3.6",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_rows: `{metrics.get('total_rows')}`",
        f"- post_restore_progress_rate_pct: `{metrics.get('post_restore_progress_rate_pct')}`",
        f"- success_beyond_single_sweep_rate_pct: `{metrics.get('success_beyond_single_sweep_rate_pct')}`",
        "",
        "## Bucket Counts",
        "",
    ]
    for bucket in FAILURE_BUCKETS:
        lines.append(f"- `{bucket}`: {counts.get(bucket, 0)}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify v0.3.6 post-restore outcomes from refreshed lane evidence.")
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_post_restore_failure_classifier(
        refreshed_summary_path=str(args.refreshed_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "total_rows": (payload.get("metrics") or {}).get("total_rows")}))


if __name__ == "__main__":
    main()
