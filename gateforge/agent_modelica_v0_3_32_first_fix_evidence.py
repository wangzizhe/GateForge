from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_32_common import (
    DEFAULT_ENTRY_SPEC_OUT_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    SCHEMA_PREFIX,
    apply_repair_step,
    fixture_pipe_target_result,
    norm,
    now_utc,
    pipe_slice_target_hit,
    probe_resolved_result,
    probe_target_result,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_32_entry_spec import build_v0332_entry_spec


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_first_fix_evidence"


def build_v0332_first_fix_evidence(
    *,
    entry_taskset_path: str = str(DEFAULT_ENTRY_SPEC_OUT_DIR / "taskset.json"),
    out_dir: str = str(DEFAULT_FIRST_FIX_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    if not Path(entry_taskset_path).exists():
        build_v0332_entry_spec(out_dir=str(Path(entry_taskset_path).parent), use_fixture_only=use_fixture_only)
    taskset = json.loads(Path(entry_taskset_path).read_text(encoding="utf-8"))
    summary_row = taskset.get("summary") or {}
    if norm(summary_row.get("status")) != "PASS":
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "SKIPPED",
            "execution_status": "not_executed_due_to_entry_gate",
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", summary)
        write_text(out_root / "summary.md", "# v0.3.32 First-Fix Evidence\n\n- status: `SKIPPED`\n")
        return summary

    tasks = [row for row in (taskset.get("single_tasks") or []) if isinstance(row, dict)]
    rows: list[dict] = []
    reason_counts: dict[str, int] = {}
    admitted_tasks: list[dict] = []
    for task in tasks:
        step = ((task.get("repair_steps") or [])[0] if isinstance(task.get("repair_steps"), list) else {}) or {}
        initial = probe_target_result(
            model_name=norm(task.get("model_name")),
            model_text=norm(task.get("mutated_model_text")),
            wrong_symbol=norm(task.get("wrong_symbol")),
            use_fixture_only=use_fixture_only,
        )
        patched_text, patch_meta = apply_repair_step(norm(task.get("mutated_model_text")), step)
        post = probe_resolved_result(
            model_name=norm(task.get("model_name")),
            model_text=patched_text,
            use_fixture_only=use_fixture_only,
        ) if bool(patch_meta.get("applied")) else fixture_pipe_target_result(phase="target_hit", wrong_symbol=norm(task.get("wrong_symbol")))
        target_first_failure_hit = pipe_slice_target_hit(initial)
        patch_applied = bool(patch_meta.get("applied"))
        signature_advance = bool(post.get("check_model_pass") or (norm(initial.get("error_signature")) != norm(post.get("error_signature"))))
        drift = bool(not post.get("check_model_pass") and norm(post.get("error_subtype")) == "compile_failure_unknown" and not pipe_slice_target_hit(post))
        if not signature_advance:
            reason = "patch_missed_focal_token" if patch_applied else "no_patch_applied"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        row = {
            "task_id": norm(task.get("task_id")),
            "target_first_failure_hit": target_first_failure_hit,
            "patch_applied": patch_applied,
            "signature_advance": signature_advance,
            "drift_to_compile_failure_unknown": drift,
            "component_subtype": norm(task.get("component_subtype")),
        }
        rows.append(row)
        if target_first_failure_hit and patch_applied and signature_advance and not drift:
            admitted_tasks.append(dict(task))
    task_count = len(rows)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "execution_status": "executed",
        "task_count": task_count,
        "target_first_failure_hit_rate_pct": round(100.0 * sum(1 for row in rows if row.get("target_first_failure_hit")) / float(task_count), 1) if task_count else 0.0,
        "patch_applied_rate_pct": round(100.0 * sum(1 for row in rows if row.get("patch_applied")) / float(task_count), 1) if task_count else 0.0,
        "signature_advance_rate_pct": round(100.0 * sum(1 for row in rows if row.get("signature_advance")) / float(task_count), 1) if task_count else 0.0,
        "drift_to_compile_failure_unknown_rate_pct": round(100.0 * sum(1 for row in rows if row.get("drift_to_compile_failure_unknown")) / float(task_count), 1) if task_count else 0.0,
        "signature_advance_not_fired_reason_counts": reason_counts,
        "admitted_task_count": len(admitted_tasks),
        "rows": rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(
        out_root / "admitted_taskset.json",
        {
            "summary": summary,
            "task_count": len(admitted_tasks),
            "task_ids": [norm(task.get("task_id")) for task in admitted_tasks],
            "tasks": admitted_tasks,
        },
    )
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.32 First-Fix Evidence",
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
    parser = argparse.ArgumentParser(description="Build the v0.3.32 pipe-slice first-fix evidence.")
    parser.add_argument("--entry-taskset", default=str(DEFAULT_ENTRY_SPEC_OUT_DIR / "taskset.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_FIRST_FIX_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0332_first_fix_evidence(
        entry_taskset_path=str(args.entry_taskset),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.use_fixture_only),
    )
    print(json.dumps({"status": payload.get("status"), "execution_status": payload.get("execution_status"), "signature_advance_rate_pct": payload.get("signature_advance_rate_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
