from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_32_common import (
    DEFAULT_DISCOVERY_OUT_DIR,
    DEFAULT_ENTRY_SPEC_OUT_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    SCHEMA_PREFIX,
    apply_pipe_slice_discovery_patch,
    build_medium_candidate_rhs_symbols,
    fixture_pipe_target_result,
    norm,
    now_utc,
    parse_canonical_rhs_from_repair_step,
    rank_medium_rhs_candidates,
    probe_resolved_result,
    probe_target_result,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_32_first_fix_evidence import build_v0332_first_fix_evidence


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_discovery_probe"


def build_v0332_discovery_probe(
    *,
    first_fix_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    entry_taskset_path: str = str(DEFAULT_ENTRY_SPEC_OUT_DIR / "taskset.json"),
    out_dir: str = str(DEFAULT_DISCOVERY_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    if not Path(first_fix_path).exists():
        build_v0332_first_fix_evidence(out_dir=str(Path(first_fix_path).parent), use_fixture_only=use_fixture_only)
    first_fix = json.loads(Path(first_fix_path).read_text(encoding="utf-8"))
    if (
        norm(first_fix.get("execution_status")) != "executed"
        or float(first_fix.get("target_first_failure_hit_rate_pct") or 0.0) < 80.0
        or float(first_fix.get("patch_applied_rate_pct") or 0.0) < 70.0
        or float(first_fix.get("signature_advance_rate_pct") or 0.0) < 50.0
        or float(first_fix.get("drift_to_compile_failure_unknown_rate_pct") or 0.0) > 10.0
    ):
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "SKIPPED",
            "execution_status": "not_executed_due_to_first_fix_gate",
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", summary)
        write_text(out_root / "summary.md", "# v0.3.32 Discovery Probe\n\n- status: `SKIPPED`\n")
        return summary

    taskset = json.loads(Path(entry_taskset_path).read_text(encoding="utf-8"))
    tasks = [row for row in (taskset.get("single_tasks") or []) if isinstance(row, dict)]
    rows: list[dict] = []
    source_failure_counts: dict[str, int] = {}
    ranking_failure_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    for task in tasks:
        step = ((task.get("repair_steps") or [])[0] if isinstance(task.get("repair_steps"), list) else {}) or {}
        candidate_info = build_medium_candidate_rhs_symbols(
            source_model_text=norm(task.get("source_model_text")),
            canonical_rhs_symbol=parse_canonical_rhs_from_repair_step(step),
            use_fixture_only=use_fixture_only,
        )
        ranked = rank_medium_rhs_candidates(
            candidate_rhs_symbols=list(candidate_info.get("candidate_rhs_symbols") or []),
            canonical_rhs_symbol=norm(candidate_info.get("canonical_rhs_symbol")),
            canonical_package_path=norm(candidate_info.get("canonical_package_path")),
            local_cluster_rhs_values=list(candidate_info.get("local_cluster_rhs_values") or []),
            adjacent_component_package_paths=list(candidate_info.get("adjacent_component_package_paths") or []),
        )
        selected_rhs_symbol = norm((ranked[0] or {}).get("candidate_rhs_symbol")) if ranked else ""
        canonical_rhs_symbol = parse_canonical_rhs_from_repair_step(step)
        initial = probe_target_result(
            model_name=norm(task.get("model_name")),
            model_text=norm(task.get("mutated_model_text")),
            wrong_symbol=norm(task.get("wrong_symbol")),
            use_fixture_only=use_fixture_only,
        )
        patched_text, patch_meta = apply_pipe_slice_discovery_patch(
            current_text=norm(task.get("mutated_model_text")),
            step=step,
            selected_rhs_symbol=selected_rhs_symbol,
        )
        post = probe_resolved_result(
            model_name=norm(task.get("model_name")),
            model_text=patched_text,
            use_fixture_only=use_fixture_only,
        ) if bool(patch_meta.get("applied")) else fixture_pipe_target_result(phase="target_hit", wrong_symbol=norm(task.get("wrong_symbol")))
        candidate_contains_canonical = canonical_rhs_symbol in [norm(x) for x in (candidate_info.get("candidate_rhs_symbols") or [])]
        candidate_top1_is_canonical = selected_rhs_symbol == canonical_rhs_symbol
        signature_advance = bool(post.get("check_model_pass") or (norm(initial.get("error_signature")) != norm(post.get("error_signature"))))
        if not signature_advance:
            if not candidate_contains_canonical:
                reason = "candidate_source_missing_canonical"
                source_failure_counts[reason] = source_failure_counts.get(reason, 0) + 1
            elif not candidate_top1_is_canonical:
                reason = "wrong_candidate_selected"
                ranking_failure_counts[reason] = ranking_failure_counts.get(reason, 0) + 1
            else:
                reason = "patch_missed_focal_token"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        rows.append(
            {
                "task_id": norm(task.get("task_id")),
                "candidate_contains_canonical": candidate_contains_canonical,
                "candidate_top1_is_canonical": candidate_top1_is_canonical,
                "patch_applied": bool(patch_meta.get("applied")),
                "signature_advance": signature_advance,
                "selected_rhs_symbol": selected_rhs_symbol,
                "canonical_rhs_symbol": canonical_rhs_symbol,
                "ranked_candidates": ranked,
            }
        )
    task_count = len(rows)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "execution_status": "executed",
        "task_count": task_count,
        "candidate_contains_canonical_rate_pct": round(100.0 * sum(1 for row in rows if row.get("candidate_contains_canonical")) / float(task_count), 1) if task_count else 0.0,
        "candidate_top1_canonical_rate_pct": round(100.0 * sum(1 for row in rows if row.get("candidate_top1_is_canonical")) / float(task_count), 1) if task_count else 0.0,
        "patch_applied_rate_pct": round(100.0 * sum(1 for row in rows if row.get("patch_applied")) / float(task_count), 1) if task_count else 0.0,
        "signature_advance_rate_pct": round(100.0 * sum(1 for row in rows if row.get("signature_advance")) / float(task_count), 1) if task_count else 0.0,
        "candidate_source_failure_counts": source_failure_counts,
        "candidate_ranking_failure_counts": ranking_failure_counts,
        "signature_advance_not_fired_reason_counts": reason_counts,
        "rows": rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.32 Discovery Probe",
                "",
                f"- status: `{summary.get('status')}`",
                f"- candidate_contains_canonical_rate_pct: `{summary.get('candidate_contains_canonical_rate_pct')}`",
                f"- candidate_top1_canonical_rate_pct: `{summary.get('candidate_top1_canonical_rate_pct')}`",
                f"- signature_advance_rate_pct: `{summary.get('signature_advance_rate_pct')}`",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.32 pipe-slice discovery probe.")
    parser.add_argument("--first-fix", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--entry-taskset", default=str(DEFAULT_ENTRY_SPEC_OUT_DIR / "taskset.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_DISCOVERY_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0332_discovery_probe(
        first_fix_path=str(args.first_fix),
        entry_taskset_path=str(args.entry_taskset),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.use_fixture_only),
    )
    print(json.dumps({"status": payload.get("status"), "execution_status": payload.get("execution_status"), "candidate_top1_canonical_rate_pct": payload.get("candidate_top1_canonical_rate_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
