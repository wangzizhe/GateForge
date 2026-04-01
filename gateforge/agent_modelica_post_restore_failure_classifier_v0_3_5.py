from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_post_restore_failure_classifier_v0_3_5"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_post_restore_failure_classifier_v0_3_5"
FAILURE_BUCKETS = (
    "success_after_restore",
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


def _load_input_rows(path: str | Path) -> list[dict]:
    p = Path(path)
    if p.is_dir():
        rows: list[dict] = []
        for child in sorted(p.glob("*.json")):
            if child.name == "run_summary.json":
                continue
            payload = _load_json(child)
            if payload:
                rows.append(payload)
        return rows
    payload = _load_json(p)
    return _rows(payload)


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _rows(payload: dict) -> list[dict]:
    for key in ("results", "records", "tasks", "cases"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _item_id(row: dict) -> str:
    return _norm(row.get("task_id") or row.get("mutation_id") or row.get("item_id"))


def _attempt_rows(row: dict) -> list[dict]:
    attempts = row.get("attempts")
    return [a for a in attempts if isinstance(a, dict)] if isinstance(attempts, list) else []


def _has_progress(row: dict) -> bool:
    for attempt in _attempt_rows(row):
        source_repair = attempt.get("source_repair")
        if isinstance(source_repair, dict) and bool(source_repair.get("applied")):
            return True
        sim_recovery = attempt.get("simulate_error_parameter_recovery")
        if isinstance(sim_recovery, dict) and bool(sim_recovery.get("applied")):
            return True
    if _norm(row.get("resolution_path")) in {"rule_then_llm", "llm_planner_assisted"}:
        return True
    return False


def _is_success(row: dict) -> bool:
    return bool(row.get("success")) or _norm(row.get("executor_status")).upper() == "PASS"


def _is_infra(row: dict) -> bool:
    text = " | ".join(
        part for part in (
            _norm(row.get("error_message")),
            _norm(row.get("output_text")),
            _norm(row.get("infra_failure_reason")),
        )
        if part
    ).lower()
    return any(hint in text for hint in INFRA_HINTS)


def classify_post_restore_row(row: dict) -> dict:
    progress = _has_progress(row)
    success = _is_success(row)
    check_model_pass = row.get("check_model_pass")
    simulate_pass = row.get("simulate_pass")
    wrong_branch_entered = bool(row.get("wrong_branch_entered"))
    correct_branch_selected = bool(row.get("correct_branch_selected"))

    if _is_infra(row):
        return {
            "failure_bucket": "infra_interruption",
            "bucket_reasons": ["infra_hint_text"],
            "progress_detected": progress,
        }
    if success and progress:
        return {
            "failure_bucket": "success_after_restore",
            "bucket_reasons": ["post_restore_progress_detected", "row_marked_success"],
            "progress_detected": True,
        }
    if progress and wrong_branch_entered and not correct_branch_selected:
        return {
            "failure_bucket": "wrong_branch_after_restore",
            "bucket_reasons": ["post_restore_progress_detected", "wrong_branch_entered_true"],
            "progress_detected": True,
        }
    if progress and check_model_pass is False:
        return {
            "failure_bucket": "residual_semantic_conflict_after_restore",
            "bucket_reasons": ["post_restore_progress_detected", "check_model_pass_false"],
            "progress_detected": True,
        }
    if progress and check_model_pass is True and simulate_pass is False:
        return {
            "failure_bucket": "verifier_reject_after_restore",
            "bucket_reasons": ["post_restore_progress_detected", "check_model_pass_true", "simulate_pass_false"],
            "progress_detected": True,
        }
    if progress:
        return {
            "failure_bucket": "stalled_search_after_progress",
            "bucket_reasons": ["post_restore_progress_detected", "default_post_restore_stall"],
            "progress_detected": True,
        }
    return {
        "failure_bucket": "no_meaningful_progress",
        "bucket_reasons": ["no_post_restore_progress_detected"],
        "progress_detected": False,
    }


def build_post_restore_failure_classifier(
    *,
    input_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    rows = _load_input_rows(input_path)
    classified_rows: list[dict] = []
    failure_counts = {bucket: 0 for bucket in FAILURE_BUCKETS}
    progress_count = 0

    for row in rows:
        item_id = _item_id(row)
        classification = classify_post_restore_row(row)
        bucket = _norm(classification.get("failure_bucket"))
        progress = bool(classification.get("progress_detected"))
        if progress:
            progress_count += 1
        failure_counts[bucket] = int(failure_counts.get(bucket) or 0) + 1
        classified_rows.append(
            {
                **row,
                "item_id": item_id,
                "post_restore_failure_bucket": bucket,
                "post_restore_bucket_reasons": list(classification.get("bucket_reasons") or []),
                "post_restore_progress_detected": progress,
            }
        )

    total = len(rows)
    payload_out = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if total > 0 else "EMPTY",
        "input_path": str(Path(input_path).resolve()) if Path(input_path).exists() else str(input_path),
        "metrics": {
            "total_rows": total,
            "post_restore_progress_count": progress_count,
            "post_restore_progress_rate_pct": round(100.0 * progress_count / total, 1) if total else 0.0,
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
        "# Post-Restore Failure Classifier v0.3.5",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_rows: `{metrics.get('total_rows')}`",
        f"- post_restore_progress_rate_pct: `{metrics.get('post_restore_progress_rate_pct')}`",
        "",
        "## Bucket Counts",
        "",
    ]
    for bucket in FAILURE_BUCKETS:
        lines.append(f"- `{bucket}`: {counts.get(bucket, 0)}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify post-restore outcomes for v0.3.5.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_post_restore_failure_classifier(
        input_path=str(args.input),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "total_rows": (payload.get("metrics") or {}).get("total_rows")}))


if __name__ == "__main__":
    main()
