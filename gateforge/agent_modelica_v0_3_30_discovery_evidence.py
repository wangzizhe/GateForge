from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_30_common import (
    DEFAULT_DISCOVERY_OUT_DIR,
    DEFAULT_DISCOVERY_RESULTS_DIR,
    DEFAULT_FIRST_FIX_OUT_DIR,
    DEFAULT_SURFACE_INDEX_OUT_DIR,
    DEFAULT_V0329_ENTRY_TASKSET_PATH,
    SCHEMA_PREFIX,
    apply_medium_redeclare_discovery_patch,
    fixture_dry_run_result,
    load_json,
    now_utc,
    norm,
    parse_canonical_rhs_from_repair_step,
    rank_medium_rhs_candidates,
    run_dry_run,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_30_first_fix_evidence import build_v0330_first_fix_evidence
from .agent_modelica_v0_3_30_surface_index import build_v0330_surface_index


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_discovery_evidence"


def _single_rows(payload: dict) -> list[dict]:
    rows = payload.get("single_tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _surface_row_map(payload: dict) -> dict[str, dict]:
    rows = payload.get("task_rows")
    if not isinstance(rows, list):
        return {}
    return {norm(row.get("task_id")): row for row in rows if isinstance(row, dict) and norm(row.get("task_id"))}


def _run_or_fixture(*, model_name: str, model_text: str, phase: str, use_fixture_only: bool) -> dict:
    if use_fixture_only:
        return fixture_dry_run_result(phase=phase)
    return run_dry_run(model_name, model_text)


def build_v0330_discovery_evidence(
    *,
    first_fix_path: str = str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"),
    surface_index_path: str = str(DEFAULT_SURFACE_INDEX_OUT_DIR / "surface_index.json"),
    entry_taskset_path: str = str(DEFAULT_V0329_ENTRY_TASKSET_PATH),
    results_dir: str = str(DEFAULT_DISCOVERY_RESULTS_DIR),
    out_dir: str = str(DEFAULT_DISCOVERY_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    del results_dir
    if not Path(first_fix_path).exists():
        build_v0330_first_fix_evidence(out_dir=str(Path(first_fix_path).parent), use_fixture_only=use_fixture_only)
    if not Path(surface_index_path).exists():
        build_v0330_surface_index(out_dir=str(Path(surface_index_path).parent), use_fixture_only=use_fixture_only)
    first_fix = load_json(first_fix_path)
    if float(first_fix.get("target_first_failure_hit_rate_pct") or 0.0) < 80.0 or float(first_fix.get("patch_applied_rate_pct") or 0.0) < 70.0 or float(first_fix.get("focal_patch_hit_rate_pct") or 0.0) < 80.0 or float(first_fix.get("signature_advance_rate_pct") or 0.0) < 50.0 or float(first_fix.get("drift_to_compile_failure_unknown_rate_pct") or 0.0) > 10.0:
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "SKIPPED",
            "execution_status": "not_executed_due_to_first_fix_gate",
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", summary)
        write_text(out_root / "summary.md", "# v0.3.30 Discovery Evidence\n\n- status: `SKIPPED`\n")
        return summary

    taskset = load_json(entry_taskset_path)
    tasks = _single_rows(taskset)
    surface_payload = load_json(surface_index_path)
    surface_rows = _surface_row_map(surface_payload)
    rows: list[dict] = []
    reason_counts: dict[str, int] = {}
    source_failure_counts: dict[str, int] = {}
    ranking_failure_counts: dict[str, int] = {}
    for task in tasks:
        task_id = norm(task.get("task_id"))
        step = ((task.get("repair_steps") or [{}])[0] if isinstance(task.get("repair_steps"), list) else {}) or {}
        surface_row = surface_rows.get(task_id) or {}
        initial = _run_or_fixture(model_name=norm(task.get("model_name")), model_text=norm(task.get("mutated_model_text")), phase="target_hit", use_fixture_only=use_fixture_only)
        ranked = rank_medium_rhs_candidates(
            candidate_rhs_symbols=list(surface_row.get("candidate_rhs_symbols") or []),
            canonical_rhs_symbol=norm(surface_row.get("canonical_rhs_symbol")),
            canonical_package_path=norm(surface_row.get("canonical_package_path")),
            local_cluster_rhs_values=list(surface_row.get("local_cluster_rhs_values") or []),
            adjacent_component_package_paths=list(surface_row.get("adjacent_component_package_paths") or []),
        )
        selected_rhs_symbol = norm((ranked[0] or {}).get("candidate_rhs_symbol")) if ranked else ""
        canonical_rhs_symbol = parse_canonical_rhs_from_repair_step(step)
        patched_text, patch_meta = apply_medium_redeclare_discovery_patch(
            current_text=norm(task.get("mutated_model_text")),
            step=step,
            selected_rhs_symbol=selected_rhs_symbol,
        )
        post = _run_or_fixture(model_name=norm(task.get("model_name")), model_text=patched_text, phase="resolved", use_fixture_only=use_fixture_only) if bool(patch_meta.get("applied")) else {}
        signature_advance = bool(post.get("check_model_pass") or (norm(initial.get("error_signature")) != norm(post.get("error_signature"))))
        candidate_contains_canonical = canonical_rhs_symbol in [norm(x) for x in (surface_row.get("candidate_rhs_symbols") or [])]
        candidate_top1_is_canonical = selected_rhs_symbol == canonical_rhs_symbol
        source_failure = ""
        ranking_failure = ""
        if not signature_advance:
            if not candidate_contains_canonical:
                reason = "candidate_source_missing_canonical"
                source_failure = reason
                source_failure_counts[reason] = source_failure_counts.get(reason, 0) + 1
            elif not candidate_top1_is_canonical:
                reason = "wrong_candidate_selected"
                ranking_failure = reason
                ranking_failure_counts[reason] = ranking_failure_counts.get(reason, 0) + 1
            else:
                reason = "patch_missed_focal_token"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        rows.append(
            {
                "task_id": task_id,
                "candidate_contains_canonical": candidate_contains_canonical,
                "candidate_top1_is_canonical": candidate_top1_is_canonical,
                "selected_rhs_symbol": selected_rhs_symbol,
                "canonical_rhs_symbol": canonical_rhs_symbol,
                "candidate_source_failure": source_failure,
                "candidate_ranking_failure": ranking_failure,
                "patch_applied": bool(patch_meta.get("applied")),
                "signature_advance": signature_advance,
                "ranked_candidates": ranked,
                "initial": initial,
                "post": post,
            }
        )
    task_count = len(rows)
    contains_count = sum(1 for row in rows if bool(row.get("candidate_contains_canonical")))
    top1_count = sum(1 for row in rows if bool(row.get("candidate_top1_is_canonical")))
    patch_count = sum(1 for row in rows if bool(row.get("patch_applied")))
    advance_count = sum(1 for row in rows if bool(row.get("signature_advance")))
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "execution_status": "executed",
        "task_count": task_count,
        "candidate_contains_canonical_rate_pct": round(100.0 * contains_count / float(task_count), 1) if task_count else 0.0,
        "candidate_top1_canonical_rate_pct": round(100.0 * top1_count / float(task_count), 1) if task_count else 0.0,
        "patch_applied_rate_pct": round(100.0 * patch_count / float(task_count), 1) if task_count else 0.0,
        "signature_advance_rate_pct": round(100.0 * advance_count / float(task_count), 1) if task_count else 0.0,
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
                "# v0.3.30 Discovery Evidence",
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
    parser = argparse.ArgumentParser(description="Build the v0.3.30 discovery evidence.")
    parser.add_argument("--first-fix", default=str(DEFAULT_FIRST_FIX_OUT_DIR / "summary.json"))
    parser.add_argument("--surface-index", default=str(DEFAULT_SURFACE_INDEX_OUT_DIR / "surface_index.json"))
    parser.add_argument("--entry-taskset", default=str(DEFAULT_V0329_ENTRY_TASKSET_PATH))
    parser.add_argument("--results-dir", default=str(DEFAULT_DISCOVERY_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_DISCOVERY_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0330_discovery_evidence(
        first_fix_path=str(args.first_fix),
        surface_index_path=str(args.surface_index),
        entry_taskset_path=str(args.entry_taskset),
        results_dir=str(args.results_dir),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.use_fixture_only),
    )
    print(json.dumps({"status": payload.get("status"), "execution_status": payload.get("execution_status"), "candidate_top1_canonical_rate_pct": payload.get("candidate_top1_canonical_rate_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
