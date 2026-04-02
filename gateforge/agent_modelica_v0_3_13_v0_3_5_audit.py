from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_13_v0_3_5_audit"
DEFAULT_CANDIDATE_DIR = "artifacts/agent_modelica_block_a_dual_layer_candidates_v0_3_5"
DEFAULT_RESULTS_DIR = "artifacts/agent_modelica_block_a_gf_results_v0_3_5"
DEFAULT_PREVIEW_SUMMARY = "artifacts/agent_modelica_v0_3_13_trajectory_preview_v0_3_5_current/summary.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_v0_3_5_audit"
EARLY_STAGE_PREFIXES = ("stage_1_", "stage_2_", "stage_3_")
LATE_STAGE_PREFIXES = ("stage_4_", "stage_5_")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _load_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _load_dir_rows(path: str | Path) -> dict[str, dict]:
    target = Path(path)
    rows: dict[str, dict] = {}
    if not target.is_dir():
        return rows
    for child in sorted(target.glob("*.json")):
        if child.name == "lane_summary.json" or child.name == "run_summary.json":
            continue
        payload = _load_json(child)
        task_id = _norm(payload.get("task_id") or payload.get("item_id") or child.stem)
        if task_id:
            rows[task_id] = payload
    return rows


def _load_preview_rows(path: str | Path) -> dict[str, dict]:
    payload = _load_json(path)
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return {}
    mapping: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        task_id = _norm(row.get("task_id"))
        if task_id:
            mapping[task_id] = row
    return mapping


def _attempt_diagnostic(attempt: dict) -> dict:
    diagnostic = attempt.get("diagnostic_ir")
    if isinstance(diagnostic, dict):
        return diagnostic
    return {
        "error_type": _norm(attempt.get("observed_failure_type")),
        "stage_subtype": _norm(attempt.get("stage_subtype")),
        "reason": _norm(attempt.get("reason")),
    }


def classify_masking_pattern(result_row: dict) -> str:
    attempts = result_row.get("attempts")
    if not isinstance(attempts, list) or len(attempts) < 2:
        return "insufficient_attempt_history"
    first = _attempt_diagnostic(attempts[0])
    second = _attempt_diagnostic(attempts[1])
    first_stage = _norm(first.get("stage_subtype") or first.get("dominant_stage_subtype")).lower()
    second_stage = _norm(second.get("stage_subtype") or second.get("dominant_stage_subtype")).lower()
    if first_stage.startswith(EARLY_STAGE_PREFIXES) and second_stage.startswith(LATE_STAGE_PREFIXES):
        return "surface_masks_residual"
    if first_stage.startswith(LATE_STAGE_PREFIXES) and second_stage.startswith(LATE_STAGE_PREFIXES):
        if first_stage == second_stage:
            return "residual_visible_before_surface_cleanup"
        return "residual_shift_after_surface_cleanup"
    if first_stage.startswith(EARLY_STAGE_PREFIXES) and second_stage.startswith(EARLY_STAGE_PREFIXES):
        return "surface_fix_did_not_unlock_late_residual"
    return "mixed_transition"


def classify_success_pattern(result_row: dict) -> str:
    success = bool(result_row.get("executor_status") == "PASS" or result_row.get("success"))
    rounds_used = int(result_row.get("rounds_used") or 0)
    resolution_path = _norm(result_row.get("resolution_path")).lower()
    if success and resolution_path == "rule_then_llm" and rounds_used >= 3:
        return "rule_then_llm_multiround_success"
    if success and rounds_used <= 1:
        return "single_round_success"
    if success:
        return "other_success"
    return "not_success"


def build_audit_row(*, candidate_row: dict, result_row: dict, preview_row: dict) -> dict:
    attempts = result_row.get("attempts")
    first = _attempt_diagnostic(attempts[0]) if isinstance(attempts, list) and attempts else {}
    second = _attempt_diagnostic(attempts[1]) if isinstance(attempts, list) and len(attempts) > 1 else {}
    return {
        "task_id": _norm(candidate_row.get("task_id") or result_row.get("task_id")),
        "hidden_base_operator": _norm(candidate_row.get("hidden_base_operator")),
        "surface_rule_id": _norm(preview_row.get("surface_rule_id")),
        "surface_rule_reason": _norm(preview_row.get("surface_rule_reason")),
        "masking_pattern": classify_masking_pattern(result_row),
        "success_pattern": classify_success_pattern(result_row),
        "preview_admission": bool(preview_row.get("preview_admission")),
        "residual_signal_cluster_id": _norm(preview_row.get("residual_signal_cluster_id")),
        "first_attempt_stage_subtype": _norm(first.get("stage_subtype") or first.get("dominant_stage_subtype")),
        "second_attempt_stage_subtype": _norm(second.get("stage_subtype") or second.get("dominant_stage_subtype")),
        "first_attempt_error_type": _norm(first.get("error_type")),
        "second_attempt_error_type": _norm(second.get("error_type")),
        "rounds_used": int(result_row.get("rounds_used") or 0),
        "resolution_path": _norm(result_row.get("resolution_path")),
        "llm_plan_candidate_parameters": list(result_row.get("llm_plan_candidate_parameters") or []),
        "gf_success": bool(result_row.get("executor_status") == "PASS" or result_row.get("success")),
    }


def _count_by_key(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = _norm(row.get(key))
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def _build_summary(*, audit_rows: list[dict], candidate_dir: str, results_dir: str, preview_summary_path: str) -> dict:
    recommended_seed_task_ids = [
        row["task_id"]
        for row in audit_rows
        if bool(row.get("preview_admission"))
        and row.get("success_pattern") == "rule_then_llm_multiround_success"
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if audit_rows else "EMPTY",
        "candidate_dir": str(Path(candidate_dir).resolve()) if Path(candidate_dir).exists() else str(candidate_dir),
        "results_dir": str(Path(results_dir).resolve()) if Path(results_dir).exists() else str(results_dir),
        "preview_summary_path": str(Path(preview_summary_path).resolve()) if Path(preview_summary_path).exists() else str(preview_summary_path),
        "metrics": {
            "total_rows": len(audit_rows),
            "preview_admitted_count": sum(1 for row in audit_rows if bool(row.get("preview_admission"))),
            "successful_rule_then_llm_multiround_count": sum(
                1 for row in audit_rows if row.get("success_pattern") == "rule_then_llm_multiround_success"
            ),
            "hidden_base_operator_counts": _count_by_key(audit_rows, "hidden_base_operator"),
            "masking_pattern_counts": _count_by_key(audit_rows, "masking_pattern"),
            "residual_signal_cluster_counts": _count_by_key(audit_rows, "residual_signal_cluster_id"),
        },
        "recommended_seed_task_ids": recommended_seed_task_ids,
        "rows": audit_rows,
    }


def render_markdown(payload: dict) -> str:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    lines = [
        "# v0.3.5 Audit For v0.3.13",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_rows: `{metrics.get('total_rows')}`",
        f"- preview_admitted_count: `{metrics.get('preview_admitted_count')}`",
        f"- successful_rule_then_llm_multiround_count: `{metrics.get('successful_rule_then_llm_multiround_count')}`",
        "",
        "## Recommended Seed Task IDs",
        "",
    ]
    for task_id in payload.get("recommended_seed_task_ids") or []:
        lines.append(f"- `{task_id}`")
    lines.append("")
    return "\n".join(lines)


def build_v0_3_5_audit(
    *,
    candidate_dir: str = DEFAULT_CANDIDATE_DIR,
    results_dir: str = DEFAULT_RESULTS_DIR,
    preview_summary_path: str = DEFAULT_PREVIEW_SUMMARY,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    candidates = _load_dir_rows(candidate_dir)
    results = _load_dir_rows(results_dir)
    preview_rows = _load_preview_rows(preview_summary_path)
    task_ids = sorted(set(candidates) & set(results))
    audit_rows = [
        build_audit_row(
            candidate_row=candidates[task_id],
            result_row=results[task_id],
            preview_row=preview_rows.get(task_id, {}),
        )
        for task_id in task_ids
    ]
    payload = _build_summary(
        audit_rows=audit_rows,
        candidate_dir=candidate_dir,
        results_dir=results_dir,
        preview_summary_path=preview_summary_path,
    )
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the v0.3.5 seed lane for v0.3.13.")
    parser.add_argument("--candidate-dir", default=DEFAULT_CANDIDATE_DIR)
    parser.add_argument("--results-dir", default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--preview-summary", default=DEFAULT_PREVIEW_SUMMARY)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_5_audit(
        candidate_dir=str(args.candidate_dir),
        results_dir=str(args.results_dir),
        preview_summary_path=str(args.preview_summary),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "recommended_seed_task_ids": payload.get("recommended_seed_task_ids"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
