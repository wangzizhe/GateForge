from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_30_common import (
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_FIRST_FIX_RESULTS_DIR,
    DEFAULT_V0329_ENTRY_TASKSET_PATH,
    SCHEMA_PREFIX,
    apply_exact_repair_step,
    fixture_dry_run_result,
    load_json,
    medium_redeclare_target_hit,
    now_utc,
    norm,
    run_dry_run,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_first_fix_evidence"


def _single_rows(payload: dict) -> list[dict]:
    rows = payload.get("single_tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _run_or_fixture(*, model_name: str, model_text: str, phase: str, use_fixture_only: bool) -> dict:
    if use_fixture_only:
        return fixture_dry_run_result(phase=phase)
    return run_dry_run(model_name, model_text)


def build_v0330_first_fix_evidence(
    *,
    entry_taskset_path: str = str(DEFAULT_V0329_ENTRY_TASKSET_PATH),
    results_dir: str = str(DEFAULT_FIRST_FIX_RESULTS_DIR),
    out_dir: str = str(DEFAULT_FIRST_FIX_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    del results_dir
    taskset = load_json(entry_taskset_path)
    tasks = _single_rows(taskset)
    rows: list[dict] = []
    reason_counts: dict[str, int] = {}
    admitted_tasks: list[dict] = []
    for task in tasks:
        step = ((task.get("repair_steps") or [{}])[0] if isinstance(task.get("repair_steps"), list) else {}) or {}
        initial = _run_or_fixture(model_name=norm(task.get("model_name")), model_text=norm(task.get("mutated_model_text")), phase="target_hit", use_fixture_only=use_fixture_only)
        patched_text, patch_meta = apply_exact_repair_step(norm(task.get("mutated_model_text")), step)
        post = _run_or_fixture(model_name=norm(task.get("model_name")), model_text=patched_text, phase="resolved", use_fixture_only=use_fixture_only) if bool(patch_meta.get("applied")) else {}
        target_first_failure_hit = medium_redeclare_target_hit(initial)
        post_resolved = bool(post.get("check_model_pass"))
        focal_patch_hit = bool(patch_meta.get("applied"))
        signature_advance = bool(post_resolved or (norm(initial.get("error_signature")) != norm(post.get("error_signature"))))
        drift = bool(
            not post_resolved
            and norm(post.get("error_subtype")) == "compile_failure_unknown"
            and not medium_redeclare_target_hit(post)
        )
        if not signature_advance:
            reason = "patch_missed_focal_token" if patch_meta.get("applied") else "no_patch_applied"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        rows.append(
            {
                "task_id": norm(task.get("task_id")),
                "target_first_failure_hit": target_first_failure_hit,
                "patch_applied": bool(patch_meta.get("applied")),
                "focal_patch_hit": focal_patch_hit,
                "signature_advance": signature_advance,
                "post_resolved": post_resolved,
                "drift_to_compile_failure_unknown": drift,
                "initial": initial,
                "post": post,
            }
        )
        if target_first_failure_hit and bool(patch_meta.get("applied")) and focal_patch_hit and signature_advance and not drift:
            admitted_task = dict(task)
            admitted_task["v0_3_30_first_fix_row"] = rows[-1]
            admitted_tasks.append(admitted_task)
    task_count = len(rows)
    target_hits = sum(1 for row in rows if bool(row.get("target_first_failure_hit")))
    patch_hits = sum(1 for row in rows if bool(row.get("patch_applied")))
    focal_hits = sum(1 for row in rows if bool(row.get("focal_patch_hit")))
    advances = sum(1 for row in rows if bool(row.get("signature_advance")))
    drifts = sum(1 for row in rows if bool(row.get("drift_to_compile_failure_unknown")))
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "task_count": task_count,
        "target_first_failure_hit_rate_pct": round(100.0 * target_hits / float(task_count), 1) if task_count else 0.0,
        "patch_applied_rate_pct": round(100.0 * patch_hits / float(task_count), 1) if task_count else 0.0,
        "focal_patch_hit_rate_pct": round(100.0 * focal_hits / float(task_count), 1) if task_count else 0.0,
        "signature_advance_rate_pct": round(100.0 * advances / float(task_count), 1) if task_count else 0.0,
        "drift_to_compile_failure_unknown_rate_pct": round(100.0 * drifts / float(task_count), 1) if task_count else 0.0,
        "signature_advance_not_fired_reason_counts": reason_counts,
        "admitted_task_count": len(admitted_tasks),
        "rows": rows,
    }
    admitted_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if admitted_tasks else "EMPTY",
        "task_count": len(admitted_tasks),
        "task_ids": [norm(task.get("task_id")) for task in admitted_tasks],
        "tasks": admitted_tasks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "admitted_taskset.json", admitted_payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.30 First-Fix Evidence",
                "",
                f"- status: `{summary.get('status')}`",
                f"- target_first_failure_hit_rate_pct: `{summary.get('target_first_failure_hit_rate_pct')}`",
                f"- patch_applied_rate_pct: `{summary.get('patch_applied_rate_pct')}`",
                f"- signature_advance_rate_pct: `{summary.get('signature_advance_rate_pct')}`",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.30 first-fix evidence.")
    parser.add_argument("--entry-taskset", default=str(DEFAULT_V0329_ENTRY_TASKSET_PATH))
    parser.add_argument("--results-dir", default=str(DEFAULT_FIRST_FIX_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_FIRST_FIX_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0330_first_fix_evidence(
        entry_taskset_path=str(args.entry_taskset),
        results_dir=str(args.results_dir),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.use_fixture_only),
    )
    print(json.dumps({"status": payload.get("status"), "signature_advance_rate_pct": payload.get("signature_advance_rate_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
